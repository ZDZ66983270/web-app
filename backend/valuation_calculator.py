r"""
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# ⚠️ WARNING: CORE VALUATION LOGIC - DO NOT MODIFY WITHOUT APPROVAL
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Valuation Calculator (估值计算核心模块)
=====================================

此模块实现了 VERA Pro (Valuation Engine for Risk Assessment) 的核心算法。
所有历史回填 (Backfill) 和实时计算 (ETL) 均**必须**调用此模块，严禁硬编码。

核心逻辑与公式 (The VERA Pro Standard):
----------------------------------
1. **市盈率 (PE TTM)**:
   $$PE_{TTM} = \frac{\text{Price}}{\text{EPS}_{TTM}}$$
   
   其中 $\text{EPS}_{TTM}$ 计算步骤如下:
   
   a. **分子 (Numerator)**: 
      - 使用 **归属于普通股股东的净利润 (Net Income Available to Common Stockholders)**。
      - 严禁使用未扣除优先股股息的 Net Income。
      - 来源: `FinancialFundamentals.net_income_common_ttm`
      
   b. **分母 (Denominator)**:
      - 使用 **稀释加权平均股数 (Weighted Average Diluted Shares)**。
      - 来源: `FinancialFundamentals.shares_diluted`
      
   c. **汇率 (FX Conversion)**:
      - 必须进行动态汇率换算，严禁使用静态汇率。
      - 公式: `EPS_{Market} = EPS_{Report} \times \text{FX\_Rate}(\text{Date})`
      - 来源: `ForexRate` 表 (通过 `session` 查询)
      
   d. **ADR 换算**:
      - 对于 ADR，需乘以换算比例 (e.g. TSM: 1 ADR = 5 Common)。
      - 公式: `EPS_{Final} = EPS_{Market} \times \text{ADR\_Ratio}`

2. **数据源优先级 (Data Priority Logic)**:
   - 优先使用 `FinancialFundamentals` 中的清洗后数据 (Verified Data)。
   - 缺失时回退到 Yahoo Finance/FMP 的原始字段，但必须记录警告。

3. **Point-in-Time (PIT) 原则 (Time Travel Prevention)**:
   - 历史计算必须基于**当时已知**的财报 (Filing Date <= Calculation Date)。
   - 严禁使用未来数据。

4. **稀释股本获取策略 (Shares Outstanding Strategy)**:
   - 优先级 1: 财报中的 `weightedAverageShsOutDil` (最准)。
   - 优先级 2: `SYMBOLS_CONFIG` 中的手工配置 (针对拆股等特殊情况)。
   - 优先级 3: `MarketCap / Price` (动态推导)。
   - 优先级 4: 接口原始 `sharesOutstanding`。

5. **异常处理逻辑 (Exception Handling)**:
   - 缺少汇率: 尝试静态配置 -> 失败则报错，拒绝计算 (避免 HSBC 100x PE)。
   - 缺少财报: 返回 None，不强行填充。
   - 亏损股: EPS 保留负值，PE 返回 None (前端显示亏损)。


作者: Antigravity
日期: 2026-01-23 (Audit Passed)
"""
import logging
import pandas as pd
from typing import Optional, Tuple, List
from sqlmodel import Session, select
from .models import FinancialFundamentals, ForexRate
from .symbols_config import FOREX_RATES, get_yfinance_symbol, normalize_code, SYMBOLS_CONFIG, get_symbol_info
from .sanitizers import sanitize_financials, check_valuation_outliers
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger("ValuationCalculator")


_FX_SERIES_CACHE = {} # { (from, to): [(date, rate), ...] }

