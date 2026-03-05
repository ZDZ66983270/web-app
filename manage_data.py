#!/usr/bin/env python3
"""
Data Management Console - 数据管理中枢 (交互式清理 / 导入 / 同步)
==============================================================================

功能说明:
本脚本是 VERA 系统的**运维控制台**，提供对核心数据库表的增删改同步操作，
是系统初始化、重置和维护的主要入口。通过一个交互式菜单统一管理以下功能：

操作项:
1. **清除行情数据** (rawmarketdata / marketdatadaily / marketsnapshot)
   - 全量清空行情相关三表。用于重置下载或修复数据问题。

2. **清除财务数据** (financialfundamentals / dividendfact / splitfact)
   - 全量清空财报及企业行为数据。

3. **清除监控列表** (watchlist)
   - ⚠️ 危险操作: 需要二次 'yes' 确认。

4. **从 symbols.txt 重新导入** (Force Re-import)
   - 先清空 watchlist，再从 `imports/symbols.txt` 全量解析导入。
   - 解析规则: 行级注释 `#` 定义 `市场/类型` 分组（如 `# CN Stocks`），
     后续非空行即为该组资产的代码。

5. **同步监控列表 (Smart Sync)** ⭐ 推荐
   - 增量对比: 计算 (文件 vs 数据库) 的新增 / 待移除 delta。
   - 新增和移除均有单独的交互确认步骤，安全可控。

6. **全量财务补全与估值重算** (Full Backfill & Repair)
   - 依序调用: fetch_financials.py (HK -> US -> CN) + 估值重算脚本。
   - 包含限流等待（避免 Yahoo 频率限制）。

文件依赖:
- `imports/symbols.txt`: 监控资产清单文件
- `backend/database.db`: 主 SQLite 数据库
- `fetch_financials.py`: 财报获取脚本 (被 run_full_backfill 调用)

注意事项:
- 清除操作无法撤销，请谨慎执行。
- `Smart Sync` (5号) 比 `Force Re-import` (4号) 更安全，优先使用。
- 行情数据清除后需重新运行 `download_full_history.py` → `process_raw_data_optimized.py`。

作者: Antigravity
日期: 2026-01-23
"""

import sys
sys.path.append('backend')

from sqlmodel import Session, create_engine, text, select
from datetime import datetime
import os
from collections import defaultdict

# Late import to avoid circular dependency if possible, but here models are needed
from backend.models import Watchlist
import subprocess

engine = create_engine('sqlite:///backend/database.db')

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def print_section(title):
    """打印小节标题"""
    print("\n" + "-" * 80)
    print(title)
    print("-" * 80)

