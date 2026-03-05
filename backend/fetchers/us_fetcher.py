import os
import re
import pandas as pd
from datetime import datetime

try:
    from sec_edgar_downloader import Downloader
    SEC_AVAILABLE = True
except ImportError:
    SEC_AVAILABLE = False

def fetch_us_xbrl_data(symbol: str, base_dir: str = "sec-edgar-filings", mode: str = 'inc'):
    """
    Download and parse US 10-K and 10-Q filings for a symbol.
    Returns: List[Dict] matching FinancialFundamentals schema.
    """
    if not SEC_AVAILABLE:
        print("   [US] ❌ sec-edgar-downloader not installed.")
        return []

    ticker = symbol.split(':')[-1]
    
    # 1. Download
    print(f"   [US] Downloading 10-K and 10-Q filings for {ticker}...")
    try:
        # Use a generic user agent as required by SEC
        dl = Downloader("VERA-AI", "admin@vera.com", base_dir)
        # Determine limits based on mode
        limit_k = 1 if mode == 'inc' else 10
        limit_q = 2 if mode == 'inc' else 20
        
        # Download 10-Ks and 10-Qs
        dl.get("10-K", ticker, limit=limit_k)
        dl.get("10-Q", ticker, limit=limit_q)
    except Exception as e:
        print(f"   [US] Download failed: {e}")
        return []

    # 2. Define standard tags inside the function for isolation
    TAG_MAP = {
        # Income Statement
        "revenue_ttm": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "TotalRevenuesAndOtherIncome", "InterestAndDividendIncomeOperating"],
        "gross_profit_ttm": ["GrossProfit"],
        "operating_profit_ttm": ["OperatingIncomeLoss", "IncomeLossFromOperatingActivitiesBeforeIncomeTaxExpenseBenefit", "OperatingProfitLoss"],
        "ebit_ttm": ["OperatingIncomeLoss", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
        "net_income_ttm": ["NetIncomeLoss", "ProfitLoss"],
        "net_income_common_ttm": ["NetIncomeLossAvailableToCommonStockholdersBasic", "NetIncomeLoss"],
        "eps": ["EarningsPerShareBasic"],
        "eps_diluted": ["EarningsPerShareDiluted"],
        "r_and_d_expense_ttm": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
        "interest_expense_ttm": ["InterestExpense", "InterestExpenseDebt"],
        
        # Balance Sheet
        "total_assets": ["Assets"],
        "total_liabilities": ["Liabilities"],
        "common_equity_end": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "cash_and_equivalents": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"],
        "total_debt": ["DebtInstrumentCarryingAmount", "LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"],
        "accounts_receivable_end": ["AccountsReceivableNetCurrent", "AccountsReceivableNet", "ReceivablesNetCurrent"],
        "inventory_end": ["InventoryNet", "InventoryNetExcludingRawMaterials"],
        "accounts_payable_end": ["AccountsPayableCurrent", "AccountsPayable"],
        
        # Cash Flow
        "operating_cashflow_ttm": ["NetCashProvidedByUsedInOperatingActivities"],
        "capex_ttm": ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpenditures", "PaymentsToAcquireProductiveAssets"],
        "dividends_paid_cashflow": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
        
        # Bank Specifics
        "net_interest_income": ["InterestIncomeExpenseAfterProvisionForLoanLoss", "InterestIncomeExpenseNet", "NetInterestIncome"],
        "npl_ratio": ["NonperformingAssetsToTotalAssetsRatio"], 
    }

    all_results = []
    forms = ["10-K", "10-Q"]
    
    # Path where downloader saves: {base_dir}/sec-edgar-filings/{ticker}/{form}/
    # Check if sec-edgar-filings is already in base_dir or if we need to append it
    search_root = os.path.join(base_dir, "sec-edgar-filings", ticker)
    if not os.path.exists(search_root):
        # Fallback to direct path check
        search_root = os.path.join(base_dir, ticker)

    for form in forms:
        filing_path = os.path.join(search_root, form)
        if not os.path.exists(filing_path):
            continue
            
        for folder in os.listdir(filing_path):
            full_sub_path = os.path.join(filing_path, folder, "full-submission.txt")
            if not os.path.exists(full_sub_path): continue
            
            try:
                with open(full_sub_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Extract Period End Date
                date_match = re.search(r'<(?:dei:)?DocumentPeriodEndDate[^>]*>(\d{4}-\d{2}-\d{2})</', content)
                if not date_match:
                     continue
                date_str = date_match.group(1)

                entry = {
                    "symbol": symbol,
                    "as_of_date": date_str,
                    "report_type": "annual" if form == "10-K" else "quarterly",
                    "data_source": "sec-xbrl",
                    "currency": "USD"
                }
                
                # Extract Fields
                for field, tags in TAG_MAP.items():
                    val = _extract_max_val(content, tags, date_str)
                    if val is not None:
                        entry[field] = val
                
                # Basic validation
                if entry.get("revenue_ttm") or entry.get("net_income_ttm"):
                     all_results.append(entry)
                     
            except Exception as e:
                print(f"      [US] Err parsing {folder}: {e}")
                
    return all_results

def _extract_max_val(content, tags, target_date):
    """
    Smarter XBRL extraction that filters candidate values by their context date.
    Only values matching the targeted 'target_date' are considered.
    """
    # 1. First, build a map of Context ID -> End Date
    # Look for: <xbrli:context id="ctx_1"> ... <xbrli:endDate>2024-12-31</xbrli:endDate> ... </xbrli:context>
    context_map = {}
    context_matches = re.finditer(r'<xbrli:context id="([^"]+)">.*?(?:<xbrli:endDate>|<xbrli:instant>)([\d-]{10})', content, re.DOTALL)
    for m in context_matches:
        context_map[m.group(1)] = m.group(2)
        
    candidates = []
    for tag in tags:
        # Pattern 1: Standard XML
        p1 = rf'<(?:us-gaap:)?{tag}\s+[^>]*contextRef="([^"]+)"[^>]*>([\d\.,\(\)\s\-]+)</'
        # Pattern 2: Inline XBRL
        p2 = rf'<ix:[^>]*name="(?:us-gaap:)?{tag}"[^>]*contextRef="([^"]+)"[^>]*>([\d\.,\(\)\s\-]+)</ix:'
        
        matches = re.findall(p1, content) + re.findall(p2, content)
        
        for ctx_id, val_str in matches:
            # FILTER 1: Date Alignment
            # The context date must match exactly (or close enough? usually exact)
            ctx_date = context_map.get(ctx_id)
            if ctx_date and ctx_date != target_date:
                continue
                
            # FILTER 2: Segment/Member filter (ignore non-consolidated)
            if any(x in ctx_id for x in ['Member', 'Axis', 'Segment', 'Domain']):
                continue
                
            # Clean number
            val_str = val_str.strip().replace(',', '')
            if val_str.startswith('(') and val_str.endswith(')'):
                val_str = '-' + val_str[1:-1]
            try:
                v = float(val_str)
                candidates.append(v)
            except: pass
            
    if candidates:
        # Heuristic: largest absolute value usually consolidated total
        return max(candidates, key=abs)
    return None