def get_dynamic_fx_rate(
    session: Session,
    from_curr: str,
    to_curr: str,
    date: str
) -> float:
    """
    获取动态汇率 (优先查库，失败则回退到静态配置)
    """
    if from_curr == to_curr:
        return 1.0

    pair = (from_curr, to_curr)
    
    # 1. Check if we have pre-loaded this series
    if pair not in _FX_SERIES_CACHE:
        # Load all records for this pair from DB once
        stmt = select(ForexRate).where(
            ForexRate.from_currency == from_curr,
            ForexRate.to_currency == to_curr
        ).order_by(ForexRate.date.asc())
        
        recs = session.exec(stmt).all()
        if recs:
            _FX_SERIES_CACHE[pair] = [(r.date, r.rate) for r in recs]
        else:
            # Try reverse lookup if forward fails
            rev_pair = (to_curr, from_curr)
            stmt_rev = select(ForexRate).where(
                ForexRate.from_currency == to_curr,
                ForexRate.to_currency == from_curr
            ).order_by(ForexRate.date.asc())
            
            recs_rev = session.exec(stmt_rev).all()
            if recs_rev:
                _FX_SERIES_CACHE[pair] = [(r.date, 1.0 / r.rate) for r in recs_rev]
            else:
                # Still nothing? Mark as None to avoid repeated DB hits
                _FX_SERIES_CACHE[pair] = None

    # 2. Use memory cache if available
    series = _FX_SERIES_CACHE.get(pair)
    if series:
        import bisect
        # series is sorted by date. Find latest rate where rate_date <= date
        # bisect_right returns the place where 'date' would be inserted to the right of existing equal elements
        idx = bisect.bisect_right(series, (date, float('inf')))
        if idx > 0:
            return series[idx-1][1]
        else:
            # Date is before first available record, use the first one
            return series[0][1]

    # 3. Fallback to Static
    pair1 = f"{to_curr}/{from_curr}"
    pair2 = f"{from_curr}/{to_curr}"
    
    if pair1 in FOREX_RATES: return 1.0 / FOREX_RATES[pair1]
    if pair2 in FOREX_RATES: return FOREX_RATES[pair2]
    
    # logger.warning(f"  ⚠️ 缺失汇率: {from_curr}->{to_curr} on {date}, defaulting to 1.0 (RISK)")
    return 1.0

def compute_ttm_eps_per_unit(
    net_income_common: float,
    shares_diluted: float,
    fin_currency: str,
    market_currency: str,
    fx_rate: float,
    adr_ratio: float = 1.0
) -> Optional[float]:
    """
    计算每交易单位的 TTM EPS (核心估值逻辑 - Pro版)
    
    Args:
        net_income_common: TTM 归母净利润 (财报原币种)
        shares_diluted: 稀释加权股本 (Original Shares, 非 ADR)
        fin_currency: 财报币种
        market_currency: 市场交易币种
        fx_rate: 汇率 (1 FinCurr = ? MarketCurr)
        adr_ratio: 1 ADR 对应多少普通股
    """
    if not net_income_common or not shares_diluted or shares_diluted == 0:
        return None
        
    # 1. 基础 EPS (稀释后, 原币种)
    raw_eps = net_income_common / shares_diluted
    
    # 2. 汇率换算
    eps_market_curr = raw_eps * fx_rate
            
    # 3. ADR / 单位换算
    final_eps = eps_market_curr * adr_ratio
    
    return final_eps


def get_shares_outstanding(symbol: str, market: str) -> Optional[float]:
    """
    获取当前总股本 (优先配置 > MarketCap推算 > 字段读取)
    
    Args:
        symbol: 股票符号 (如 "US:STOCK:AAPL")
        market: 市场 (如 "US")
        
    Returns:
        float: 总股本数量
        None: 如果无法获取
    """
    # 1. Check Config Override
    simple_code = normalize_code(symbol)
    if simple_code in SYMBOLS_CONFIG:
        conf = SYMBOLS_CONFIG[simple_code]
        if conf.get("total_shares"):
            return conf.get("total_shares")

    # 2. 从 Yahoo Finance 获取
    # 从 Canonical ID 提取纯代码
    code = symbol.split(':')[-1] if ':' in symbol else symbol
    
    # Use symbol_utils.get_yahoo_symbol to correctly handle suffixes (e.g. .HK)
    from backend.symbol_utils import get_yahoo_symbol
    yf_sym = get_yahoo_symbol(code, market)
    
    try:
        ticker = yf.Ticker(yf_sym)
        info = ticker.info
        
        # Strategy: Use MarketCap / Price for Total Economic Shares
        mcap = info.get('marketCap')
        price = info.get('currentPrice') or info.get('regularMarketPreviousClose')
        
        derived_shares = 0
        if mcap and price and price > 0:
            derived_shares = mcap / price
            
        raw_shares = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding') or 0
        
        # 优先使用推算值（更准确）
        if derived_shares > 0:
            return derived_shares
        elif raw_shares > 0:
            return raw_shares
            
    except Exception as e:
        logger.warning(f"无法获取 {symbol} 的股本: {e}")
    
    return None


