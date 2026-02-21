
import logging
from typing import Optional
from backend.models import FinancialFundamentals
from backend.symbols_config import get_symbol_info

logger = logging.getLogger("Sanitizer")

def sanitize_financials(f: FinancialFundamentals) -> FinancialFundamentals:
    """
    Sanitize and fix common errors in financial fundamentals data.
    Handle unit errors, missing fields, and logic inconsistencies.
    """
    if not f:
        return f
        
    config = get_symbol_info(f.symbol)
    
    # 1. Equity Fallback (for HK Banks/Conslomerates where PDF parser might miss 'Common Equity')
    if f.common_equity_end is None and config.get('equity_fallback'):
        if f.total_assets and f.total_liabilities:
             f.common_equity_end = f.total_assets - f.total_liabilities
             logger.info(f"  🔍 [Sanitizer] Deriving equity from Assets-Liabilities for {f.symbol} ({f.as_of_date})")

    # 2. Logic Consistency: Shares vs Market Cap
    # If shares are missing but config has them, fill it
    if (not f.shares_outstanding_common_end or f.shares_outstanding_common_end == 0) and config.get('total_shares'):
         f.shares_outstanding_common_end = config.get('total_shares')
         logger.info(f"  🔍 [Sanitizer] Using config shares for {f.symbol} ({f.as_of_date})")

    # 3. Unit Detection (Protection against B/M/K confusion)
    # Strategy: Total Assets should be in a reasonable range (usually > 1M for listed companies)
    # If Total Assets exists but is < 1000, it's likely scaling error (e.g. Billions represented as units)
    # This is a bit risky, but we can target specific fields.
    
    # 4. Outlier Clamping for TTM fields
    # Example: net_income_ttm > total_assets? Very unlikely for 99% of stocks.
    
    return f

def check_valuation_outliers(val: float, val_type: str) -> bool:
    """
    Final defense line: Check if a calculated Valuation metric is insane.
    Returns False if outlier.
    """
    if val is None or val <= 0:
        return False
        
    thresholds = {
        'pe': (0.01, 1000),      # PE > 1000 is usually data error or near-zero profit
        'pb': (0.001, 80),       # PB > 80 is almost always wrong equity recognition
        'ps': (0.001, 60),       # PS > 60 (unless SaaS/Tech)
        'dividend_yield': (0, 50) # Yield > 50% is suspect
    }
    
    low, high = thresholds.get(val_type.lower(), (0, float('inf')))
    return low <= val <= high
