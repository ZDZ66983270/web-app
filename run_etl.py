"""
ETL 快照同步脚本 (MarketDataDaily → MarketSnapshot)
==============================================================================

功能说明:
本脚本是 VERA 系统 ETL 流程的**最终同步步骤**，负责将历史日线库的最新值
提取并写入前端实时看板所依赖的 `MarketSnapshot` 快照表。

核心逻辑:
1. **遍历全部唯一标的**: 从 `MarketDataDaily` 表中取出所有不重复的 (symbol, market) 组合。
2. **取最新日线记录**: 对每个标的，取 timestamp 最新一条日线数据。
3. **计算涨跌幅**:
   - 优先从 `MarketDataDaily` 中取前一交易日的收盘价计算 change / pct_change。
   - 若无前一日数据，则使用记录自身已存的 change/pct_change 字段作为备用。
4. **UPSERT 到 MarketSnapshot**:
   - 若该标的已有快照 → UPDATE
   - 若无快照 → INSERT

数据流:
RawMarketData → [process_raw_data_optimized.py] → MarketDataDaily → [本脚本] → MarketSnapshot

字段说明:
- MarketSnapshot.price = MarketDataDaily.close (最新收盘价)
- MarketSnapshot.pe 字段: 优先使用日线表中的 pe；若缺失但有 eps，则本地通过 close/eps 计算。
- MarketSnapshot.data_source = 'etl' (区分于 realtime API 写入的快照)

使用方法:
    python3 run_etl.py

注意:
- 本脚本不下载任何新数据，仅是数据库内部的表间同步。
- 应在 `process_raw_data_optimized.py` 之后运行，以确保 MarketDataDaily 已是最新。

作者: Antigravity
日期: 2026-01-23
"""
import sys
sys.path.insert(0, 'backend')

from database import engine
from sqlmodel import Session, select
from models import MarketDataDaily, MarketSnapshot
from datetime import datetime


def run_etl_pipeline():
    print("=" * 80)
    print("🔄 ETL: 历史数据仓库 → 生产快照")
    print("=" * 80)
    
    success_count = 0
    fail_count = 0
    
    with Session(engine) as session:
        # 获取所有唯一的(symbol, market)组合
        result = session.exec(
            select(MarketDataDaily.symbol, MarketDataDaily.market)
            .distinct()
        )
        
        symbols = list(result.all())
        print(f"\n找到 {len(symbols)} 个标的需要处理\n")
        
        for idx, (symbol, market) in enumerate(symbols, 1):
            try:
                print(f"[{idx}/{len(symbols)}] {symbol} ({market})...", end=" ")
                
                # 1. 获取最新记录
                latest = session.exec(
                    select(MarketDataDaily)
                    .where(
                        MarketDataDaily.symbol == symbol,
                        MarketDataDaily.market == market
                    )
                    .order_by(MarketDataDaily.timestamp.desc())
                ).first()
                
                if not latest:
                    print("❌ 无数据")
                    fail_count += 1
                    continue
                
                # 2. 获取前一日收盘价（用于计算涨跌幅）
                prev_day = session.exec(
                    select(MarketDataDaily)
                    .where(
                        MarketDataDaily.symbol == symbol,
                        MarketDataDaily.market == market,
                        MarketDataDaily.timestamp < latest.timestamp
                    )
                    .order_by(MarketDataDaily.timestamp.desc())
                ).first()
                
                # 3. 计算涨跌幅
                if prev_day and prev_day.close > 0:
                    change = latest.close - prev_day.close
                    pct_change = (change / prev_day.close) * 100
                    prev_close = prev_day.close
                    calc_method = "计算"
                else:
                    # 如果没有前一日数据，使用原始值
                    change = latest.change or 0
                    pct_change = latest.pct_change or 0
                    prev_close = latest.prev_close
                    calc_method = "原始"
                
                # 4. UPSERT到MarketSnapshot
                existing = session.exec(
                    select(MarketSnapshot)
                    .where(
                        MarketSnapshot.symbol == symbol,
                        MarketSnapshot.market == market
                    )
                ).first()
                
                if existing:
                    # UPDATE
                    existing.price = latest.close
                    existing.open = latest.open
                    existing.high = latest.high
                    existing.low = latest.low
                    existing.prev_close = prev_close
                    existing.change = change
                    existing.pct_change = pct_change
                    existing.volume = latest.volume
                    existing.turnover = latest.turnover
                    existing.pe = latest.pe
                    # Fallback PE calculation if yfinance missing it but we have EPS
                    if (not existing.pe or existing.pe == 0) and latest.eps and latest.eps > 0:
                        existing.pe = latest.close / latest.eps
                        
                    existing.pb = latest.pb
                    existing.dividend_yield = latest.dividend_yield
                    existing.market_cap = latest.market_cap
                    existing.timestamp = latest.timestamp
                    existing.data_source = 'etl'
                    existing.updated_at = datetime.now()
                    session.add(existing)
                else:
                    # INSERT
                    current_pe = latest.pe
                    if (not current_pe or current_pe == 0) and latest.eps and latest.eps > 0:
                        current_pe = latest.close / latest.eps
                        
                    snapshot = MarketSnapshot(
                        symbol=symbol,
                        market=market,
                        price=latest.close,
                        open=latest.open,
                        high=latest.high,
                        low=latest.low,
                        prev_close=prev_close,
                        change=change,
                        pct_change=pct_change,
                        volume=latest.volume,
                        turnover=latest.turnover,
                        pe=current_pe,
                        pb=latest.pb,
                        dividend_yield=latest.dividend_yield,
                        market_cap=latest.market_cap,
                        timestamp=latest.timestamp, # ✅ Fixed: field name is timestamp, not date
                        data_source='etl',
                        fetch_time=datetime.now(),
                        updated_at=datetime.now()
                    )
                    session.add(snapshot)
                
                session.commit()
                print(f"✅ {calc_method} | 涨跌: {change:.2f} ({pct_change:.2f}%)")
                success_count += 1
                
            except Exception as e:
                print(f"❌ 错误: {e}")
                session.rollback()
                fail_count += 1

    # 验证结果
    print("\n" + "=" * 80)
    print("📊 ETL完成统计")
    print("=" * 80)
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")

    with Session(engine) as session:
        count = session.exec(select(MarketSnapshot)).all()
        print(f"📸 MarketSnapshot表记录数: {len(count)}")

    print("=" * 80)

if __name__ == "__main__":
    run_etl_pipeline()

