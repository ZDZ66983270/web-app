#!/usr/bin/env python3
"""
Unified Data Downloader (统一行情/财报下载器)
==============================================================================

功能说明:
1. **全资产支持**: 统一处理 Stock, Index, ETF, Crypto, Fund 等所有资产类型。
2. **多模式并行**: 支持下载 历史行情 (OHLCV) 和 财务报表 (Financials)。
3. **架构模式**: 采用 **ELT (Extract-Load-Transform)** 模式。
   - 本脚本仅负责 **Extract (下载)** 和 **Load (存入 Raw 表)**。
   - **Transform (清洗/入库)** 必须由下游 ETL 脚本 (`process_raw_data_optimized.py`) 完成。

核心逻辑架构:

I. Historical Market Data (历史行情)
------------------------------------------------------------------------------
- **主数据源**: **Yahoo Finance** (`yfinance`).
  - 覆盖 CN (A股), HK (港股), US (美股), Crypto (加密货币)。
- **备选策略 (Fallback)**:
  - **Index (指数)**: 当 Yahoo 缺失关键指数 (如 HSTECH, CSI300) 时，自动切换至 AkShare。
  - **CN ETF (A股ETF)**: 
    - 场景1: Yahoo 返回为空。
    - 场景2 (Data Depth Integrity): 请求 `max` 全量数据时，若 Yahoo 返回少于 1 年 (252天) 数据，视为不完整，自动触发 AkShare 全量下载并保留更长的数据集。
- **智能增量 (Smart Incremental)**:
  - 算法: `calculate_period`
  - 逻辑: 检查 `MarketDataDaily` 中该资产的最后日期。
    - Gap <= 0: Skip (跳过)
    - Gap < 4: Download `5d`
    - Gap < 28: Download `1mo`
    - Gap < 350: Download `1y`
    - Else: Download `max` (全量)

II. Financial Reports (财务报表) - Optional
------------------------------------------------------------------------------
- 若启用 `Financials` 选项，将调用 `fetch_financials.py` 模块。
- **策略**:
  - CN: AkShare (Abstract)
  - HK: AkShare (Annual) + Yahoo (Quarterly)
  - US: Yahoo (Annual/Quarterly) + FMP (if configured downstream)

III. Execution Flow (执行流)
------------------------------------------------------------------------------
1. **Config**: 交互式菜单或命令行参数 (`--auto`) 确定下载范围。
2. **Filter**: 基于内存中的 `Watchlist` 快照过滤目标资产。
3. **Fetch & Save**:
   - 下载数据 -> 转换为 JSON -> 存入 `RawMarketData` 表 (Status: `processed=False`)。
4. **Next Step**: 用户需运行 ETL 脚本处理 Raw 数据。

IV. Internal Module Structure (内部代码结构)
------------------------------------------------------------------------------
本脚本代码量约 450 行，分为以下四大模块：

1. **Helper Functions (基础工具)**:
   - `get_last_sync_date`: 查询 DB 获取最后同步时间。
   - `calculate_period`: **核心算法**。根据 (Now - LastSync) 的天数差，动态计算 Yahoo 下载窗口 (`5d`/`1mo`/`1y`/`max`)，实现流量最小化。
   - `save_to_raw`: 封装 JSON 转换逻辑，写入 `RawMarketData` 表。
   - `fallback_index_akshare`: 封装 AkShare 指数获取逻辑，对外提供统一接口。

2. **Core Download Logic (下载业务逻辑)**:
   - `download_history_single`: 行情下载入口。组合 Yahoo API + AkShare Fallback + Error Handling。
   - `download_financials_single`: 财报下载入口。作为调度器 (Dispatcher)，将任务分发给 `fetch_financials.py` 中的具体实现。

3. **Interactive CLI (交互界面)**:
   - `Config` 类: 维护用户选择的状态 (Selected Markets/Types/Actions)。
   - `print_menu`: 绘制包含复选框状态 (`[x]`) 的动态终端 UI。
   - `configure`: 处理键盘输入和状态切换逻辑。

4. **Main Execution (主流程)**:
   - 支持 `--auto` 命令行参数 (Headless 模式)。
   - 基于内存 `In-Memory Filter` 筛选 Watchlist。
   - 执行下载循环，包含进度打印和 `sleep` 限流。

V. Dependencies
------------------------------------------------------------------------------
- `backend.models`: RawMarketData, Watchlist
- `backend.symbol_utils`: Canonical ID 解析与转换
- `fetch_financials.py`: (Optional) 外部财报获取模块

作者: Antigravity
日期: 2026-01-23
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
import pandas as pd
import yfinance as yf
import akshare as ak

# Ensure backend and current dir are in path
sys.path.append('backend')
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from sqlmodel import Session, select
from backend.database import engine
from backend.models import Watchlist, RawMarketData, FinancialFundamentals
from backend.symbol_utils import get_yahoo_symbol, parse_canonical_id
from backend.index_config import get_yfinance_symbol as get_index_yf_symbol

# --- Import Financials Logic ---
try:
    from fetch_financials import (
        fetch_yahoo_financials, 
        fetch_akshare_cn_financials_abstract,
        fetch_akshare_hk_financials,
        upsert_financials
    )
    FINANCIALS_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: fetch_financials.py not found. Financials feature disabled.")
    FINANCIALS_AVAILABLE = False

# ==============================================================================
# Helper Functions (Preserved & Adapted)
# ==============================================================================

def get_last_sync_date(symbol: str) -> datetime.date:
    """Check MarketDataDaily for the latest data date"""
    from backend.models import MarketDataDaily
    with Session(engine) as session:
        statement = select(MarketDataDaily.timestamp).where(
            MarketDataDaily.symbol == symbol
        ).order_by(MarketDataDaily.timestamp.desc()).limit(1)
        res = session.exec(statement).first()
        if res:
            # res is a string or date depending on model. Model says str?
            # Let's parse safely.
            if isinstance(res, str):
                return pd.to_datetime(res).date()
            if isinstance(res, datetime):
                return res.date()
            return res # date
    return None

def calculate_period(last_date: datetime.date) -> str:
    """
    Calculate optimal Yahoo period based on gap.
    Gap <= 0 -> 'skip'
    Gap < 4 -> '5d'
    Gap < 28 -> '1mo'
    Gap < 85 -> '3mo'
    Gap < 350 -> '1y'
    Else -> 'max'
    """
    if not last_date:
        return 'max'
        
    gap = (datetime.now().date() - last_date).days
    
    if gap <= 0: return 'skip'
    if gap <= 4: return '5d'
    if gap <= 28: return '1mo'
    if gap <= 85: return '3mo'
    if gap <= 350: return '1y'
    return 'max'

def convert_to_yfinance_symbol(symbol: str, market: str, asset_type: str = 'STOCK') -> str:
    """转换为yfinance格式"""
    from backend.symbol_utils import get_yahoo_symbol
    s = symbol.strip().upper()
    
    # 1. Index Config
    yf_symbol = get_index_yf_symbol(s, market)
    if yf_symbol != s:
        return yf_symbol
    
    # 2. General logic
    return get_yahoo_symbol(s, market, asset_type)

def save_to_raw(canonical_id: str, market: str, df: pd.DataFrame, source: str = "yfinance") -> int:
    """保存原始数据到 RawMarketData"""
    if df is None or df.empty: return 0
    
    # Format
    df_reset = df.reset_index()
    rename_map = {
        'Date': 'timestamp', 'Datetime': 'timestamp',
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
    }
    df_reset = df_reset.rename(columns=rename_map)
    
    if 'timestamp' in df_reset.columns:
        df_reset['timestamp'] = pd.to_datetime(df_reset['timestamp']).dt.strftime('%Y-%m-%d')
    records = df_reset.to_dict(orient='records')
    
    # Payload
    payload = {
        "symbol": canonical_id,
        "market": market,
        "source": source,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": records
    }
    
    try:
        from backend.models import RawMarketData
        with Session(engine) as session:
            record = RawMarketData(
                symbol=canonical_id, market=market, source=source,
                period="1d", fetch_time=datetime.now(),
                payload=json.dumps(payload), processed=False
            )
            session.add(record)
            session.commit()
            return len(records)
    except Exception as e:
        print(f"      ❌ 保存失败: {e}")
        return 0

def fallback_index_akshare(canonical_id, market, symbol, source_type):
    """AkShare Fallback for Indices"""
    print(f"⚠️  尝试 AkShare 补全 {canonical_id} 数据 ({source_type})...")
    try:
        df = None
        if source_type == "hk_index_sina":
            df = ak.stock_hk_index_daily_sina(symbol=symbol)
        elif source_type == "cn_index":
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            
        if df is not None and not df.empty:
            rename_map = {
                'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
                '日期': 'Date', '开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
            }
            df = df.rename(columns=rename_map)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            print(f"✅ AkShare 获取 {len(df)} 条记录")
            return save_to_raw(canonical_id, market, df, source="akshare")
    except Exception as e:
        print(f"      ❌ AkShare 补全失败: {e}")
    return 0

def fallback_etf_akshare(canonical_id, market, code, source_type):
    """AkShare Fallback for ETFs (CN)"""
    print(f"⚠️  尝试 AkShare 补全 {canonical_id} 数据 ({source_type})...")
    try:
        # Determine prefix for AkShare (sh/sz)
        # 51xxxx -> sh, 58xxxx -> sh, 15xxxx -> sz
        prefix = "sh"
        if code.startswith('15') or code.startswith('16'):
            prefix = "sz"
        elif code.startswith('5'):
            prefix = "sh"
        
        symbol = f"{prefix}{code}"
        
        df = ak.fund_etf_hist_sina(symbol=symbol)
            
        if df is not None and not df.empty:
            # AkShare ETF: date, open, high, low, close, volume
            rename_map = {
                'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            }
            df = df.rename(columns=rename_map)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            print(f"✅ AkShare 获取 {len(df)} 条记录")
            return save_to_raw(canonical_id, market, df, source="akshare")
    except Exception as e:
        print(f"      ❌ AkShare 补全失败: {e}")
    return 0

# ==============================================================================
# Core Download Logic
# ==============================================================================

def download_history_single(canonical_id: str, code: str, market: str, asset_type: str = 'STOCK', force_full: bool = False):
    """下载单个资产的历史行情"""
    yf_symbol = convert_to_yfinance_symbol(code, market, asset_type)
    
    # --- Incremental Logic ---
    period = "max"
    if not force_full:
        last_date = get_last_sync_date(canonical_id)
        period = calculate_period(last_date)
        
    if period == 'skip':
        print(f"   ⏩ [History] {yf_symbol} is up-to-date ({last_date}).")
        return 0
    else:
        print(f"   📉 [History] Fetching {yf_symbol} ({period})...")
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, auto_adjust=True)
        
        if df.empty:
            # Fallbacks
            if market == 'HK' and code == 'HSTECH':
                return fallback_index_akshare(canonical_id, market, "HSTECH", "hk_index_sina")
            elif market == 'CN' and asset_type == 'INDEX':
                ak_map = {"000001": "sh000001", "000300": "sh000300", "000016": "sh000016", "000905": "sh000905"}
                ak_symbol = ak_map.get(code)
                if ak_symbol: return fallback_index_akshare(canonical_id, market, ak_symbol, "cn_index")
            elif market == 'CN' and asset_type == 'ETF':
                 # Fallback for CN ETFs (e.g. 512800 -> sh512800)
                 return fallback_etf_akshare(canonical_id, market, code, "cn_etf")
            print(f"      ⚠️  无数据")
            return 0
        
        # New Logic: Check for Suspiciously Short Data (Yahoo Quirk)
        # If we asked for 'max' but got less than 1 year (approx 252 days) for a CN ETF
        if market == 'CN' and asset_type == 'ETF' and period == 'max' and len(df) < 252:
            print(f"      ⚠️  Yahoo data suspicious ({len(df)} rows < 1 year). Attempting fallback...")
            ak_res = fallback_etf_akshare(canonical_id, market, code, "cn_etf_depth_check")
            if ak_res > len(df):
                print(f"      ✅ Fallback superior: AkShare ({ak_res}) > Yahoo ({len(df)}). Using Fallback.")
                return ak_res
            else:
                print(f"      ℹ️  Fallback result ({ak_res}) not better than Yahoo. Reverting to Yahoo data.")

        count = save_to_raw(canonical_id, market, df, source="yfinance")
        if count > 0:
            return count
        
    except Exception as e:
        print(f"      ❌ 异常: {e}")
        return 0

def download_financials_single(canonical_id: str, code: str, market: str, asset_type: str):
    """下载单个资产的财务数据"""
    if asset_type in ['INDEX', 'ETF', 'CRYPTO', 'FUND']:
        print(f"   💰 [Financials] 跳过 (不支持的类型: {asset_type})")
        return 0
        
    print(f"   💰 [Financials] Fetching {canonical_id}...")
    data_list = []
    
    try:
        # Reuse logic from fetch_financials.py
        if market == 'CN':
            # AkShare Abstract
             data_list.extend(fetch_akshare_cn_financials_abstract(canonical_id))
        elif market == 'HK':
             # 1. AkShare Annual
             try:
                 code_raw = canonical_id.split(':')[-1]
                 # Get currency hint
                 yf_sym = get_yahoo_symbol(code_raw, 'HK')
                 yf_t = yf.Ticker(yf_sym)
                 cur = yf_t.info.get('financialCurrency') or 'HKD'
             except: cur = 'HKD'
             
             data_list.extend(fetch_akshare_hk_financials(canonical_id, preferred_currency=cur))
             # 2. AkShare Details
             data_list.extend(fetch_akshare_hk_financials_details(canonical_id))
             # 3. Yahoo Quarterly
             data_list.extend(fetch_yahoo_financials(canonical_id, market='HK', report_type='quarterly'))
             # 4. Yahoo Annual
             data_list.extend(fetch_yahoo_financials(canonical_id, market='HK', report_type='annual'))
             
        elif market == 'US':
             data_list.extend(fetch_yahoo_financials(canonical_id, market='US', report_type='annual'))
             data_list.extend(fetch_yahoo_financials(canonical_id, market='US', report_type='quarterly'))
             
        # Save
        if data_list:
             data_list.sort(key=lambda x: x['as_of_date'], reverse=True)
             with Session(engine) as session:
                 for d in data_list:
                     upsert_financials(session, d)
                 session.commit()
             print(f"      ✅ 已保存 {len(data_list)} 条财报记录")
             return len(data_list)
        else:
             print("      ℹ️  无财报数据")
             return 0
             
    except Exception as e:
        print(f"      ❌ 财报异常: {e}")
        return 0

# ==============================================================================
# Interactive CLI
# ==============================================================================

class Config:
    def __init__(self):
        self.markets = {'CN', 'HK', 'US'}
        self.types = {'STOCK', 'INDEX', 'ETF', 'CRYPTO', 'TRUST', 'FUND'}
        self.actions = {'History', 'Financials'}
        
        # Selection State
        self.selected_markets = self.markets.copy()
        self.selected_types = self.types.copy()
        self.selected_actions = {'History'}
        self.force_full = False # NEW

def clear_screen():
    print("\033[H\033[J", end="")

def print_menu(cfg: Config):
    clear_screen()
    print("="*60)
    print(" 📥 统一数据下载器 (Interactive) - 快捷菜单")
    print("="*60)
    
    def status(condition):
        return "✅" if condition else "❌"
    
    # 扁平化展示
    print(f" [1] {status('CN' in cfg.selected_markets)} CN      [4] {status('STOCK' in cfg.selected_types)} Stock      [8] {status('History' in cfg.selected_actions)} History")
    print(f" [2] {status('HK' in cfg.selected_markets)} HK      [5] {status('INDEX' in cfg.selected_types)} Index      [9] {status('Financials' in cfg.selected_actions)} Financials")
    print(f" [3] {status('US' in cfg.selected_markets)} US      [6] {status('ETF' in cfg.selected_types)} ETF")
    print(f"                [7] {status('CRYPTO' in cfg.selected_types)} Crypto     [F] {status(cfg.force_full)} Force Full")
    print(f"                [T] {status('TRUST' in cfg.selected_types)} Trust")
    
    print("-" * 60)
    print(" [0] ▶️  开始下载     [A] 全选     [C] 清空")
    print(" [Q] 退出")
    print("="*60)

def configure():
    cfg = Config()
    
    # Mapping keys to toggle actions
    toggles = {
        '1': lambda: toggle(cfg.selected_markets, 'CN'),
        '2': lambda: toggle(cfg.selected_markets, 'HK'),
        '3': lambda: toggle(cfg.selected_markets, 'US'),
        '4': lambda: toggle(cfg.selected_types, 'STOCK'),
        '5': lambda: toggle(cfg.selected_types, 'INDEX'),
        '6': lambda: toggle(cfg.selected_types, 'ETF'),
        '7': lambda: toggle(cfg.selected_types, 'CRYPTO'),
        'T': lambda: toggle(cfg.selected_types, 'TRUST'),
        '8': lambda: toggle(cfg.selected_actions, 'History'),
        '9': lambda: toggle(cfg.selected_actions, 'Financials'),
        'F': lambda: toggle_bool(cfg, 'force_full')
    }
    
    while True:
        print_menu(cfg)
        try:
            choice = input(" 请输入选项 [0-9/A/C/F]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            sys.exit(0)
            
        if choice == '0':
            return cfg
        elif choice == 'Q':
            sys.exit(0)
        elif choice in toggles:
            toggles[choice]()
        elif choice == 'A':
            cfg.selected_markets = cfg.markets.copy()
            cfg.selected_types = cfg.types.copy()
            cfg.selected_actions = {'History', 'Financials'}
        elif choice == 'C':
            cfg.selected_markets.clear()
            cfg.selected_types.clear()
            # Keep one action to be safe? or allow clear
            cfg.selected_actions.clear()
            
def toggle(selection_set, item):
    if item in selection_set:
        selection_set.remove(item)
    else:
        selection_set.add(item)

def toggle_bool(obj, attr):
    setattr(obj, attr, not getattr(obj, attr))

# ==============================================================================
# Main
# ==============================================================================

def main():
    import sys
    
    # 1. Configuration
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("🤖 Auto Mode Detected (Command Line Argument). Selecting Default Set.")
        cfg = Config()
        # Default: CN,HK,US; Stock,Index,ETF,Crypto,Trust; History Only
        cfg.selected_markets = {'CN', 'HK', 'US'}
        cfg.selected_types = {'STOCK', 'INDEX', 'ETF', 'CRYPTO', 'TRUST'}
        cfg.selected_actions = {'History'} # Default to History, Financials handled by separate step
    else:
        try:
            cfg = configure()
        except KeyboardInterrupt:
            print("\nExit")
            return


    print("\n准备开始...")
    print(f"市场: {cfg.selected_markets}")
    print(f"类型: {cfg.selected_types}")
    print(f"内容: {cfg.selected_actions}")
    
    # 2. Load Watchlist
    with Session(engine) as session:
        watchlist = session.exec(select(Watchlist)).all()
        
    # 3. Filter Targets (In Memory)
    targets = []
    print("\n🔍 正在筛选资产列表 (In-Memory Filter)...")
    
    for item in watchlist:
        # Parse info
        parts = parse_canonical_id(item.symbol)
        asset_type = parts['type']
        
        # Filter Logic
        if item.market not in cfg.selected_markets:
            if not (item.market == 'WORLD' and 'CRYPTO' in cfg.selected_actions): # Special handling for WORLD/CRYPTO?
                # Usually Crypto is WORLD market.
                if not (item.market == 'WORLD' and 'WORLD' in cfg.selected_markets):
                     continue
        
        if asset_type not in cfg.selected_types:
            continue
            
        targets.append({
            "symbol": item.symbol,
            "market": item.market,
            "type": asset_type,
            "name": item.name or item.symbol,
            "code": parts['symbol']
        })

    total = len(targets)
    if total == 0:
        print("⚠️  在此筛选条件下未找到任何资产。")
        return

    print(f"✅ 筛选出 {total} 个目标资产。")
    time.sleep(1)
    
    # 4. Execution Loop
    success_hist = 0
    success_fin = 0
    
    for idx, item in enumerate(targets, 1):
        print(f"\n[{idx}/{total}] {item['symbol']} ({item['name']})")
        
        # Action: History
        if 'History' in cfg.selected_actions:
            res = download_history_single(item['symbol'], item['code'], item['market'], item['type'], force_full=cfg.force_full)
            if res > 0: success_hist += 1
            time.sleep(0.5)
            
        # Action: Financials
        if 'Financials' in cfg.selected_actions:
            if not FINANCIALS_AVAILABLE:
                print("   💰 [Financials] 跳过 (功能不可用)")
            else:
                res = download_financials_single(item['symbol'], item['code'], item['market'], item['type'])
                if res > 0: success_fin += 1
            time.sleep(0.5)

    print("\n" + "="*80)
    print("🏁 下载完成")
    print("="*80)
    if 'History' in cfg.selected_actions:
        print(f"行情下载成功: {success_hist} 个")
    if 'Financials' in cfg.selected_actions:
        print(f"财报下载成功: {success_fin} 个")
    print("="*80)
    print("💡 下一步建议: 运行 ETl")
    print("   python3 process_raw_data_optimized.py")

if __name__ == "__main__":
    main()