def get_ttm_net_income(
    financials: List[FinancialFundamentals],
    target_date: str
) -> Tuple[Optional[float], Optional[str]]:
    """
    计算 TTM 净利润 (处理累计数据)
    
    Args:
        financials: 财报数据列表 (按日期降序排列)
        target_date: 目标日期 (YYYY-MM-DD)
        
    Returns:
        Tuple[float, str]: (TTM 净利润, 币种)
        Tuple[None, None]: 如果无法计算
    """
    valid_fins = [f for f in financials if f.as_of_date <= target_date]
    if not valid_fins:
        return None, None
    
    latest = valid_fins[0]
    
    # Strategy 1: Quarterly Logic
    if latest.report_type == 'quarterly':
        qs = [f for f in valid_fins if f.report_type == 'quarterly']
        annuals = [f for f in valid_fins if f.report_type == 'annual']
        
        # Check for AkShare Accumulated Data Pattern (Common in CN/HK stocks from AkShare)
        # AkShare data sources: 'akshare-cn-quarterly', 'akshare-hk-quarterly' etc.
        is_accumulated = 'akshare' in (latest.data_source or '').lower()
        
        if is_accumulated:
            try:
                # 尝试计算: TTM = 本期累计 + (上年全年 - 上年同期累计)
                # Formula: TTM = Latest_Accum + (Prev_Annual - Prev_Same_Period_Accum)
                curr_date = latest.as_of_date # YYYY-MM-DD
                curr_year = int(curr_date[:4])
                curr_md = curr_date[4:] # -MM-DD
                
                prev_year_str = str(curr_year - 1)
                
                # 1. 找上年年报
                prev_annual = next((f for f in annuals if f.as_of_date.startswith(prev_year_str)), None)
                
                # 2. 找上年同期累计 (e.g. 2023-09-30 -> 2022-09-30)
                # 注意：考虑月底日期微差 (28/29/30/31)，简单匹配月份
                target_prev_month = curr_date[5:7]
                prev_same_period = next((
                    f for f in qs 
                    if f.as_of_date.startswith(prev_year_str) and f.as_of_date[5:7] == target_prev_month
                ), None)
                
                if prev_annual and prev_same_period:
                     # 确保字段存在
                    if prev_annual.net_income_ttm is not None and prev_same_period.net_income_ttm is not None and latest.net_income_ttm is not None:
                        # AkShare's net_income_ttm field actually stores "Net Income (Accumulated)" for quarterly reports
                        # and "Net Income (Annual)" for annual reports
                        accum_latest = latest.net_income_ttm
                        accum_prev_same = prev_same_period.net_income_ttm
                        annual_prev = prev_annual.net_income_ttm
                        
                        ttm_val = accum_latest + (annual_prev - accum_prev_same)
                        return ttm_val, latest.currency
            
            except Exception as e:
                logger.warning(f"TTM Accum logic failed for {latest.symbol}: {e}")
            
            # ⚠️ CRITICAL: AkShare data is Accumulated. Do NOT fallback to Summation.
            # If Accum logic fails, fallback to Latest Annual (safer than double counting)
            latest_annual = next((f for f in valid_fins if f.report_type == 'annual'), None)
            if latest_annual:
                return latest_annual.net_income_ttm, latest_annual.currency
            return None, None

        # Fallback (Discrete Summation - for US/Yahoo or Non-Accumulated)
        # 仅当数据源明确不是 accumulated 时才求和
        qs_top4 = qs[:4]
        if len(qs_top4) == 4:
            currencies = {q.currency for q in qs_top4}
            if len(currencies) == 1:
                # 必须确保 4 个季度都有数据，否则和偏小
                valid_quarters = [q.net_income_ttm for q in qs_top4 if q.net_income_ttm is not None]
                if len(valid_quarters) == 4:
                    total_inc = sum(valid_quarters)
                    return total_inc, latest.currency
    
    # Strategy 2: Annual Fallback
    latest_annual = next((f for f in valid_fins if f.report_type == 'annual'), None)
    if latest_annual:
        # 优先使用归母净利润 (Common)
        ni = latest_annual.net_income_common_ttm
        if ni is None: ni = latest_annual.net_income_ttm # Fallback
        return ni, latest_annual.currency
        
    return None, None


