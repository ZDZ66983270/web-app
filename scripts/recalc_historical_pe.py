# -*- coding: utf-8 -*-
"""
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

PE Recalculation Script (历史回填工具)
==================================

功能:
全量或者增量重算所有个股的历史 PE/EPS 数据，并将结果写入 `MarketDataDaily` 表。

核心流程:
1. **遍历资产**: 扫描 Watchlist 中所有股票 (跳过指数/Crypto)。
2. **准备数据**:
   - 获取该资产所有的历史财报 (`FinancialFundamentals`)。
   - 获取该资产所有的历史日线 (`MarketDataDaily`)。
3. **逐日计算**:
   - 对于每一个交易日，调用 `valuation_calculator.calculate_pe_metrics_with_cache`。
   - **关键**: 必须传入 `session` 以启用动态汇率查询。
4. **批量更新**:
   - 将计算出的 `pe_ttm` 和 `eps` 批量 update 回数据库。

逻辑 1: **缓存优化 (Memory & Performance)**
------------------------------------
为了避免 N(Dates) * M(Calls) 的数据库查询，脚本采用 "Pre-fetch" 策略：
- 一次性加载某只股票的所有 `MarketDataDaily` 记录。
- 一次性加载所有的 `FinancialFundamentals`。
- 在内存中进行日期匹配和指标计算。

逻辑 2: **汇率注入 (FX Injection)**
--------------------------
- 历史回填时，`calculate_pe_metrics_with_cache` 需要访问 `ForexRate` 表。
- 由于 `ForexRate` 数据量大且需要精确日期匹配，我们**不**预加载所有汇率，
- 而是将 `db_session` 传递给计算函数，由其在需要时查询 (利用 SQL 的 B-Tree 索引)。

逻辑 3: **增量更新 (Incremental Updates)**
--------------------------
- 脚本支持 `--full` 参数。
- 默认情况下，如果某日已存在 `pe_ttm` 且不强制覆盖，则跳过计算，节省时间。


注意:
此通过 `recalc_pe_history` 函数实现，它是 VERA Pro 逻辑的唯一回填入口。
"""
import sys
import os
import pandas as pd
import numpy as np
import bisect
from sqlmodel import Session, select
from sqlalchemy import text

# Ensure backend can be imported
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(base_dir, 'backend')
if base_dir not in sys.path: sys.path.append(base_dir)
if backend_dir not in sys.path: sys.path.append(backend_dir)

from database import engine
from models import Watchlist, FinancialFundamentals, MarketDataDaily
from valuation_calculator import calculate_pe_metrics_with_cache, get_shares_outstanding

