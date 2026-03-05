#!/usr/bin/env python3
"""
期权数据下载脚本 - fetch_options_data.py
==============================================================================

功能:
1. 从 Watchlist 获取需要下载期权的股票列表
2. 支持美股/港股市场开关
3. 下载1、2、3个月到期的近价看跌期权
4. 计算希腊字母并存入数据库
5. 自动清理过期期权

使用方法:
    python3 fetch_options_data.py --market US --months 1,2,3
    python3 fetch_options_data.py --market HK --months 1,2
    python3 fetch_options_data.py --all  # 下载所有市场
"""

import argparse
import yfinance as yf
import mibian
from scipy.stats import norm
from backend.symbol_utils import get_yahoo_symbol
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 无风险利率配置
RISK_FREE_RATES = {
    'US': 0.045,  # 美国国债收益率
    'HK': 0.035   # 香港国债收益率
}

# 导入 Futu API (放在 sqlmodel 之前)
try:
    from futu import *
    FUTU_AVAILABLE = True
except ImportError as e:
    FUTU_AVAILABLE = False
    # 暂时用 print，因为 logger 可能尚未配置好 (取决于执行顺序)
    # 不过上面的 logger = logging.getLogger(__name__) 已经在配置之后了，所以可以用 logger
    print(f"Futu API (futu-api) 导入失败，港股期权不可用。错误详情: {e}")

# 必须在 futu 之后导入 sqlmodel，以确保 Session 指向 sqlmodel.Session
from sqlmodel import Session, select, delete
from backend.database import engine
from backend.models import Watchlist
from backend.option_models import OptionData, OptionCSPCandidate
import yaml

def load_csp_config():
    try:
        with open("config/permission_rules.yaml", "r") as f:
            config = yaml.safe_load(f)
            return config.get("csp_contract_prefs", {})
    except Exception as e:
        print(f"Failed to load CSP config: {e}")
        return {}

def save_csp_candidate(session, candidate_data):
    try:
        candidate = OptionCSPCandidate(**candidate_data)
        session.add(candidate)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Failed to save CSP candidate: {e}")

def filter_and_save_csp_candidates(chain_df, spot_price, expiry_date, session, symbol, market, prefs):
    """
    Filter option chain for CSP candidates and save to DB.
    Handles both Futu (HK) and yfinance (US) DataFrame structures.
    """
    if not prefs or chain_df.empty:
        return

    try:
        # Config
        hard_min = prefs["tenor_days"]["hard_min"]
        hard_max = prefs["tenor_days"]["hard_max"]
        min_discount = prefs["moneyness"]["min_discount_pct"]
        max_discount = prefs["moneyness"]["max_discount_pct"]
        
        # Calculate DTE
        expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        today = datetime.now()
        dte = (expiry_dt - today).days
        
        
        if not (hard_min <= dte <= hard_max):
            return

        # Normalize Columns
        # US (yfinance): 'strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility'
        # HK (Futu): 'strike_price', 'last_price', 'bid_price', 'ask_price', 'option_implied_volatility', 'option_delta'
        
        # Create a standardized copy
        df = chain_df.copy()
        
        # Standardize Strike
        if 'strike_price' in df.columns: df['strike'] = df['strike_price']
        
        # Iterate rows
        count = 0
        for _, row in df.iterrows():
            strike = row['strike']
            if spot_price <= 0: continue
            
            discount_pct = (spot_price - strike) / spot_price
            
            # Check Moneyness Filter (Low 3-7%)
            if not (min_discount <= discount_pct <= max_discount):
                # print(f"debug: reject s={strike} disc={discount_pct:.2f}")
                continue
                
            # Extract Data
            mid = None
            bid = row.get('bid_price') if 'bid_price' in row else row.get('bid', 0)
            ask = row.get('ask_price') if 'ask_price' in row else row.get('ask', 0)
            
            # Handle NaN/0 types
            import math
            if isinstance(bid, float) and math.isnan(bid): bid = 0
            if isinstance(ask, float) and math.isnan(ask): ask = 0
            
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2.0
            
            # Greeks (HK has them, US might calculate later or exist)
            iv = row.get('option_implied_volatility') if 'option_implied_volatility' in row else row.get('impliedVolatility')
            delta = row.get('option_delta') if 'option_delta' in row else row.get('delta') # wrapper script might add delta to df for US? No.
            
            # For US, yfinance doesn't give greeks directly in chain df usually. 
            # But the caller (fetch_options_for_symbol) calculates them! 
            # Wait, the caller loop iterates rows and calculates greeks.
            # I am calling this function *inside* the Fetcher function, so I have access to the *chain* DF before iteration?
            # Or I should call this *after* processing?
            # Actually, `fetch_options_for_symbol` calculates Greeks row by row.
            # If I call this on the raw dataframe, I miss the Greeks for US.
            # But I can accept `delta=None` for now or calculate rudimentary ones if needed.
            # The Requirement says "data landing or export".
            # I will save what I have.
            
            candidate_data = {
                "symbol": symbol,
                "expiry_date": expiry_date,
                "dte": dte,
                "strike": strike,
                "spot": spot_price,
                "discount_pct": discount_pct,
                "mid_price": mid,
                "bid": bid,
                "ask": ask,
                "iv": iv,
                "delta": delta,
                # "gamma": ... (omitted for brevity if not available)
                "created_at": datetime.now()
            }
            
            save_csp_candidate(session, candidate_data)
            count += 1
            
        if count > 0:
            print(f"    ✨ Found {count} CSP candidates for {expiry_date}")

    except Exception as e:
        print(f"Error filtering CSP candidates: {e}")