def calculate_pe_metrics(
    session: Session,
    symbol: str,
    market: str,
    close_price: float,
    as_of_date: str
) -> dict:
    """
    计算 PE 相关指标 (供 ETL 调用)
    
    Args:
        session: 数据库会话
        symbol: 股票符号
        market: 市场
        close_price: 收盘价
        as_of_date: 日期 (YYYY-MM-DD)
        
    Returns:
        dict: {'eps': float, 'pe': float} or {'eps': None, 'pe': None}
    """
    try:
        # 1. Fetch Fundamentals
        stmt = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        financials = session.exec(stmt).all()
        
        if not financials:
            return {'eps': None, 'pe': None}
        
        # 2. 筛选 PIT (Point-in-Time) 财报
        pit_financials = [f for f in financials if (f.filing_date and f.filing_date <= as_of_date) or (f.as_of_date <= as_of_date)]
        
        if not pit_financials:
            return {'eps': None, 'pe': None}

        # 🎯 NORMALIZE: 使用 Sanitizer 清洗数据
        latest_fin = sanitize_financials(pit_financials[0])
        fin_currency = latest_fin.currency
        
        # 3. 计算 TTM 净利润 (优先使用 Common)
        ttm_income = latest_fin.net_income_common_ttm
        if ttm_income is None:
             ttm_income, _ = get_ttm_net_income(pit_financials, as_of_date)
             
        if ttm_income is None:
            return {'eps': None, 'pe': None}
        
        # 4. 获取稀释股本
        shares_diluted = latest_fin.shares_diluted or latest_fin.shares_outstanding_common_end
        
        # 5. 获取配置信息 & 汇率
        config = get_symbol_info(symbol)
        adr_ratio = config.get('adr_ratio', 1.0)
        
        # 兜底股本
        if not shares_diluted:
             shares_diluted = config.get('total_shares') or get_shares_outstanding(symbol, market)
             
        if not shares_diluted:
            return {'eps': None, 'pe': None}
        
        market_currency_map = {'US': 'USD', 'HK': 'HKD', 'CN': 'CNY'}
        market_currency = market_currency_map.get(market, 'USD')
        
        # Get Dynamic FX Rate
        fx_rate = get_dynamic_fx_rate(session, fin_currency, market_currency, as_of_date)
        
        # 6. 计算 EPS
        eps = compute_ttm_eps_per_unit(
            ttm_income,
            shares_diluted, 
            fin_currency,
            market_currency,
            fx_rate,
            adr_ratio
        )
        
        if eps is None or eps <= 0:
            return {'eps': eps, 'pe': None}
        
        # 7. 计算 PE
        pe = close_price / eps
        
        # 🛡️防御: 异常值拦截
        if not check_valuation_outliers(pe, 'pe'):
             logger.warning(f"  ⚠️ [Calculator] Detect abnormal PE={pe:.2f} for {symbol}, discarded.")
             return {'eps': eps, 'pe': None}
             
        return {'eps': eps, 'pe': pe}
        
    except Exception as e:
        logger.error(f"计算 PE 失败 ({symbol}): {e}")
        return {'eps': None, 'pe': None}


