#!/usr/bin/env python3
"""
Watchlist & Index 全量同步脚本 (硬编码目标清单版)
==============================================================================

功能说明:
本脚本以**硬编码方式**定义了 VERA 系统的完整监控资产清单，并通过"清空+重建"
的全量同步策略，将 `Watchlist` 和 `Index` 两张表与预定义清单保持一致。

与 manage_data.py 的关系:
- `manage_data.py` → 从文件 (`imports/symbols.txt`) 动态读取，支持灵活增删。
- 本脚本 → 直接硬编码在代码中，架构更稳定，适合在代码层面版本化管理资产配置。

资产清单说明:
- WATCHLIST_TARGETS: 港股 / 美股 / A股 的个股 + 各类 ETF（共约 60 个标的）。
- INDEX_TARGETS: HK / US / CN 三地核心指数（共 11 个），存入独立的 Index 表。

同步策略 (Full Replace):
1. 对比 (文件清单 vs 数据库)，打印新增数量。
2. 执行 DELETE + INSERT，完全重建两表。
   - ⚠️ 注意: 这一策略会删除所有行但历史行情数据不受影响（仅配置表被清空）。

返回值:
new_stocks: 本次新增的 Watchlist 标的列表 (用于调用方触发数据同步)
new_indices: 本次新增的 Index 标的列表

使用方法:
    python3 sync_full_watchlist.py

作者: Antigravity
日期: 2026-01-23
"""
import sys
import os
from datetime import datetime
from sqlmodel import Session, select, delete

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database import engine
from models import Watchlist, Index

# 完整目标清单
WATCHLIST_TARGETS = [
    # === HK 港股 ===
    {"symbol": "00005.HK", "name": "汇丰控股", "market": "HK"},
    {"symbol": "00700.HK", "name": "腾讯控股", "market": "HK"},
    {"symbol": "00998.HK", "name": "中信银行", "market": "HK"},
    {"symbol": "01919.HK", "name": "中远海控", "market": "HK"},
    {"symbol": "06099.HK", "name": "招商证券", "market": "HK"},
    {"symbol": "09988.HK", "name": "阿里巴巴-W", "market": "HK"},
    
    # === HK ETF ===
    {"symbol": "02800.HK", "name": "盈富基金", "market": "HK"},
    {"symbol": "03033.HK", "name": "南方恒生科技", "market": "HK"},
    {"symbol": "03110.HK", "name": "3110", "market": "HK"},
    {"symbol": "03437.HK", "name": "博时央企红利", "market": "HK"},
    {"symbol": "03447.HK", "name": "南方亚太房托", "market": "HK"},
    
    # === US 美股 ===
    {"symbol": "AAPL", "name": "苹果", "market": "US"},
    {"symbol": "AMZN", "name": "亚马逊", "market": "US"},
    {"symbol": "BAC", "name": "美国银行", "market": "US"},
    {"symbol": "BTC", "name": "Grayscale Bitcoin Mini Trust", "market": "US"},
    {"symbol": "GOOG", "name": "谷歌-C", "market": "US"},
    {"symbol": "IBIT", "name": "iShares比特币信托", "market": "US"},
    {"symbol": "META", "name": "Meta Platforms", "market": "US"},
    {"symbol": "MSFT", "name": "微软", "market": "US"},
    {"symbol": "NVDA", "name": "英伟达", "market": "US"},
    {"symbol": "TSLA", "name": "特斯拉", "market": "US"},
    {"symbol": "TSM", "name": "台积电", "market": "US"},
    
    # === US ETF ===
    {"symbol": "DIA", "name": "道琼斯指数ETF", "market": "US"},
    {"symbol": "GLD", "name": "黄金现货SPDR", "market": "US"},
    {"symbol": "IWM", "name": "罗素2000指数ETF", "market": "US"},
    {"symbol": "QQQ", "name": "纳指100ETF", "market": "US"},
    {"symbol": "SGOV", "name": "0-3月美国国债ETF", "market": "US"},
    {"symbol": "SPY", "name": "标普500指数ETF", "market": "US"},
    {"symbol": "TLT", "name": "20年期以上国债ETF", "market": "US"},
    {"symbol": "USMV", "name": "美国最小波动率ETF", "market": "US"},
    {"symbol": "VTV", "name": "价值股ETF", "market": "US"},
    {"symbol": "VUG", "name": "成长股ETF", "market": "US"},
    {"symbol": "VYM", "name": "红利股ETF", "market": "US"},
    {"symbol": "XLB", "name": "基础材料ETF", "market": "US"},
    {"symbol": "XLC", "name": "通讯服务ETF", "market": "US"},
    {"symbol": "XLE", "name": "能源指数ETF", "market": "US"},
    {"symbol": "XLF", "name": "金融行业ETF", "market": "US"},
    {"symbol": "XLI", "name": "工业行业ETF", "market": "US"},
    {"symbol": "XLK", "name": "科技行业ETF", "market": "US"},
    {"symbol": "XLP", "name": "消费品指数ETF", "market": "US"},
    {"symbol": "XLRE", "name": "房地产行业ETF", "market": "US"},
    {"symbol": "XLU", "name": "公共事业指数ETF", "market": "US"},
    {"symbol": "XLV", "name": "医疗保健行业ETF", "market": "US"},
    {"symbol": "XLY", "name": "消费品指数SPDR", "market": "US"},
    {"symbol": "BTC-USD", "name": "比特币", "market": "US"},
    
    # === CN A股 ===
    {"symbol": "600030.SH", "name": "中信证券", "market": "CN"},
    {"symbol": "600309.SH", "name": "万华化学", "market": "CN"},
    {"symbol": "600536.SH", "name": "中国软件", "market": "CN"},
    {"symbol": "601519.SH", "name": "大智慧", "market": "CN"},
    {"symbol": "601919.SH", "name": "中远海控", "market": "CN"},
    {"symbol": "601998.SH", "name": "中信银行", "market": "CN"},
    
    # === CN ETF ===
    {"symbol": "159662.SZ", "name": "航运ETF", "market": "CN"},
    {"symbol": "159751.SZ", "name": "港股通科技ETF", "market": "CN"},
    {"symbol": "159851.SZ", "name": "金融科技ETF", "market": "CN"},
    {"symbol": "159852.SZ", "name": "软件ETF", "market": "CN"},
    {"symbol": "512800.SH", "name": "银行ETF", "market": "CN"},
    {"symbol": "512880.SH", "name": "证券ETF", "market": "CN"},
    {"symbol": "513190.SH", "name": "港股通金融ETF", "market": "CN"},
    {"symbol": "516020.SH", "name": "化工ETF", "market": "CN"},
]