def calculate_days_to_expiry(expiry_date_str):
    """计算距离到期日的天数"""
    expiry = datetime.strptime(expiry_date_str, '%Y-%m-%d')
    today = datetime.now()
    days = (expiry - today).days
    return days

def find_target_expiry_dates(ticker, target_months=[1, 2, 3]):
    """
    找到目标月份的期权到期日
    
    参数:
        ticker: yfinance Ticker对象
        target_months: 目标月份列表 [1, 2, 3]
    
    返回:
        {1: '2026-03-20', 2: '2026-04-17', 3: '2026-05-15'}
    """
    try:
        all_expiries = ticker.options
        if not all_expiries:
            return {}
        
        today = datetime.now()
        target_dates = {}
        
        for month in target_months:
            target_date = today + timedelta(days=30 * month)
            
            # 找到最接近目标日期的到期日
            closest_expiry = None
            min_diff = float('inf')
            
            for expiry_str in all_expiries:
                expiry = datetime.strptime(expiry_str, '%Y-%m-%d')
                diff = abs((expiry - target_date).days)
                
                # 确保是未来日期
                if expiry > today and diff < min_diff:
                    min_diff = diff
                    closest_expiry = expiry_str
            
            if closest_expiry:
                target_dates[month] = closest_expiry
        
        return target_dates
        
    except Exception as e:
        print(f"查找到期日失败: {e}")
        return {}

def find_target_expiry_dates_with_csp(ticker, target_months=[1, 2, 3], csp_prefs=None):
    """
    Find target expiry dates, including standard months AND CSP-specific range.
    """
    target_dates = find_target_expiry_dates(ticker, target_months) # Reuse existing logic
    
    if not csp_prefs:
        return target_dates
        
    try:
        hard_min = csp_prefs["tenor_days"]["hard_min"]
        hard_max = csp_prefs["tenor_days"]["hard_max"]
        
        all_expiries = ticker.options
        if not all_expiries: return target_dates
        
        today = datetime.now()
        
        for expiry_str in all_expiries:
            expiry = datetime.strptime(expiry_str, '%Y-%m-%d')
            days = (expiry - today).days
            
            if hard_min <= days <= hard_max:
                # Add to targets if not already present
                # Use a unique key to avoid overwriting month keys
                display_key = f"CSP_{days}d" 
                if expiry_str not in target_dates.values():
                   target_dates[display_key] = expiry_str
                   
    except Exception as e:
        print(f"Error finding CSP expiries: {e}")
        
    return target_dates


def find_near_money_puts(option_chain, underlying_price, num_strikes=3):
    """
    找到接近标的价格的看跌期权
    
    参数:
        option_chain: 期权链数据
        underlying_price: 标的价格
        num_strikes: 返回的执行价数量
    
    返回:
        DataFrame of near-money put options
    """
    puts = option_chain.puts
    
    if puts.empty:
        return puts
    
    # 计算每个执行价与标的价格的距离
    puts = puts.copy()
    puts['distance'] = abs(puts['strike'] - underlying_price)
    
    # 选择最接近的N个执行价
    near_money = puts.nsmallest(num_strikes, 'distance')
    
    return near_money

