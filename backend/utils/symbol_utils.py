"""
Symbol conversion utilities for market data fetching and storage.

This module centralizes all symbol format conversions:
- Database normalization (for ETL and storage)
- API format conversion (for data fetching)
- Market detection (for routing logic)
"""


def normalize_symbol_db(symbol: str, market: str) -> str:
    """
    Standardize symbols for Database storage/lookup.
    
    Used by ETL Service and database operations.
    
    Args:
        symbol: Raw symbol (e.g., "TSLA.OQ", "00700.HK", "800000")
        market: Market type ("US", "HK", "CN")
    
    Returns:
        Normalized symbol for database storage
        
    Examples:
        >>> normalize_symbol_db("TSLA.OQ", "US")
        "TSLA"
        >>> normalize_symbol_db("00700.HK", "HK")
        "00700.HK"
        >>> normalize_symbol_db("600519.SH", "CN")
        "600519.SH"
        >>> normalize_symbol_db("800000", "HK")
        "HSI"  # Alias mapping applied
    """
    if not symbol:
        return symbol
    
    symbol = symbol.upper().strip()
    
    # ✅ 应用别名映射（防止重复数据）
    from symbols_config import get_canonical_symbol
    symbol = get_canonical_symbol(symbol)
    
    if market == 'US':
        # Remove common US exchange suffixes
        for suffix in ['.OQ', '.N', '.K', '.O', '.AM']:
            if symbol.endswith(suffix):
                return symbol.replace(suffix, '')
        
        # Generic split if dot exists
        if '.' in symbol:
            return symbol.split('.')[0]
    
    # HK/CN: Keep suffix
    return symbol


def to_akshare_us_symbol(symbol: str, for_minute: bool = False) -> str:
    """
    Convert symbol to AkShare US format.
    
    Used by DataFetcher for API calls.
    
    Args:
        symbol: Input symbol (e.g., "TSLA", "105.MSFT", "TSM")
        for_minute: True for minute data format, False for daily
    
    Returns:
        AkShare-compatible symbol format
        
    Examples:
        >>> to_akshare_us_symbol("TSLA", for_minute=True)
        "105.tsla"
        >>> to_akshare_us_symbol("105.MSFT", for_minute=False)
        "MSFT"
        >>> to_akshare_us_symbol("TSM", for_minute=True)
        "106.tsm"
    """
    if for_minute:
        # Minute data: keep prefix, lowercase
        if symbol.startswith("105.") or symbol.startswith("106."):
            return symbol.lower()
        
        # Special case: TSM
        if symbol.upper() == "TSM":
            return "106.tsm"
        
        # Default: add 105 prefix
        return "105." + symbol.lower()
    else:
        # Daily data: uppercase, remove prefix
        if symbol.startswith("105.") or symbol.startswith("106."):
            return symbol.split(".")[1].upper()
        
        return symbol.upper()


def get_market(symbol: str) -> str:
    """
    Detect market type from symbol format.
    
    Used by DataFetcher to route to correct API.
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Market type: "US", "HK", "CN", or "Other"
        
    Examples:
        >>> get_market("TSLA")
        "Other"  # Ambiguous without suffix
        >>> get_market("TSLA.OQ")
        "US"
        >>> get_market("00700.HK")
        "HK"
        >>> get_market("600519.SH")
        "CN"
        >>> get_market("^SPX")
        "US"
    """
    symbol = symbol.upper()
    
    # AkShare prefixes
    if symbol.startswith("105.") or symbol.startswith("106."):
        return "US"
    
    # US indices
    if symbol.startswith("^"):
        return "US"
    
    # HK suffix
    if symbol.endswith(".HK"):
        return "HK"
    
    # CN suffixes
    if symbol.endswith(".SH") or symbol.endswith(".SZ"):
        return "CN"
    
    # US exchange suffixes
    if any(symbol.endswith(s) for s in [".OQ", ".N", ".AM", ".O", ".K"]):
        return "US"
    
    # Ambiguous
    return "Other"