INDEX_TARGETS = [
    # === HK 指数 ===
    {"symbol": "HSCC", "name": "红筹指数", "market": "HK"},
    {"symbol": "HSI", "name": "恒生指数", "market": "HK"},
    {"symbol": "HSCE", "name": "国企指数", "market": "HK"},
    {"symbol": "HSTECH", "name": "恒生科技指数", "market": "HK"},
    
    # === US 指数 ===
    {"symbol": "DJI", "name": "道琼斯工业指数", "market": "US"},
    {"symbol": "NDX", "name": "纳斯达克100指数", "market": "US"},
    {"symbol": "SPX", "name": "标普500指数", "market": "US"},
    
    # === CN 指数 ===
    {"symbol": "000001.SH", "name": "上证指数", "market": "CN"},
    {"symbol": "000016.SH", "name": "上证50", "market": "CN"},
    {"symbol": "000300.SH", "name": "沪深300", "market": "CN"},
    {"symbol": "000905.SH", "name": "中证500", "market": "CN"},
]

def sync_tables():
    print("🚀 开始同步关注列表和指数表...")
    
    with Session(engine) as session:
        # 1. 获取现有数据用于对比
        existing_watchlist = {item.symbol for item in session.exec(select(Watchlist)).all()}
        existing_index = {item.symbol for item in session.exec(select(Index)).all()}
        
        target_watchlist = {item["symbol"] for item in WATCHLIST_TARGETS}
        target_index = {item["symbol"] for item in INDEX_TARGETS}
        
        # 2. 识别新增项
        new_watchlist = target_watchlist - existing_watchlist
        new_index = target_index - existing_index
        
        print(f"📊 新增 Watchlist: {len(new_watchlist)} 个")
        print(f"📊 新增 Index: {len(new_index)} 个")
        
        if new_watchlist:
            print("  新增 Watchlist 标的:")
            for sym in new_watchlist:
                item = next(i for i in WATCHLIST_TARGETS if i["symbol"] == sym)
                print(f"    - {sym}: {item['name']}")
        
        if new_index:
            print("  新增 Index 标的:")
            for sym in new_index:
                item = next(i for i in INDEX_TARGETS if i["symbol"] == sym)
                print(f"    - {sym}: {item['name']}")
        
        # 3. 清空并重建表（确保完全一致）
        print("\n🗑️  清空现有表...")
        session.exec(delete(Watchlist))
        session.exec(delete(Index))
        session.commit()
        
        # 4. 批量插入新数据
        print(f"📥 插入 {len(WATCHLIST_TARGETS)} 个 Watchlist 项...")
        for target in WATCHLIST_TARGETS:
            item = Watchlist(
                symbol=target["symbol"],
                name=target["name"],
                market=target["market"],
                added_at=datetime.utcnow()
            )
            session.add(item)
        
        print(f"📥 插入 {len(INDEX_TARGETS)} 个 Index 项...")
        for target in INDEX_TARGETS:
            item = Index(
                symbol=target["symbol"],
                name=target["name"],
                market=target["market"],
                added_at=datetime.utcnow()
            )
            session.add(item)
        
        session.commit()
        print("✅ 同步完成!")
        
        # 5. 返回新增项用于后续处理
        return list(new_watchlist), list(new_index)

if __name__ == "__main__":
    new_stocks, new_indices = sync_tables()
    
    if new_stocks or new_indices:
        print(f"\n🔔 需要补全历史数据的新标的: {len(new_stocks) + len(new_indices)} 个")
    else:
        print("\n✅ 无新增标的，数据已是最新!")