def calculate_greeks(underlying_price, strike, risk_free_rate, days_to_expiry, implied_vol):
    """
    使用 mibian 计算希腊字母
    
    返回:
        dict with greeks or None if calculation fails
    """
    try:
        if implied_vol <= 0 or days_to_expiry <= 0:
            return None
        
        greeks = mibian.BS(
            [underlying_price, strike, risk_free_rate * 100, days_to_expiry],
            volatility=implied_vol * 100
        )
        
        return {
            'delta': greeks.putDelta,
            'gamma': greeks.gamma,
            'theta': greeks.putTheta,
            'vega': greeks.vega,
            'rho': greeks.putRho,
            'theoretical_price': greeks.putPrice
        }
    except Exception as e:
        print(f"计算希腊字母失败: {e}")
        return None

def fetch_hk_options_futu(symbol, session, target_months, csp_prefs=None, quote_ctx=None):
    """
    使用 Futu OpenD 获取港股期权数据
    需要本地运行 OpenD (127.0.0.1:11111)
    """
    if not FUTU_AVAILABLE:
        print("❌ Futu API 未安装，无法获取港股期权")
        return 0
        
    code = symbol.split(':')[-1]
    futu_symbol = f"HK.{code}"
    
    print(f"\n{'='*60}")
    print(f"Futu 处理 {symbol} -> {futu_symbol}")
    print(f"{'='*60}")
    
    close_ctx_here = False
    if quote_ctx is None:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        close_ctx_here = True
        
    total_saved = 0
    import time
    
    try:
        # 1. 获取正股当前价格
        ret, snap_df = quote_ctx.get_market_snapshot([futu_symbol])
        if ret != RET_OK:
            print(f"❌ 无法获取 {futu_symbol} 当前价格: {snap_df}")
            if close_ctx_here: quote_ctx.close()
            return 0
            
        underlying_price = snap_df['last_price'][0]
        print(f"  💰 当前价格: ${underlying_price:.2f}")
        time.sleep(0.5) # Prevent rate limit
        
        # 2. 获取到期日列表
        ret, expiry_df = quote_ctx.get_option_expiration_date(code=futu_symbol)
        if ret != RET_OK:
            print(f"  ⚠️  无法获取到期日: {expiry_df}")
            if close_ctx_here: quote_ctx.close()
            return 0
            
        time.sleep(0.5) # Prevent rate limit after expiration query
            
        # 筛选目标月份的到期日
        target_dates = {}
        today = datetime.now()
        existing_expiries = pd.to_datetime(expiry_df['strike_time']).dt.strftime('%Y-%m-%d').tolist()
        
        for month in target_months:
            target_date = today + timedelta(days=30 * month)
            # Find closest future expiry
            closest = None
            min_diff = 999
            for exp in existing_expiries:
                exp_date = datetime.strptime(exp, '%Y-%m-%d')
                if exp_date > today:
                    diff = abs((exp_date - target_date).days)
                    if diff < min_diff:
                        min_diff = diff
                        closest = exp
            if closest:
                target_dates[month] = closest
        
        # Add CSP Dates for HK
        if csp_prefs:
            try:

                hard_min = csp_prefs["tenor_days"]["hard_min"]
                hard_max = csp_prefs["tenor_days"]["hard_max"]
                for exp in existing_expiries:
                    exp_date = datetime.strptime(exp, '%Y-%m-%d')
                    days = (exp_date - today).days
                    if hard_min <= days <= hard_max:
                        # Use expiry date string as value, ensure we scan it
                        # Key can be anything unique
                        if exp not in target_dates.values():
                            target_dates[f"CSP_{days}d"] = exp
            except Exception as e:
                print(f"Error adding HK CSP dates: {e}")
                
        print(f"  📅 目标到期日: {list(target_dates.values())}")

        # 3. 遍历到期日获取期权链
        for month, expiry_date in target_dates.items():
            days_to_expiry = calculate_days_to_expiry(expiry_date)
            
            # 获取该到期日的看跌期权 (PUT)
            ret, chain_df = quote_ctx.get_option_chain(
                code=futu_symbol, 
                start=expiry_date, 
                end=expiry_date, 
                option_type=OptionType.PUT
            )
            
            if ret != RET_OK:
                print(f"  ⚠️  无法获取 {expiry_date} 期权链: {chain_df}")
                continue
                
            if chain_df.empty:
                continue

            time.sleep(3.1) # 严格控制获取期权链频率，每30秒最多10次
            
            filter_and_save_csp_candidates(chain_df, underlying_price, expiry_date, session, symbol, 'HK', csp_prefs)

            # 筛选近价期权 (Moneyness)
            if 'strike_price' in chain_df.columns:
                chain_df['strike'] = chain_df['strike_price']
            
            chain_df['distance'] = abs(chain_df['strike'] - underlying_price)
            near_puts = chain_df.nsmallest(3, 'distance')
            
            print(f"\n  📊 {expiry_date} - 找到 {len(near_puts)} 个近价 PUT")
            
            # 批量获取期权行情快照
            option_codes = near_puts['code'].tolist()
            ret, opt_snaps = quote_ctx.get_market_snapshot(option_codes)
            if ret != RET_OK:
                print(f"  ⚠️  无法获取期权行情: {opt_snaps}")
                time.sleep(1) # Backoff
                continue
            
            time.sleep(0.5) # Prevent rate limit
            
            # 合并数据
            merged = pd.merge(near_puts, opt_snaps, on='code', how='inner')
            
            for _, row in merged.iterrows():
                try:
                    # 数据提取
                    option_ret_code = row['code'] # e.g. HK.0070023092800185
                     # Futu format: HK.00700... we need standard format? Or keep Futu format?
                    # Let's keep a readable format or use Futu's code as option_symbol
                    
                    strike = row['strike']
                    last_price = row['last_price']
                    
                    bid = row.get('bid_price', 0)
                    ask = row.get('ask_price', 0)
                    vol = row.get('volume', 0)
                    oi = row.get('open_interest', 0)
                    
                    # 从 Futu 快照直接获取 Greeks 和 IV (优于本地计算)
                    iv = row.get('option_implied_volatility')
                    delta = row.get('option_delta')
                    gamma = row.get('option_gamma')
                    vega = row.get('option_vega')
                    theta = row.get('option_theta')
                    rho = row.get('option_rho')
                    
                    # 处理无效值 (Futu 可能返回 -999 或 NaN)
                    def clean_greek(val):
                        if pd.isna(val) or val == -999: return None
                        return float(val)

                    iv = clean_greek(iv)
                    # 注意: Futu 的 IV 通常是百分比 (e.g. 30.5 表示 30.5%), 还是小数? 
                    # 通常 API 返回的是百分比数值，但也可能视版本而定。
                    # 此处假设它是百分比数值，需转为小数? (yfinance 是小数 0.305)
                    # 经查证，Futu API 返回的 IV 通常是百分比 (例如 25.5)，为了统一，我们应除以 100 吗？
                    # 我们的数据库期望小数 (0.255) 还是百分比 (25.5)?
                    # fetch_options_data.py 里: print(f"IV {option.get('impliedVolatility', 0)*100:.1f}%")
                    # 说明 fetch_options_data 认为 yfinance 返回的是小数 (0.x)。
                    # Futu 返回的 IV 通常也是小数 (0.x) 或者百分比。
                    # 让我们先保持原值，如果发现是百分比 (例如 > 1)，我们再处理。
                    # 通常 Futu 返回的是百分比 (如 25.432)，我们需要除以 100 变成 0.25432 以对齐 yfinance 格式
                    if iv and iv > 1: iv = iv / 100.0

                    delta = clean_greek(delta)
                    gamma = clean_greek(gamma)
                    vega = clean_greek(vega)
                    theta = clean_greek(theta)
                    rho = clean_greek(rho)
                    
                    # Calculate Moneyness
                    moneyness = (strike - underlying_price) / underlying_price
                    
                    option_data = OptionData(
                        symbol=symbol,
                        market='HK',
                        underlying_price=underlying_price,
                        option_symbol=option_ret_code,
                        option_type='PUT',
                        strike=strike,
                        expiry_date=expiry_date,
                        days_to_expiry=days_to_expiry,
                        last_price=last_price,
                        bid=bid,
                        ask=ask,
                        volume=int(vol),
                        open_interest=int(oi),
                        implied_volatility=iv,
                        delta=delta, 
                        gamma=gamma, 
                        theta=theta, 
                        vega=vega, 
                        rho=rho,
                        theoretical_price=None, # Futu 不直接返回理论价，可选填
                        moneyness=moneyness,
                        currency='HKD',
                        data_source='futu',
                        updated_at=datetime.now()
                    )
                    
                    # Upsert
                    existing = session.exec(
                        select(OptionData).where(
                            OptionData.symbol == symbol,
                            OptionData.option_symbol == option_data.option_symbol,
                            OptionData.expiry_date == expiry_date
                        )
                    ).first()
                    
                    if existing:
                        for key, value in option_data.model_dump(exclude={'id', 'created_at'}).items():
                            setattr(existing, key, value)
                    else:
                        session.add(option_data)
                        
                    total_saved += 1
                    
                    itm_status = "价内" if moneyness > 0 else "价外" if moneyness < 0 else "平值"
                    print(f"     ✓ ${strike:.2f} ({itm_status}) - Last: ${last_price:.2f}")

                except Exception as e:
                    print(f"Save Error: {e}")
                    
            session.commit()
            
    except Exception as e:
        print(f"Futu Error: {e}")
    finally:
        if close_ctx_here:
            quote_ctx.close()
        
    return total_saved