def get_table_count(session, table_name):
    """获取表记录数"""
    try:
        result = session.exec(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.first()[0]
    except:
        return 0

def show_current_status():
    """显示当前数据状态"""
    print_section("当前数据状态")
    
    with Session(engine) as session:
        tables = {
            '行情数据': [
                ('rawmarketdata', 'RAW原始数据'),
                ('marketdatadaily', '历史日线'),
                ('marketsnapshot', '最新快照')
            ],
            '财务数据': [
                ('financialfundamentals', '财务基本面'),
                ('dividendfact', '分红记录'),
                ('splitfact', '拆股记录')
            ],
            '配置数据': [
                ('watchlist', '监控列表'),
                ('stockinfo', '股票信息')
            ]
        }
        
        for category, table_list in tables.items():
            print(f"\n{category}:")
            for table, desc in table_list:
                count = get_table_count(session, table)
                print(f"  {desc:15s} ({table:25s}): {count:>10,} 条")

def parse_symbols_file(file_path):
    """
    解析 symbols.txt 文件
    返回: list of dict {'canonical_id', 'market', 'ticker'}
    """
    if not os.path.exists(file_path):
        print(f"  ❌ 文件不存在: {file_path}")
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_market = None
    current_type = None
    parsed_symbols = []
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Parse Headers
        if line.startswith('#'):
            current_market = None
            current_type = None
            if 'CN Indices' in line or 'A股指数' in line:
                current_market, current_type = 'CN', 'INDEX'
            elif 'HK Indices' in line or '港股指数' in line:
                current_market, current_type = 'HK', 'INDEX'
            elif 'US Indices' in line or '美股指数' in line:
                current_market, current_type = 'US', 'INDEX'
            elif 'CN Stocks' in line or ('A股' in line and 'ETF' not in line):
                current_market, current_type = 'CN', 'STOCK'
            elif 'HK Stocks' in line or ('港股' in line and 'ETF' not in line):
                current_market, current_type = 'HK', 'STOCK'
            elif 'US Stocks' in line or ('美股' in line and 'ETF' not in line):
                current_market, current_type = 'US', 'STOCK'
            elif 'CN ETF' in line or 'A股 ETF' in line:
                current_market, current_type = 'CN', 'ETF'
            elif 'HK ETF' in line or '港股 ETF' in line:
                current_market, current_type = 'HK', 'ETF'
            elif 'US ETF' in line or '美股 ETF' in line:
                current_market, current_type = 'US', 'ETF'
            elif 'Trusts' in line or '信托' in line:
                current_market, current_type = 'US', 'TRUST'
            elif 'Crypto' in line or '加密货币' in line:
                current_market, current_type = 'US', 'CRYPTO' # Changed from WORLD to US
            continue
        
        # Parse Item
        if current_market and current_type:
            canonical_id = f"{current_market}:{current_type}:{line}"
            parsed_symbols.append({
                'canonical_id': canonical_id,
                'market': current_market,
                'ticker': line
            })
            
    return parsed_symbols

def clear_market_data():
    """清除行情数据"""
    print_section("清除行情数据")
    tables = ['rawmarketdata', 'marketdatadaily', 'marketsnapshot']
    with Session(engine) as session:
        for table in tables:
            count = get_table_count(session, table)
            if count > 0:
                session.exec(text(f"DELETE FROM {table}"))
                print(f"  ✅ 已清空 {table} ({count:,} 条)")
            else:
                print(f"  ⏭️  {table} 已为空")
        session.commit()
    print("\n✅ 行情数据清除完成")

def clear_financial_data():
    """清除财务数据"""
    print_section("清除财务数据")
    tables = ['financialfundamentals', 'dividendfact', 'splitfact']
    with Session(engine) as session:
        for table in tables:
            count = get_table_count(session, table)
            if count > 0:
                session.exec(text(f"DELETE FROM {table}"))
                print(f"  ✅ 已清空 {table} ({count:,} 条)")
            else:
                print(f"  ⏭️  {table} 已为空")
        session.commit()
    print("\n✅ 财务数据清除完成")

def clear_watchlist():
    """清除监控列表"""
    print_section("清除监控列表")
    with Session(engine) as session:
        count = get_table_count(session, 'watchlist')
        if count > 0:
            print(f"\n⚠️  警告: 即将删除 {count} 个监控资产")
            confirm = input("确认删除? (yes/no): ").strip().lower()
            if confirm == 'yes':
                session.exec(text("DELETE FROM watchlist"))
                session.commit()
                print(f"  ✅ 已清空 watchlist ({count:,} 条)")
            else:
                print("  ⏭️  取消操作")
        else:
            print("  ⏭️  watchlist 已为空")

def import_symbols():
    """从 symbols.txt 导入监控列表 (全量覆盖)"""
    print_section("导入 symbols.txt (重新导入)")
    
    symbols_file = "imports/symbols.txt"
    parsed_symbols = parse_symbols_file(symbols_file)
    print(f"  📄 解析到 {len(parsed_symbols)} 个资产")

    try:
        with Session(engine) as session:
            # 清空现有
            # 注意: 这个函数最初的设计是清空后导入? 
            # 原始代码是 DELETE FROM watchlist 
            # 既然有 Smart Sync，保留这个作为 'Force Re-import' 选项
            print("  ⚠️  即将在导入前清空现有 Watchlist...")
            session.exec(text("DELETE FROM watchlist"))
            
            added = 0
            for item in parsed_symbols:
                try:
                    # 添加
                    watchlist_item = Watchlist(
                        symbol=item['canonical_id'],
                        market=item['market'],
                        name=item['ticker']
                    )
                    session.add(watchlist_item)
                    added += 1
                except Exception as e:
                    print(f"  ⚠️  跳过: {item['canonical_id']} ({e})")
            
            session.commit()
            print(f"\n  ✅ 成功导入 {added} 个资产到 watchlist")
            
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")

def sync_symbols():
    """Smart Sync: 增量同步"""
    print_section("同步监控列表 (Smart Sync)")
    
    symbols_file = "imports/symbols.txt"
    file_items = parse_symbols_file(symbols_file) # List of dicts
    
    if not file_items:
        print("  ⚠️  文件为空或不存在，无法同步。")
        return

    # Map file content: Canonical ID -> Item Dict
    file_map = {item['canonical_id']: item for item in file_items}
    file_ids = set(file_map.keys())
    
    with Session(engine) as session:
        # Get DB Content
        db_rows = session.exec(select(Watchlist)).all()
        db_map = {row.symbol: row for row in db_rows}
        db_ids = set(db_map.keys())
        
        # Calculate Delta
        to_add = file_ids - db_ids
        to_remove = db_ids - file_ids
        
        print(f"  📊 分析结果:")
        print(f"     当前数据库: {len(db_ids)} 个")
        print(f"     文件列表:   {len(file_ids)} 个")
        print(f"     ➕ 待新增:   {len(to_add)} 个")
        print(f"     ➖ 待移除:   {len(to_remove)} 个")
        
        # 1. Handle Additions
        if to_add:
            print("\n  👉 [新增列表]:")
            for i, sid in enumerate(to_add):
                if i < 5: print(f"     + {sid}")
            if len(to_add) > 5: print(f"     ... 等 {len(to_add)} 个")
            
            confirm = input(f"  ❓ 确认添加 {len(to_add)} 个新资产吗? (y/n) [y]: ").strip().lower()
            if confirm in ('', 'y', 'yes'):
                count = 0
                for sid in to_add:
                    item = file_map[sid]
                    new_rec = Watchlist(symbol=sid, market=item['market'], name=item['ticker'])
                    session.add(new_rec)
                    count += 1
                session.commit()
                print(f"     ✅ 已添加 {count} 个资产。")
            else:
                print("     ⏭️  跳过添加。")
        else:
            print("\n  ✅ 没有需要新增的资产。")
            
        # 2. Handle Removals
        if to_remove:
            print("\n  👉 [移除列表]:")
            for i, sid in enumerate(to_remove):
                if i < 5: print(f"     - {sid}")
            if len(to_remove) > 5: print(f"     ... 等 {len(to_remove)} 个")
            
            # Risk warning: Removing assets clears their history association usually? 
            # Or just removes from watchlist.
            print("  ⚠️  注意: 移除资产不会自动删除已下载的历史行情数据，但会停止更新它们。")
            
            confirm = input(f"  ❓ 确认从监控列表中移除这 {len(to_remove)} 个资产吗? (y/n) [n]: ").strip().lower()
            if confirm in ('y', 'yes'):
                # Bulk delete
                # SQLite usually can't convert set to tuple easily in 'in_', wait it can.
                for sid in to_remove:
                    row = db_map[sid]
                    session.delete(row)
                session.commit()
                print(f"     ✅ 已移除 {len(to_remove)} 个资产。")
            else:
                print("     ⏭️  跳过移除。")
        else:
            print("\n  ✅ 没有需要移除的资产。")

def run_full_backfill():
    """执行分批全量补全逻辑"""
    print_section("全量财务补全与估值重算 (Full Backfill & Repair)")
    print("🚀 准备执行全量修复序列...")
    print("⚠️  由于 Yahoo 限流，该过程将包含阶梯式等待，预计耗时 15-20 分钟。")
    
    confirm = input("确认启动全量补全? (y/n) [n]: ").strip().lower()
    if confirm not in ('y', 'yes'):
        print("⏭️  取消操作")
        return

    try:
        # 1. HK Market
        print("\n🕒 [1/3] 同步港股报表 (HK)...")
        subprocess.run([sys.executable, "fetch_financials.py", "--market", "HK"], check=True)
        
        print("\n💤 休息 5 分钟避开 Yahoo 限流...")
        import time
        for i in range(5, 0, -1):
            print(f"   剩余 {i} 分钟...", end="\r")
            time.sleep(60)
            
        # 2. US Market
        print("\n🕒 [2/3] 同步美股报表 (US)...")
        subprocess.run([sys.executable, "fetch_financials.py", "--market", "US"], check=True)
        
        # 3. CN Market
        print("\n🕒 [3/3] 同步 A 股报表 (CN)...")
        subprocess.run([sys.executable, "fetch_financials.py", "--market", "CN"], check=True)
        
        # 4. Repair & Recalc
        print("\n🛠️ [4/4] 执行 EPS 专项修复与 PE 全量重算...")
        subprocess.run([sys.executable, "scripts/fetch_missing_financials.py", "--market", "ALL"], check=True)
        subprocess.run([sys.executable, "scripts/recalc_historical_pe.py", "--market", "ALL"], check=True)
        
        print("\n✅ 全量补全任务成功完成！")
    except Exception as e:
        print(f"\n❌ 执行过程中出错: {e}")

def main():
    """主函数"""
    print_header("数据管理工具")
    print(f"执行时间: {datetime.now()}")
    
    # 显示菜单
    print_section("操作选项")
    print("""
请选择要执行的操作 (单选/多选):

  1) 清除行情数据 (rawmarketdata, marketdatadaily, marketsnapshot)
  2) 清除财务数据 (financialfundamentals, dividendfact, splitfact)
  3) 清除监控列表 (watchlist) [⚠️ 全部清空]
  4) 从 symbols.txt 重新导入 [⚠️ 清空后导入]
  
  5) 同步监控列表 (Smart Sync) [🔍 推荐: 增量添加/安全移除]
  6) 全量财务补全与估值重算 (Full Backfill & Repair) [🛠️ 修复空值/重算 PE]
  
  0) 退出

示例: "1" 或 "5"
    """)
    
    # 获取用户输入
    choice = input("请输入选项 (空格分隔): ").strip()
    
    if not choice or choice == '0':
        print("\n👋 退出")
        return
    
    options = choice.split()
    
    for opt in options:
        if opt == '1':
            clear_market_data()
        elif opt == '2':
            clear_financial_data()
        elif opt == '3':
            clear_watchlist()
        elif opt == '4':
            import_symbols()
        elif opt == '5':
            sync_symbols()
        elif opt == '6':
            run_full_backfill()
        else:
            print(f"\n⚠️  无效选项: {opt}")
    
    show_current_status()
    print_header("操作完成")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

