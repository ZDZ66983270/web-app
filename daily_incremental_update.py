"""
Daily Incremental Update Script (每日增量更新脚本)
===============================================

功能说明:
1. 自动化执行每日行情下载流程：获取资产列表 -> 下载行情数据 -> 存入 Raw 表。
2. 采用 yfinance Unified 策略，统一处理美股 (US)、港股 (HK) 和 A 股 (CN) 的行情下载。
3. 集成 AkShare 回退机制：针对 yfinance 缺失的国内指数和 ETF 自动切换备选源。
4. 实现“智能跳过”逻辑：如果今日数据已存在且为最新，则不重复下载。

核心逻辑与流程:
1. **符号转换 (Symbol Normalization)**:
   - 剥离 Canonical ID 前缀并应用市场规则补全后缀。
2. **下载策略与回退**:
   - 下载过去 5 天日线数据。
   - 若 yfinance 失效，针对 CN 指数/ETF 自动触发 AkShare 回退。
3. **数据暂存 (ELT - Extract & Load)**:
   - 数据以 JSON 格式存入 `RawMarketData` 表，等待后续独立 ETL 脚本处理。

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
from sqlmodel import Session, select

# 添加后端路径以导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import engine
from models import Watchlist, RawMarketData

# ==========================================
# 0. Result Tracker
# ==========================================
class ResultTracker:
    def __init__(self):
        self.results = []
        
    def add(self, symbol, market, status, message=""):
        self.results.append({
            "symbol": symbol,
            "market": market,
            "status": status,
            "message": message,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        
    def print_summary(self):
        print("\n" + "="*80)
        print(f"📊 每日更新详细报告 (Daily Update Report) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Group by Market
        by_market = {}
        for r in self.results:
            m = r['market'] or 'UNKNOWN'
            if m not in by_market: by_market[m] = {'ok': 0, 'fail': 0, 'skip': 0, 'details': []}
            
            if r['status'] == 'SUCCESS': by_market[m]['ok'] += 1
            elif r['status'] == 'FAILED': by_market[m]['fail'] += 1
            else: by_market[m]['skip'] += 1
            
            by_market[m]['details'].append(r)
            
        # Print Table Header
        print(f"{'Market':<8} | {'Symbol':<18} | {'Status':<10} | {'Message'}")
        print("-" * 80)
        
        total_ok, total_fail = 0, 0
        
        for market in sorted(by_market.keys()):
            stats = by_market[market]
            total_ok += stats['ok']
            total_fail += stats['fail']
            
            # Print details (Failed first, then Success)
            sorted_details = sorted(stats['details'], key=lambda x: (x['status'] == 'SUCCESS', x['symbol']))
            
            for item in sorted_details:
                # Colorize status
                status_str = item['status']
                if status_str == 'SUCCESS': status_icon = "✅ OK"
                elif status_str == 'FAILED': status_icon = "❌ FAIL"
                else: status_icon = "⏭️ SKIP"
                
                # Truncate message
                msg = item['message'][:40] + "..." if len(item['message']) > 40 else item['message']
                print(f"{market:<8} | {item['symbol']:<18} | {status_icon:<10} | {msg}")
            
            # Market Summary Line
            print(f"   >>> {market} Summary: ✅ {stats['ok']}  ❌ {stats['fail']}  ⏭️ {stats['skip']}")
            print("-" * 80)
            
        print("="*80)
        print(f"🏁 总计: 成功 {total_ok}  失败 {total_fail}")
        print("="*80)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DailyUpdate")

# ==========================================
# 1. 辅助函数
# ==========================================

def get_all_symbols_for_update():
    """
    获取所有需要更新的股票和指数（Watchlist + Index表）
    
    Returns:
        list of tuples: [(symbol, market), ...]
    """
    sys.path.insert(0, 'backend')
    from symbol_utils import get_all_symbols_to_update
    
    with Session(engine) as session:
        all_items = get_all_symbols_to_update(session)
    
    # 返回去重的 (symbol, market) 元组列表
    return list(set([(item['symbol'], item['market']) for item in all_items]))

from symbols_config import get_yfinance_symbol as get_yf_sym_config, get_canonical_symbol

def get_yfinance_symbol(symbol: str, market: str) -> str:
    """
    将内部 symbol 标准化为 yfinance 认可的 Ticker 格式
    优先使用 symbols_config.py 中的配置，其次使用通用规则
    """
    symbol = symbol.strip().upper()
    
    # 0. Strip Canonical ID prefix if present
    if ":" in symbol:
        symbol = symbol.split(":")[-1]
    
    # 1. 规范化别名 (e.g. 800700 -> HSTECH)
    canonical = get_canonical_symbol(symbol)
    
    # 2. 尝试从配置获取
    # config 返回的可能是本身(若无配置)，所以我们需要区分"有配置"和"默认"
    # 但 get_yfinance_symbol 实现是 config.get('yfinance_symbol', symbol)
    # 我们可以直接调用，如果它是指数，通常会有配置。
    config_yf = get_yf_sym_config(canonical)
    
    # 如果 config 返回的不等于 canonical，说明找到了特定配置 (或者就是 symbol 本身但我们确认一下)
    # 对于指数，如 ^DJI -> ^DJI, 000001.SS -> 000001.SS
    # 只有当它是配置表里的 Key 时，我们才信任它。
    # 如何判断是否在配置表？ get_yf_sym_config 内部是 dict.get
    # 简单策略：先查 Config。
    
    # 我们需要更明确的逻辑：如果是"已知指数/特殊品种" -> Use Config.
    # 如果是"普通个股" -> Use Generic Rule.
    
    # Hack: 检查 get_yf_sym_config 是否改变了 symbol，或者 symbol 是否在 symbols_config 的 Keys 里?
    # 由于不能直接访问 config dict，我们假设:
    # 如果 canonical 是指数 (含 .SS/.SZ 等)，config 应该能通过。
    
    if config_yf != canonical:
        # 发生了映射 (e.g. 800000 -> ^HSI, or Config has explicit definition)
        return config_yf
        
    # 特殊情况: 000001.SS 在 Config 里， get_yf_sym_config("000001.SS") returns "000001.SS"
    # 这时 config_yf == canonical，但它确实是 Config 管理的。
    # 为了避免 generic rules 误判 (虽然后面 generic 也会处理 .SS)
    # 我们可以稍微依赖 canonical 的格式.
    
    # 3. yfinance specific fix for SH
    if canonical.endswith(".SH"):
        return canonical.replace(".SH", ".SS")

    # 4. 通用规则 (Generic Stocks)
    # 如果已经包含后缀 (e.g. .HK, .SS, .SZ) -> 直接使用
    if "." in canonical:
        # Special handling for HK stocks (e.g. 09988.HK -> 9988.HK) - Yahoo prefers 4 digits
        if market == 'HK' and canonical.endswith('.HK'):
             code = canonical.split('.')[0]
             if code.isdigit():
                 return f"{int(code):04d}.HK"
        return canonical

    # 5. 根据市场规则补全
    if market == "US":
        return canonical
        
    elif market == "HK":
        if canonical.isdigit():
            return f"{int(canonical):04d}.HK"
        # 可能是未在 Config 中的指数?
        if canonical == "HSI": return "^HSI"
        if canonical == "HSTECH": return "^HSTECH"
        return f"{canonical}.HK"
        
    elif market == "CN":
        # A股规则
        if canonical.startswith("6") or canonical.startswith("5"):
            return f"{canonical}.SS"
        elif canonical.startswith("0") or canonical.startswith("3") or canonical.startswith("1"):
            return f"{canonical}.SZ"
        elif canonical.startswith("4") or canonical.startswith("8"):
            return f"{canonical}.BJ"
            
    return canonical

from models import MarketDataDaily

def get_last_sync_date(symbol: str) -> datetime.date:
    """Check MarketDataDaily for the latest data date"""
    with Session(engine) as session:
        statement = select(MarketDataDaily.timestamp).where(
            MarketDataDaily.symbol == symbol
        ).order_by(MarketDataDaily.timestamp.desc()).limit(1)
        res = session.exec(statement).first()
        if res:
            if isinstance(res, str):
                return pd.to_datetime(res).date()
            if isinstance(res, datetime):
                return res.date()
            return res
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

def fallback_index_akshare(canonical_id, market, symbol, source_type):
    """AkShare Fallback for Indices (从 download_full_history.py 移植)"""
    logger.info(f"⚠️ 尝试 AkShare 补全 {canonical_id} 数据 ({source_type})...")
    try:
        df = None
        if source_type == "hk_index_sina":
            df = ak.stock_hk_index_daily_sina(symbol=symbol)
        elif source_type == "cn_index":
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            
        if df is not None and not df.empty:
            rename_map = {
                'date': 'timestamp', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume',
                '日期': 'timestamp', '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close', '成交量': 'volume'
            }
            df = df.rename(columns=rename_map)
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d')
            
            records = df.to_dict(orient='records')
            payload = {
                "symbol": canonical_id,
                "market": market,
                "source": "akshare",
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": records
            }
            return save_payload_to_db(canonical_id, market, "akshare", payload)
    except Exception as e:
        logger.error(f"❌ AkShare 补全失败: {e}")
    return None

def fallback_etf_akshare(canonical_id, market, code):
    """AkShare Fallback for ETFs (CN) (从 download_full_history.py 移植)"""
    logger.info(f"⚠️ 尝试 AkShare 补全 {canonical_id} 数据...")
    try:
        prefix = "sz" if code.startswith(('15', '16')) else "sh"
        symbol = f"{prefix}{code}"
        df = ak.fund_etf_hist_sina(symbol=symbol)
            
        if df is not None and not df.empty:
            rename_map = {'date': 'timestamp', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'}
            df = df.rename(columns=rename_map)
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d')
            
            records = df.to_dict(orient='records')
            payload = {
                "symbol": canonical_id,
                "market": market,
                "source": "akshare",
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": records
            }
            return save_payload_to_db(canonical_id, market, "akshare", payload)
    except Exception as e:
        logger.error(f"❌ AkShare 补全失败: {e}")
    return None

def fetch_and_save_unified(symbol: str, market: str, force_full: bool = False) -> tuple[bool, str]:
    """
    统一获取逻辑：
    Returns: (Success, Message)
    """
    yf_symbol = get_yfinance_symbol(symbol, market)
    last_date = get_last_sync_date(symbol)
    
    if force_full:
        period = "max"
    else:
        period = calculate_period(last_date)
    
    if period == 'skip':
        return True, f"Skipped (Up-to-date: {last_date})"

    logger.info(f"🔄 Fetching [{market}] {symbol} -> yf: {yf_symbol} (Period: {period})")
    
    try:
        # 下载数据，包含auto_adjust=True
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval="1d", auto_adjust=True)
        
        if df.empty:
            logger.warning(f"⚠️ No data found for {yf_symbol} (yfinance)")
            
            # --- AkShare Fallback Logic ---
            from backend.symbol_utils import parse_canonical_id
            parts = parse_canonical_id(symbol)
            code = parts.get('symbol')
            asset_type = parts.get('type')

            if market == 'HK' and code == 'HSTECH':
                record_id = fallback_index_akshare(symbol, market, "HSTECH", "hk_index_sina")
            elif market == 'CN' and asset_type == 'INDEX':
                ak_map = {"000001": "sh000001", "000300": "sh000300", "000016": "sh000016", "000905": "sh000905"}
                ak_symbol = ak_map.get(code)
                if ak_symbol: record_id = fallback_index_akshare(symbol, market, ak_symbol, "cn_index")
                else: record_id = None
            elif market == 'CN' and asset_type == 'ETF':
                record_id = fallback_etf_akshare(symbol, market, code)
            else:
                record_id = None
            
            if record_id:
                return True, f"Saved via AkShare Fallback (ID: {record_id})"
                
            return False, f"No data found (yf: {yf_symbol}, fallback: None)"
            
        # 格式化数据
        df = df.reset_index()
        
        # 统一列名
        rename_map = {
            'Date': 'timestamp',
            'Datetime': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        df = df.rename(columns=rename_map)
        
        # 处理时间戳
        if 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        elif 'date' in df.columns: # Fallback
            df['timestamp'] = df['date'].dt.strftime('%Y-%m-%d')
            
        # 🛡️ SANITY CHECK
        if symbol == "000001.SS":
            last_close = df['close'].iloc[-1]
            if last_close < 1000:
                logger.error(f"❌ SANITY CHECK FAILED for {symbol}: Price {last_close} is too low for Index. Likely fetched Ping An Bank. Skipping.")
                return False, f"Sanity Check Failed (Low Price: {last_close})"
                
        # 转为 list of dicts
        records = df.to_dict(orient='records')
        
        # 构造 Payload
        payload = {
            "symbol": symbol,
            "market": market,
            "source": "yfinance",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": records
        }
        
        # 存库 (返回 ID)
        record_id = save_payload_to_db(symbol, market, "yfinance", payload, period="1d")
        
        if record_id:
            return True, f"Saved Raw ID {record_id}"
        else:
            return False, "DB Save Failed"
        
    except Exception as e:
        logger.error(f"❌ Error fetching {symbol}: {str(e)}")
        return False, str(e)

def save_payload_to_db(symbol: str, market: str, source: str, payload: dict, period: str = '1d') -> int:
    """保存 Payload 到数据库, 返回记录 ID (None if failed)"""
    try:
        payload_json = json.dumps(payload)
        with Session(engine) as session:
            record = RawMarketData(
                symbol=symbol,
                market=market,
                source=source,
                period=period,
                fetch_time=datetime.now(),
                payload=payload_json,
                processed=False
            )
            session.add(record)
            session.commit()
            logger.info(f"✅ Saved {symbol} to RawMarketData (ID: {record.id})")
            # Must refresh to get ID if not immediately available on object? 
            # Session commit usually populates it.
            session.refresh(record)
            return record.id
    except Exception as e:
        logger.error(f"❌ Database error for {symbol}: {e}")
        return None

# ==========================================
# 3. 主执行流
# ==========================================

def run_daily_update(target_market=None, target_symbol=None, target_types=None, force_full=False):
    logger.info(f"🚀 Starting Daily Incremental Update (yfinance Unified)")
    logger.info(f"   Filter -> Market: {target_market or 'ALL'}, Symbol: {target_symbol or 'ALL'}, Types: {target_types or 'ALL'}, ForceFull: {force_full}")
    
    # 获取所有需要更新的股票和指数
    all_targets = get_all_symbols_for_update()
    
    # 辅助：获取资产类型支持从 symbol 解析
    from backend.symbol_utils import parse_canonical_id
    
    # 应用过滤逻辑
    targets = []
    for symbol, market in all_targets:
        # A. 符号过滤
        if target_symbol and symbol != target_symbol:
            continue
            
        # B. 市场过滤
        if target_market and target_market != 'ALL':
            if isinstance(target_market, list):
                if market not in target_market: continue
            elif market != target_market:
                continue
        
        # C. 类型过滤
        if target_types and target_types != 'ALL':
            try:
                asset_type = parse_canonical_id(symbol)['type']
                if isinstance(target_types, list):
                    if asset_type not in target_types: continue
                elif asset_type != target_types:
                    continue
            except: pass # 容错
            
        targets.append((symbol, market))
            
    logger.info(f"📋 Total targets to process: {len(targets)}")
    
    tracker = ResultTracker()
    success_count = 0
    fail_count = 0
    
    # 3. 遍历执行
    for symbol, market in targets:
        success, msg = fetch_and_save_unified(symbol, market, force_full=force_full)
        if success:
            success_count += 1
            tracker.add(symbol, market, "SUCCESS", msg)
        else:
            fail_count += 1
            tracker.add(symbol, market, "FAILED", msg)
            
        time.sleep(1.0) # 礼貌性延迟
        
    logger.info("-" * 40)
    logger.info(f"🏁 Update Finished: Success={success_count}, Failed={fail_count}")
    logger.info("-" * 40)
    
    # 4. Final Summary (Moved to end for visibility)
    tracker.print_summary()
    
    print("\n💡 下一步建议: 运行 ETL 脚本以处理下载的原始数据")
    print("   python3 process_raw_data_optimized.py")
    print("="*80 + "\n")

# ==========================================
# 4. Interactive CLI (Advanced)
# ==========================================

class Config:
    def __init__(self):
        self.markets = {'CN', 'HK', 'US'}
        self.types = {'STOCK', 'INDEX', 'ETF', 'CRYPTO', 'TRUST', 'FUND'}
        self.actions = {'History'}
        
        # Selection State
        self.selected_markets = self.markets.copy()
        self.selected_types = self.types.copy()
        self.selected_actions = {'History'}
        self.force_full = False

def clear_screen():
    print("\033[H\033[J", end="")

def print_menu(cfg: Config):
    clear_screen()
    print("="*60)
    print(" 📥 每日增量更新 (Daily Incremental) - 智能菜单")
    print("="*60)
    
    def status(condition):
        return "✅" if condition else "❌"
    
    # Grid display
    print(f" [1] {status('CN' in cfg.selected_markets)} CN      [4] {status('STOCK' in cfg.selected_types)} Stock      [F] {status(cfg.force_full)} Force Full")
    print(f" [2] {status('HK' in cfg.selected_markets)} HK      [5] {status('INDEX' in cfg.selected_types)} Index")
    print(f" [3] {status('US' in cfg.selected_markets)} US      [6] {status('ETF' in cfg.selected_types)} ETF")
    print(f"                [7] {status('CRYPTO' in cfg.selected_types)} Crypto")
    
    print("-" * 60)
    print(" [0] ▶️  开始执行     [A] 全选     [C] 清空")
    print(" [Q] 退出")
    print("="*60)

def toggle(selection_set, item):
    if item in selection_set:
        selection_set.remove(item)
    else:
        selection_set.add(item)

def toggle_bool(obj, attr):
    setattr(obj, attr, not getattr(obj, attr))

def configure():
    cfg = Config()
    toggles = {
        '1': lambda: toggle(cfg.selected_markets, 'CN'),
        '2': lambda: toggle(cfg.selected_markets, 'HK'),
        '3': lambda: toggle(cfg.selected_markets, 'US'),
        '4': lambda: toggle(cfg.selected_types, 'STOCK'),
        '5': lambda: toggle(cfg.selected_types, 'INDEX'),
        '6': lambda: toggle(cfg.selected_types, 'ETF'),
        '7': lambda: toggle(cfg.selected_types, 'CRYPTO'),
        'F': lambda: toggle_bool(cfg, 'force_full')
    }
    
    while True:
        print_menu(cfg)
        try:
            choice = input(" 请输入选项 [号/A/C/Q]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
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
        elif choice == 'C':
            cfg.selected_markets.clear()
            cfg.selected_types.clear()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Daily Incremental Update Script')
    parser.add_argument('--market', type=str, choices=['CN', 'HK', 'US', 'ALL'], help='Filter by market')
    parser.add_argument('--symbol', type=str, help='Filter by specific symbol (e.g. HK:STOCK:09988)')
    parser.add_argument('--full', action='store_true', help='Force full download (max)')
    args = parser.parse_args()
    
    target_market = args.market
    target_symbol = args.symbol
    target_types = "ALL"
    
    # 1. Configuration
    target_full = args.full
    if not target_market and not target_symbol and not args.full:
        cfg = configure()
        target_market = list(cfg.selected_markets)
        target_types = list(cfg.selected_types)
        target_full = cfg.force_full
    
    run_daily_update(target_market=target_market, target_symbol=target_symbol, target_types=target_types, force_full=target_full)