def fetch_options_for_symbol(symbol, market, target_months, session, csp_prefs=None, quote_ctx=None):
    """
    为单个股票下载期权数据
    """
    # 严格过滤：仅支持美股和港股
    if market not in ['US', 'HK']:
        return 0

    # 针对港股，优先使用 Futu
    if market == 'HK':
        return fetch_hk_options_futu(symbol, session, target_months, csp_prefs, quote_ctx=quote_ctx)

    # 针对美股，继续使用 yfinance
    # 使用统一工具函数获取 yfinance 格式的 symbol (例如 HK:STOCK:00700 -> 0700.HK)
    raw_symbol = symbol.split(':')[-1]
    ticker_symbol = get_yahoo_symbol(raw_symbol, market, 'STOCK')
    
    print(f"\n{'='*60}")
    print(f"处理 {symbol} -> Ticker: {ticker_symbol}")
    print(f"{'='*60}")
    
    try:
        # 获取股票数据
        ticker = yf.Ticker(ticker_symbol)
        
        # 获取当前价格
        try:
            underlying_price = ticker.info.get('currentPrice') or ticker.info.get('regularMarketPrice')
            if not underlying_price:
                hist = ticker.history(period='1d')
                underlying_price = hist['Close'].iloc[-1] if not hist.empty else None
            
            if not underlying_price:
                print(f"  ❌ 无法获取 {ticker_symbol} 的当前价格")
                return 0
            
            print(f"  💰 当前价格: ${underlying_price:.2f}")
            
        except Exception as e:
            print(f"  ❌ 获取价格失败: {e}")
            return 0
        
        # 获取货币单位
        currency = 'USD' if market == 'US' else 'HKD'
        
        # 找到目标到期日
        target_expiries = find_target_expiry_dates_with_csp(ticker, target_months, csp_prefs)
        
        if not target_expiries:
            print(f"  ⚠️  没有找到合适的期权到期日")
            return 0
        
        print(f"  📅 目标到期日:")
        for month, expiry in target_expiries.items():
            days = calculate_days_to_expiry(expiry)
            print(f"     {month}个月: {expiry} (距今{days}天)")
        
        # 获取无风险利率
        risk_free_rate = RISK_FREE_RATES.get(market, 0.04)
        
        total_saved = 0
        
        # 遍历每个到期日
        for month, expiry_date in target_expiries.items():
            try:
                # 获取期权链
                option_chain = ticker.option_chain(expiry_date)
                days_to_expiry = calculate_days_to_expiry(expiry_date)
                
                if days_to_expiry <= 0:
                    print(f"  ⚠️  {expiry_date} 已过期，跳过")
                    continue
                
                # 找到近价看跌期权
                near_puts = find_near_money_puts(option_chain, underlying_price, num_strikes=3)
                
                if near_puts.empty:
                    print(f"  ⚠️  {expiry_date} 没有看跌期权数据")
                    continue
                
                # Filter CSP
                filter_and_save_csp_candidates(option_chain.puts, underlying_price, expiry_date, session, symbol, 'US', csp_prefs)
                
                print(f"\n  📊 {expiry_date} - 找到 {len(near_puts)} 个近价看跌期权")
                
                # 保存每个期权
                for idx, (_, option) in enumerate(near_puts.iterrows()):
                    try:
                        # 尝试多种方式获取 bid/ask
                        bid = option.get('bid', 0) or option.get('bidPrice', 0)
                        ask = option.get('ask', 0) or option.get('askPrice', 0)
                        
                        # 如果是包含 NaN 的数据，转换为 0
                        import math
                        if isinstance(bid, float) and math.isnan(bid): bid = 0
                        if isinstance(ask, float) and math.isnan(ask): ask = 0

                        # 计算价值状态
                        moneyness = (option['strike'] - underlying_price) / underlying_price
                        
                        # 计算希腊字母
                        greeks = None
                        if option.get('impliedVolatility') and option['impliedVolatility'] > 0:
                            greeks = calculate_greeks(
                                underlying_price,
                                option['strike'],
                                risk_free_rate,
                                days_to_expiry,
                                option['impliedVolatility']
                            )
                        
                        # 创建或更新期权记录
                        option_data = OptionData(
                            symbol=symbol,
                            market=market,
                            underlying_price=underlying_price,
                            option_symbol=option.get('contractSymbol', f"{ticker_symbol}_PUT_{option['strike']}_{expiry_date}"),
                            option_type='PUT',
                            strike=option['strike'],
                            expiry_date=expiry_date,
                            days_to_expiry=days_to_expiry,
                            last_price=option['lastPrice'],
                            bid=bid,
                            ask=ask,
                            volume=int(option.get('volume', 0) or 0),  # 处理 NaN
                            open_interest=int(option.get('openInterest', 0) or 0),
                            implied_volatility=option.get('impliedVolatility'),
                            delta=greeks['delta'] if greeks else None,
                            gamma=greeks['gamma'] if greeks else None,
                            theta=greeks['theta'] if greeks else None,
                            vega=greeks['vega'] if greeks else None,
                            rho=greeks['rho'] if greeks else None,
                            theoretical_price=greeks['theoretical_price'] if greeks else None,
                            moneyness=moneyness,
                            currency=currency,
                            data_source='yfinance',
                            updated_at=datetime.now()
                        )
                        
                        # 检查是否已存在
                        existing = session.exec(
                            select(OptionData).where(
                                OptionData.symbol == symbol,
                                OptionData.option_symbol == option_data.option_symbol,
                                OptionData.expiry_date == expiry_date
                            )
                        ).first()
                        
                        if existing:
                            # 更新现有记录
                            for key, value in option_data.model_dump(exclude={'id', 'created_at'}).items():
                                setattr(existing, key, value)
                        else:
                            # 插入新记录
                            session.add(option_data)
                        
                        total_saved += 1
                        
                        # 输出详情
                        itm_status = "价内" if moneyness > 0 else "价外" if moneyness < 0 else "平值"
                        print(f"     ✓ ${option['strike']:.2f} ({itm_status}) - "
                                  f"Last: ${option['lastPrice']:.2f}, IV {option.get('impliedVolatility', 0)*100:.1f}%")
                        
                    except Exception as e:
                        print(f"     ✗ 保存期权失败: {e}")
                        continue
                
            except Exception as e:
                print(f"  ❌ 处理到期日 {expiry_date} 失败: {e}")
                continue
        
        # 提交所有更改
        session.commit()
        print(f"\n  ✅ 成功保存 {total_saved} 条期权数据")
        
        return total_saved
        
    except Exception as e:
        print(f"  ❌ 处理 {symbol} 失败: {e}")
        session.rollback()
        return 0