def recalc_pe_history(asset_id, session):
    """
    Recalculate PE TTM history for a single asset.
    """
    # Build TTM Series
    # fin_rows is list of (date, eps, report_type) - Need to update select to include report_type
    # But wait, original select only got (date, eps).
    # We need report_type to distinguish.
    # Actually, simpler logic:
    # If market is US (or generally), assume quarterly requires rolling sum.
    # But let's look at the data gaps.
    # Algorithm:
    # 1. Convert to DataFrame.
    # 2. Sort by date.
    # 3. Calculate Rolling 4 Sum.
    # 4. But wait, Annual reports might be interleaved.
    #    If record is 'annual', EPS is already TTM.
    #    If record is 'quarterly', it is 3-month.
    #    Yahoo Financials usually provides distinct Quarterly and Annual series.
    #    If we strictly use Quarterly series and sum 4, we get TTM.
    #    If we just use Annual series, we get less frequent updates.
    #    Best: Use Quarterly series for high frequency.
    
    # Let's verify if we have enough quarterly data.
    # Ideally, we query ONLY quarterly data for US and sum them.
    # If we query all and mix, rolling sum might double count Annual.
    
    # Upgraded Query: Fetch all, deduce TTM.
    # Re-fetch with report_type
    fin_rows = session.exec(
        select(
            FinancialFundamentals.as_of_date,
            FinancialFundamentals.eps,
            FinancialFundamentals.report_type,
            FinancialFundamentals.net_income_ttm,
            FinancialFundamentals.currency,
            FinancialFundamentals.net_income_common_ttm, # VERA Pro
            FinancialFundamentals.shares_diluted,          # VERA Pro
            FinancialFundamentals.filing_date,             # VERA Pro
        )
        .where(FinancialFundamentals.symbol == asset_id)
        .where(FinancialFundamentals.eps != None)
        .order_by(FinancialFundamentals.as_of_date.desc())
    ).all()
    
    if not fin_rows:
        return 0
        
    # Calculate TTM EPS
    # Strategy:
    # 1. Market Differentiation:
    #    - US: Quarterly reports are discrete. We MUST sum last 4 quarters to get TTM.
    #    - HK/CN: Quarterly reports are often Cumulative (YTD) or already TTM in some feeds.
    #      For AkShare HK, we specifically fetched TTM EPS.
    #      For CN, we might have mixed data.
    #      SAFE APPROACH: 
    # Determine market from asset_id
    market = asset_id.split(':')[0] if ':' in asset_id else "US"
    # Skip CN market: use source-provided PE/PE_TTM directly, no recalculation needed
    if market == "CN":
        return 0

    # Build financials cache for valuation calculator
    financials_cache = []
    for row in fin_rows:
        # row: (as_of_date, eps, report_type, net_income_ttm, currency, net_income_common_ttm, shares_diluted, filing_date)
        ff = FinancialFundamentals(
            symbol=asset_id,
            as_of_date=row[0],
            eps=row[1],
            report_type=row[2],
            net_income_ttm=row[3] if len(row) > 3 else None,
            currency=row[4] if len(row) > 4 else None,
            net_income_common_ttm=row[5] if len(row) > 5 else None,
            shares_diluted=row[6] if len(row) > 6 else None,
            filing_date=row[7] if len(row) > 7 else None, # PIT compliance
        )
        financials_cache.append(ff)

    # Fetch daily prices
    price_rows = session.exec(
        select(MarketDataDaily.timestamp, MarketDataDaily.close)
        .where(MarketDataDaily.symbol == asset_id)
        .order_by(MarketDataDaily.timestamp)
    ).all()
    if not price_rows:
        return 0

    # Pre-fetch shares to avoid repetitive API calls
    shares_outstanding = get_shares_outstanding(asset_id, market)

    # Compute PE/EPS for each date using valuation calculator (keeps negative values)
    updates = []
    for ts, close in price_rows:
        metrics = calculate_pe_metrics_with_cache(
            symbol=asset_id,
            market=market,
            close_price=close,
            as_of_date=ts[:10],
            financials_cache=financials_cache,
            shares_outstanding=shares_outstanding,
            session=session
        )
        eps_val = metrics.get('eps')
        pe_val = metrics.get('pe')
        if eps_val is not None and pe_val is not None:
            updates.append({
                'pe': pe_val,
                'eps': eps_val,
                's': asset_id,
                'ts': ts,
            })

    # Batch update MarketDataDaily
    if updates:
        stmt = text("""
            UPDATE marketdatadaily 
            SET pe_ttm = :pe, eps = :eps 
            WHERE symbol = :s AND timestamp = :ts
        """)
        session.connection().execute(stmt, updates)
        session.commit()
        
    return len(updates)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", help="Specific Canonical ID")
    parser.add_argument("--market", default="ALL", help="Choose market: HK, CN, US, ALL (case insensitive)")
    args = parser.parse_args()

    # Normalize market arg
    args.market = args.market.upper()
    valid_markets = ["HK", "CN", "US", "ALL"]
    if args.market not in valid_markets:
         print(f"Error: Invalid market '{args.market}'. Choose from {valid_markets}")
         return

    with Session(engine) as session:
        query = select(Watchlist)
        if args.symbol:
            query = query.where(Watchlist.symbol == args.symbol)
        elif args.market != "ALL":
            query = query.where(Watchlist.market == args.market)
            
        assets = session.exec(query).all()
        
        total = len(assets)
        print(f"🚀 Starting PE Recalc for {total} assets...")
        
        for idx, asset in enumerate(assets, 1):
            if any(x in asset.symbol for x in [':INDEX:', ':ETF:', ':CRYPTO:', ':TRUST:', ':FUND:']):
                continue
                
            count = recalc_pe_history(asset.symbol, session)
            if count > 0:
                print(f"[{idx}/{total}] {asset.symbol}: Updated {count} PE records.")
            else:
                # verbose option? just skip print to keep clean
                pass
                
        print("\n✅ Recalculation Complete.")

if __name__ == "__main__":
    main()