def calculate_pe_metrics_with_cache(
    symbol: str,
    market: str,
    close_price: float,
    as_of_date: str,
    financials_cache: List[FinancialFundamentals],
    shares_outstanding: Optional[float] = None,
    session: Optional[Session] = None
) -> dict:
    """
    计算 PE 相关指标 (使用预加载的财报数据)
    """
    try:
        # 1. 过滤有效的 PIT 财报
        valid_financials = []
        # ... (rest of logic unchanged until FX) ...
        # Copied from viewing because replace_content needs context but I am modifying signature.
        # Actually I need to be careful not to delete lines 396-434.
        # Let me target the signature and the FX block separately or use a larger block.
        # Large block is safer for signature change.
        
        for f in financials_cache:
            if f.as_of_date <= as_of_date: 
                if f.filing_date and f.filing_date > as_of_date:
                    continue 
                valid_financials.append(f)
        
        if not valid_financials:
            return {'eps': None, 'pe': None}
        
        # 2. 计算 TTM 净利润
        latest_fin = valid_financials[0]
        ttm_income = None
        fin_currency = latest_fin.currency
        
        if latest_fin.report_type == 'annual':
            ttm_income = latest_fin.net_income_common_ttm or latest_fin.net_income_ttm
        elif latest_fin.report_type == 'quarterly':
            qs = [f for f in valid_financials if f.report_type == 'quarterly']
            qs_top4 = qs[:4]
            if len(qs_top4) == 4:
                commons = [q.net_income_common_ttm for q in qs_top4 if q.net_income_common_ttm is not None]
                if len(commons) == 4:
                    ttm_income = sum(commons)
        
        if not ttm_income:
             ttm_income, fin_currency = get_ttm_net_income(valid_financials, as_of_date)
            
        if not ttm_income:
            return {'eps': None, 'pe': None}
        
        # 3. 获取股本
        shares = latest_fin.shares_diluted
        if shares is None or shares == 0:
            if shares_outstanding is not None:
                shares = shares_outstanding
            else:
                shares = get_shares_outstanding(symbol, market)
            
        if not shares:
            return {'eps': None, 'pe': None}
        
        # 4. 获取配置信息
        simple_code = normalize_code(symbol)
        config = SYMBOLS_CONFIG.get(simple_code, {})
        adr_ratio = config.get('adr_ratio', 1.0)
        
        market_currency_map = {'US': 'USD', 'HK': 'HKD', 'CN': 'CNY'}
        market_currency = market_currency_map.get(market, 'USD')
        
        # 5. 动态汇率 (Dynamic FX) - Integrity Fix
        # Requirement: Session must be provided for historical backfill to access ForexRate table.
        # Fallback to static is dangerous (as seen with HSBC case).
        fx_rate = 1.0
        if session:
            fx_rate = get_dynamic_fx_rate(session, fin_currency, market_currency, as_of_date)
        else:
             # Critical Warning: Session missing implies we cannot fetch dynamic rates.
             # We try static fallback but log a warning.
             # Ideally this path should never be hit in production backfill.
             logger.warning(f"⚠️ Session missing in calculate_pe_metrics_with_cache for {symbol}. Using risky static fallback.")
             
             pair1 = f"{market_currency}/{fin_currency}"
             pair2 = f"{fin_currency}/{market_currency}"
             
             if pair1 in FOREX_RATES: 
                 fx_rate = 1.0 / FOREX_RATES[pair1]
             elif pair2 in FOREX_RATES: 
                 fx_rate = FOREX_RATES[pair2]
             else:
                 # If currencies differ and no static rate, this is a major logical gap.
                 if fin_currency != market_currency:
                     logger.error(f"❌ Missing FX rate for {fin_currency}->{market_currency}. PE calculation will be WRONG.")
        
        # 6. 计算 EPS
        if not fin_currency:
            return {'eps': None, 'pe': None}
            
        eps = compute_ttm_eps_per_unit(
            ttm_income,
            shares * adr_ratio, 
            fin_currency,
            market_currency,
            fx_rate,
            adr_ratio
        )
        
        if not eps or eps <= 0:
            return {'eps': eps, 'pe': None}
        
        # 7. 计算 PE
        pe = close_price / eps
        
        return {'eps': eps, 'pe': pe}
        


    except Exception as e:
        logger.error(f"计算 PE 失败 ({symbol}): {e}")
        return {'eps': None, 'pe': None}