def to_yfinance_symbol(symbol: str, market: str) -> str:
    """
    Convert symbol to yfinance format.
    
    Args:
        symbol: Input symbol
        market: Market type
    
    Returns:
        yfinance-compatible symbol
        
    Examples:
        >>> to_yfinance_symbol("00700", "HK")
        "0700.HK"
        >>> to_yfinance_symbol("600519", "CN")
        "600519.SS"
    """
    if market == "HK":
        # yfinance HK: remove leading zeros, add .HK
        if not symbol.endswith(".HK"):
            symbol = symbol.lstrip("0") + ".HK"
        return symbol
    
    elif market == "CN":
        # yfinance CN: .SS for Shanghai, .SZ for Shenzhen
        if symbol.endswith(".SH"):
            return symbol.replace(".SH", ".SS")
        elif symbol.endswith(".SZ"):
            return symbol  # Already correct
        elif symbol.startswith("6"):
            return symbol + ".SS"  # Shanghai
        else:
            return symbol + ".SZ"  # Shenzhen
    
    # US: use as-is
    return symbol


def normalize_symbol_for_watchlist(symbol: str) -> tuple[str, str]:
    """
    标准化用户输入的股票代码，用于添加自选股
    
    统一处理用户输入，确保与DataFetcher使用的标准化逻辑一致
    
    Args:
        symbol: 用户输入的股票代码
        
    Returns:
        (final_symbol, market) 元组
        
    Examples:
        >>> normalize_symbol_for_watchlist("600519")
        ("600519.SH", "CN")
        
        >>> normalize_symbol_for_watchlist("600519.sh")
        ("600519.SH", "CN")
        
        >>> normalize_symbol_for_watchlist("00700")
        ("00700.HK", "HK")
        
        >>> normalize_symbol_for_watchlist("00700.hk")
        ("00700.HK", "HK")
        
        >>> normalize_symbol_for_watchlist("tsla")
        ("TSLA", "US")
        
        >>> normalize_symbol_for_watchlist("TSLA")
        ("TSLA", "US")
    """
    if not symbol:
        raise ValueError("股票代码不能为空")
    
    symbol = symbol.strip()
    s = symbol.lower()
    
    # 1. CN市场检测和标准化
    if s.endswith(".sh") or s.endswith(".sz"):
        # 已有后缀，转大写
        market = "CN"
        final_symbol = symbol.upper()
        
    elif s.isdigit() and len(s) == 6:
        # 6位数字，推断为A股
        market = "CN"
        # 根据前缀添加后缀
        if s.startswith("6"):
            final_symbol = f"{s}.SH".upper()
        elif s.startswith(("0", "3")):
            final_symbol = f"{s}.SZ".upper()
        elif s.startswith(("4", "8")):
            # 科创板/新三板
            final_symbol = f"{s}.SZ".upper()
        else:
            raise ValueError(f"无法识别的A股代码: {symbol}")
    
    # 2. HK市场检测和标准化
    elif s.endswith(".hk"):
        # 已有后缀，转大写
        market = "HK"
        final_symbol = symbol.upper()
        
    elif s.isdigit() and len(s) == 5:
        # 5位数字，推断为港股
        market = "HK"
        final_symbol = f"{s}.HK".upper()
    
    # 3. US市场检测和标准化
    elif s.startswith("105.") or s.startswith("106."):
        # AkShare格式的美股
        market = "US"
        final_symbol = symbol.upper()
        
    elif s.startswith("^"):
        # 美股指数
        market = "US"
        final_symbol = symbol.upper()
        
    elif any(s.endswith(suffix) for suffix in [".oq", ".n", ".am", ".o", ".k"]):
        # 美股交易所后缀
        market = "US"
        final_symbol = symbol.upper()
    
    else:
        # 4. 默认处理
        # 检查是否为ASCII（排除中文）
        if not symbol.isascii():
            raise ValueError("请输入正确的股票代码 (如 600519 或 AAPL)")
        
        # 默认为美股
        market = "US"
        final_symbol = symbol.upper()
    
    # 5. 最终标准化（确保与DataFetcher一致）
    final_symbol = normalize_symbol_db(final_symbol, market)
    
    return final_symbol, market