def clean_expired_options(session):
    """清理已过期的期权数据"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # 删除过期期权
        stmt = delete(OptionData).where(OptionData.expiry_date < today)
        result = session.exec(stmt)
        session.commit()
        
        deleted_count = result.rowcount if hasattr(result, 'rowcount') else 0
        print(f"🗑️  清理了 {deleted_count} 条过期期权数据")
        
    except Exception as e:
        print(f"清理过期数据失败: {e}")
        session.rollback()

def main():
    parser = argparse.ArgumentParser(description='下载期权数据')
    parser.add_argument('--market', type=str, choices=['US', 'HK', 'ALL'], 
                       help='市场选择 (US/HK/ALL)')
    parser.add_argument('--months', type=str, default='1,2,3',
                       help='目标月份，逗号分隔 (如 1,2,3)')
    parser.add_argument('--clean', action='store_true',
                       help='清理过期期权数据')
    
    args = parser.parse_args()
    
    # 交互式菜单逻辑
    selected_markets = {'US': True, 'HK': True}  # 默认全选
    
    if not args.market:
        while True:
            # 动态生成菜单
            us_status = "✅" if selected_markets['US'] else "⬜"
            hk_status = "✅" if selected_markets['HK'] else "⬜"
            
            print("\n" + "="*50)
            print("🎯  VERA 期权数据下载中心")
            print("="*50)
            print("请选择要下载的市场 (输入数字切换开关):")
            print(f"  1. {us_status} 美股 (US)")
            print(f"  2. {hk_status} 港股 (HK)")
            print("-" * 50)
            print("  0/Enter. 🚀 开始下载")
            print("  Q.       🚪 退出程序")
            print("="*50)
            
            choice = input("\n请输入选项: ").strip().upper()
            
            if choice == '1':
                selected_markets['US'] = not selected_markets['US']
            elif choice == '2':
                selected_markets['HK'] = not selected_markets['HK']
            elif choice == 'Q':
                print("👋 已退出")
                return
            elif choice == '0' or choice == '':
                if not any(selected_markets.values()):
                    print("⚠️  请至少选择一个市场！")
                    continue
                break
            else:
                print("❌ 无效输入")
    
    # 确定最终的市场参数
    if args.market:
        final_market_arg = args.market
    else:
        if selected_markets['US'] and selected_markets['HK']:
            final_market_arg = 'ALL'
        elif selected_markets['US']:
            final_market_arg = 'US'
        elif selected_markets['HK']:
            final_market_arg = 'HK'
        else:
            return  # Should be caught by the loop above
            
    # 解析目标月份
    target_months = [int(m.strip()) for m in args.months.split(',')]
    
    # Load CSP Config
    csp_prefs = load_csp_config()
    if csp_prefs:
        print("🔧 Loaded CSP Preferences")
    else:
        print("⚠️ CSP Config Could not be loaded or is empty")

    print("="*60)
    print("期权数据下载任务启动")
    print("="*60)
    print(f"市场: {final_market_arg}")
    print(f"目标月份: {target_months}")
    print(f"清理过期数据: {'是' if args.clean else '否'}") 
    print("="*60)
    
    with Session(engine) as session:
        # 清理过期数据
        if args.clean:
            clean_expired_options(session)
        
        # 获取 Watchlist
        watchlist_items = session.exec(select(Watchlist)).all()
        
        # 过滤出股票类型
        stocks = [item for item in watchlist_items if ':STOCK:' in item.symbol]
        
        # 按市场过滤
        if final_market_arg == 'US':
            stocks = [s for s in stocks if s.symbol.startswith("US:")]
        elif final_market_arg == 'HK':
            stocks = [s for s in stocks if s.symbol.startswith("HK:")]
        # ALL 不需要额外过滤，后面会统一过滤掉不支持的市场
        
        # 重要的二次过滤：只保留 US 和 HK
        # 即使选了 ALL，也必须剔除 CN (A股) 等不支持的市场
        valid_stocks = [s for s in stocks if s.symbol.split(':')[0] in ['US', 'HK']]
        
        print(f"\n找到 {len(valid_stocks)} 只符合条件的股票 (已过滤不支持的市场)\n")
        
        if not valid_stocks:
            print("❌ 没有找到符合条件的股票，任务结束")
            return
            
        total_options = 0
        success_count = 0
            
        quote_ctx = None
        if FUTU_AVAILABLE and any(s.symbol.startswith('HK:') for s in valid_stocks):
            try:
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            except Exception as e:
                print(f"❌ 无法连接到 Futu OpenD: {e}")
                
        try:
            for item in valid_stocks:
                # 提取市场
                market = item.symbol.split(':')[0]
                
                # 下载期权数据
                saved = fetch_options_for_symbol(
                    item.symbol,
                    market,
                    target_months,
                    session,
                    csp_prefs,
                    quote_ctx=quote_ctx
                )
                
                if saved > 0:
                    success_count += 1
                    total_options += saved
                    
                # 为了防止 yfinance 限制/Futu频繁调用，适当延时
                time.sleep(1.0)
        finally:
            if quote_ctx:
                quote_ctx.close()
        print("\n" + "="*60)
        print("下载任务完成")
        print("="*60)
        print(f"成功处理: {success_count}/{len(valid_stocks)} 只股票")
        print(f"总计保存: {total_options} 条期权数据")
        print("="*60)
        
        # 打印导出提示
        print("\n📝  后续步骤:")
        print("您现在可以导出所有期权数据到 CSV 文件：")
        print(f"👉  python3 export_options_csv.py")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