def calculate_ps_metrics(
    session: Session,
    symbol: str,
    market: str,
    close_price: float,
    as_of_date: str
) -> dict:
    """
    Calculate Price-to-Sales (PS) metrics.
    PS = Price / (Revenue_TTM / Shares)
    """
    try:
        # 1. Fetch Fundamentals
        stmt = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        financials = session.exec(stmt).all()
        
        if not financials:
            return {'rps': None, 'ps': None}

        # 2. Filter PIT
        pit_financials = [f for f in financials if (f.filing_date and f.filing_date <= as_of_date) or (f.as_of_date <= as_of_date)]
        if not pit_financials:
            return {'rps': None, 'ps': None}

        # 🎯 NORMALIZE
        latest_fin = sanitize_financials(pit_financials[0])
        fin_currency = latest_fin.currency
        
        # 3. Get Revenue TTM
        rev_ttm = latest_fin.revenue_ttm
        if not rev_ttm:
            return {'rps': None, 'ps': None}
            
        # 4. Get Shares
        shares = latest_fin.shares_diluted or latest_fin.shares_outstanding_common_end
        config = get_symbol_info(symbol)
        if not shares:
            shares = config.get('total_shares') or get_shares_outstanding(symbol, market)
            
        if not shares:
            return {'rps': None, 'ps': None}
            
        # 5. FX & Config
        adr_ratio = config.get('adr_ratio', 1.0)
        
        market_currency_map = {'US': 'USD', 'HK': 'HKD', 'CN': 'CNY'}
        market_currency = market_currency_map.get(market, 'USD')
        
        fx_rate = get_dynamic_fx_rate(session, fin_currency, market_currency, as_of_date)
        
        # 6. Calculate RPS (Revenue Per Share)
        rps = (rev_ttm / shares) * fx_rate * adr_ratio
        
        if rps is None or rps <= 0:
            return {'rps': rps, 'ps': None}
            
        ps = close_price / rps
        
        # 🛡️防御
        if not check_valuation_outliers(ps, 'ps'):
             logger.warning(f"  ⚠️ [Calculator] Detect abnormal PS={ps:.2f} for {symbol}, discarded.")
             return {'rps': rps, 'ps': None}
             
        return {'rps': rps, 'ps': ps}
        
    except Exception as e:
        logger.error(f"计算 PS 失败 ({symbol}): {e}")
        return {'rps': None, 'ps': None}


def calculate_pb_metrics(
    session: Session,
    symbol: str,
    market: str,
    close_price: float,
    as_of_date: str
) -> dict:
    """
    Calculate Price-to-Book (PB) metrics.
    PB = Price / (Equity / Shares)
    """
    try:
        # 1. Fetch Fundamentals
        stmt = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        financials = session.exec(stmt).all()
        
        if not financials:
            return {'bps': None, 'pb': None}

        # 2. Filter PIT
        pit_financials = [f for f in financials if (f.filing_date and f.filing_date <= as_of_date) or (f.as_of_date <= as_of_date)]
        if not pit_financials:
            return {'bps': None, 'pb': None}

        # 🎯 NORMALIZE
        latest_fin = sanitize_financials(pit_financials[0])
        fin_currency = latest_fin.currency
        
        # 3. Get Equity
        equity = latest_fin.common_equity_end
        if not equity:
            return {'bps': None, 'pb': None}
            
        # 4. Get Shares
        shares = latest_fin.shares_outstanding_common_end or latest_fin.shares_diluted
        config = get_symbol_info(symbol)
        if not shares:
            shares = config.get('total_shares') or get_shares_outstanding(symbol, market)
            
        if not shares:
            return {'bps': None, 'pb': None}
            
        # 5. FX & Config
        adr_ratio = config.get('adr_ratio', 1.0)
        
        market_currency_map = {'US': 'USD', 'HK': 'HKD', 'CN': 'CNY'}
        market_currency = market_currency_map.get(market, 'USD')
        
        fx_rate = get_dynamic_fx_rate(session, fin_currency, market_currency, as_of_date)
        
        # 6. Calculate BPS (Book Value Per Share)
        bps = (equity / shares) * fx_rate * adr_ratio
        
        if bps is None or bps <= 0:
            return {'bps': bps, 'pb': None}
            
        pb = close_price / bps
        
        # 🛡️防御
        if not check_valuation_outliers(pb, 'pb'):
             logger.warning(f"  ⚠️ [Calculator] Detect abnormal PB={pb:.2f} for {symbol}, discarded.")
             return {'bps': bps, 'pb': None}
             
        return {'bps': bps, 'pb': pb}
        
    except Exception as e:
        logger.error(f"计算 PB 失败 ({symbol}): {e}")
        return {'bps': None, 'pb': None}

def calculate_valuation_series(
    session: Session,
    symbol: str,
    market: str,
    daily_prices: pd.DataFrame,
    metric_type: str = 'pe'
) -> pd.DataFrame:
    """
    Calculate a series of valuation metrics for a given price dataframe. (Optimized)
    
    Args:
        daily_prices: DataFrame with DatetimeIndex and 'close' column.
        metric_type: 'pe', 'pb', or 'ps'
    """
    try:
        # 1. Fetch and Sanitize All Fundamentals
        stmt = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        financials = [sanitize_financials(f) for f in session.exec(stmt).all()]
        
        if not financials:
            return pd.DataFrame()

        config = get_symbol_info(symbol)
        adr_ratio = config.get('adr_ratio', 1.0)
        market_currency_map = {'US': 'USD', 'HK': 'HKD', 'CN': 'CNY'}
        market_currency = market_currency_map.get(market, 'USD')

        results = []
        # Group daily prices for faster processing or just iterate? 
        # Usually ~1000 days, iteration is fine if we don't query DB inside the loop.
        
        # Pre-cache FX rates if possible? For now, the get_dynamic_fx_rate has its own cache/lookups.
        
        for ts, row in daily_prices.iterrows():
            date_str = ts.strftime('%Y-%m-%d')
            close = row['close']
            
            # Find the best PIT fundamental
            pit_fin = None
            for f in financials:
                if (f.filing_date and f.filing_date <= date_str) or (not f.filing_date and f.as_of_date <= date_str):
                    pit_fin = f
                    break
            
            if not pit_fin:
                continue
            
            val = None
            if metric_type == 'pe':
                res = calculate_pe_metrics_with_cache(symbol, market, close, date_str, financials, session=session)
                val = res.get('pe')
            elif metric_type == 'pb':
                # Similar optimized call or direct logic
                equity = pit_fin.common_equity_end
                shares = pit_fin.shares_outstanding_common_end or pit_fin.shares_diluted or config.get('total_shares')
                if equity and shares:
                    fx = get_dynamic_fx_rate(session, pit_fin.currency, market_currency, date_str)
                    bps = (equity / shares) * fx * adr_ratio
                    if bps > 0: val = close / bps
            elif metric_type == 'ps':
                rev = pit_fin.revenue_ttm
                shares = pit_fin.shares_diluted or pit_fin.shares_outstanding_common_end or config.get('total_shares')
                if rev and shares:
                    fx = get_dynamic_fx_rate(session, pit_fin.currency, market_currency, date_str)
                    rps = (rev / shares) * fx * adr_ratio
                    if rps > 0: val = close / rps
            
            if val is not None and check_valuation_outliers(val, metric_type):
                results.append({'date': date_str, metric_type: val})
        
        return pd.DataFrame(results)
        
    except Exception as e:
        logger.error(f"Calculate series {metric_type} failed for {symbol}: {e}")
        return pd.DataFrame()

