"""
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ⚠️CRITICAL CONFIGURATION & LOGIC DESCRIPTION - DO NOT DELETE OR MODIFY WITHOUT USER PERMISSION⚠️
# ⚠️关键配置与逻辑说明 - 未经用户专门许可不得删除和修改⚠️
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Financials Fetcher (Global Refactor with Fallback)
==================================================
Unified entry point for fetching financial data across US, HK, and CN markets.

核心策略 (Core Strategies):
-------------------------
1. **US Market (美股)**:
   - Primary: SEC EDGAR (XBRL) -> Database (FinancialFundamentals)
   - Fallback: FMP Cloud -> Yahoo Finance
   - Logic: 优先使用结构化 XBRL 数据，缺失时回退到商业 API。

2. **HK Market (港股)**:
   - Primary: CNINFO Mirror (PDF) -> Local Storage (data/reports/HK) -> PDFFinancialParser
   - Backup: HKEX Website (Selenium crawling)
   - Fallback: AkShare / Yahoo Finance (仅当 PDF 解析彻底失败或无核心数据时)
   - Note: PDF 解析优先，以确保获取最原始、准确的财报数据。

3. **CN Market (A股)**:
   - Primary: CNINFO (PDF) -> Local Storage (data/reports/CN) -> PDFFinancialParser
   - Fallback: AkShare Abstract (摘要接口)
   - Logic: 
     - 自动跳过“业绩预告”、“预盈”、“预亏”等非正式财报 PDF，防止数据污染。
     - 优先解析正式年报/季报。
     - 若 PDF 解析失败或缺失 Revenue/NetIncome 等核心指标，自动回退到 AkShare 摘要数据补全。

关键逻辑 (Key Logic):
--------------------
1. **Smart Merge Strategy (智能合并)**:
   - 函数: `upsert_financials`
   - 规则: 数据库中已有的 `annual` (年报) 数据 **绝对不会** 被 `quarterly` (季报) 数据覆盖。
   - 目的: 保护高质量的经审计年报数据不被因季度波动或数据源质量较差的季报数据污染。

2. **PDF Processing Priority**:
   - 文件排序逻辑: 优先处理 H股 (Priority 1) 和 摘要 (Priority 2)，最后处理 A股正文 (Priority 10)。
   - 目的: 利用 `upsert_financials` 的覆盖特性，确保最完整、质量最高的 A 股正文数据最后写入，从而覆盖之前的 H 股或摘要版数据。

3. **Data Integrity & Protection**:
   - 过滤: 强制跳过包含 "Forecast/业绩预告" 的文件。
   - 校验: 与 `PDFFinancialParser` 配合，通过比率过滤 (`<1000`)、动态年份识别 (`2024年`) 等机制确保提取准确性。

4. **Template & Parsing Rules (模板与解析规则)**:
   - **Bank vs General (银行 vs 通用)**:
     - 逻辑: 在 `PDFFinancialParser` 初始化时通过 `asset_id` (如 601***) 自动检测。
     - 差异: 银行使用专门的关键词集 (Net Interest Income, NPL Ratio 等) 和 Text-Based Parser；通用企业优先使用 Table-Based Parser。
   - **A-Share vs HK-Share (A股 vs 港股)**:
     - A股: 结构较规范，优先尝试表格提取 (Table Extraction)，匹配“营业总收入”等标准会计科目。
     - 港股: 结构多变（中英文混排/繁体），依赖表格提取，且关键词库(`generic_keywords.py`)已内置繁体支持(如 "營業額", "溢利", "資產總值")以应对不同表述。

   - **Unit & Logic (单位与口径)**:
     - **Currency Unit (货币单位)**: 自动扫描表头/行标签提取 "元", "百万", "亿" 等单位并进行数值缩放。
     - **Currency Detection (币种识别)**: 对于港股(H股)，优先使用 PDF 解析出的真实币种(如 "人民币")，而非默认的 HKD，以修复汇率估值偏差。
     - **Consolidated (合并口径)**: 优先选择包含 "合并" / "Consolidated" 的列，权重大于 "母公司" 列，确保只提取上市公司整体财务数据。
     - **EPS Logic (每股收益)**: 特殊处理不进行百万/亿级缩放；支持 "Basic/Diluted" 双重提取；若缺失则尝试通过 `净利润/总股本` 进行校验或补全。

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

import sys
import os
import argparse
import subprocess
import importlib.util

def check_and_install_dependencies():
    """
    Checks for required dependencies and installs them if missing.
    Feature: Self-healing environment.
    """
    REQUIRED_PACKAGES = [
        ("selenium", "selenium"),
        ("webdriver_manager", "webdriver_manager"),
        ("sec-edgar-downloader", "sec_edgar_downloader"),
        ("pdfplumber", "pdfplumber"),
        ("requests", "requests"),
        ("pandas", "pandas"),
        ("sqlmodel", "sqlmodel")
    ]
    
    print("🔍 Checking environment dependencies...")
    for package_name, import_name in REQUIRED_PACKAGES:
        if importlib.util.find_spec(import_name) is None:
            print(f"📦 Installing missing dependency: {package_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
                print(f"✅ Installed {package_name}")
            except Exception as e:
                print(f"❌ Failed to install {package_name}: {e}")
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Watchlist, FinancialFundamentals
# Imports moved to main() to allow dependency check first

# Ensure data directories exist
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/reports")

# Import Parser (Lazy import inside function or here? Here is fine)
# Placeholder, will be imported in main()
PDFFinancialParser = None

def process_pdf_directory(session, symbol: str, directory: str, filter_keyword: str = None):
    """
    Parse all valid PDFs in the directory for the given symbol.
    """
    if not os.path.exists(directory):
        print(f"      ⚠️ Directory not found: {directory}")
        return

    if PDFFinancialParser is None:
        print("      ⚠️ PDFFinancialParser not available.")
        return

    files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
    if filter_keyword:
        files = [f for f in files if filter_keyword in f]
        
    # Sort files: Prefer A-share reports over H-share/Summary ones
    # We want to process H-share/Summaries FIRST, then A-share reports LATER 
    # so A-share data (fuller) overwrites previous ones for the same date.
    def sort_key(f):
        priority = 10
        if "H股" in f: priority = 1
        if "摘要" in f or "Summary" in f: priority = 2
        return (priority, f)
    
    files.sort(key=sort_key)
        
    print(f"      📂 Found {len(files)} PDFs in {directory} to parse (ordered by priority)...")
    
    count = 0
    has_core_metrics = False
    for fname in files:
        fpath = os.path.join(directory, fname)
        
        # Skip Performance Forecasts (Text-based ranges, often empty financials)
        if any(x in fname for x in ["业绩预告", "预盈", "预亏", "Forecast"]):
             print(f"          ⚠️ Skipping {fname} (Performance Forecast)")
             continue

        try:
            print(f"        Parsing {fname}...")
            parser = PDFFinancialParser(pdf_path=fpath, asset_id=symbol)
            data = parser.parse_financials()
            
            if parser.is_summary:
                print(f"          ⚠️ Skipping {fname} (Summary/Abstract report)")
                continue
            # Map fields: parser key -> DB model key
            # report_date -> as_of_date
            # report_type -> report_type
            
            if not data.get('report_date'):
                print("          ⚠️ No report date found, skipping.")
                continue
            
            # DEBUG: Track revenue for 600309 2023-12-31
            if data.get('report_date') == '2023-12-31' and '600309' in symbol:
                print(f"DEBUG [Parser Output]: revenue={data.get('revenue')}, revenue_ttm={data.get('revenue_ttm')}, operating_profit={data.get('operating_profit')}")
                print(f"DEBUG [Parser Output]: ALL KEYS: {list(data.keys())}")
                
            db_record = {
                "symbol": symbol,
                "as_of_date": data['report_date'],
                "report_type": data.get('report_type', 'annual'),
                "data_source": "pdf-parser",
                "currency": data.get('currency') or ("CNY" if symbol.startswith('CN') else ("HKD" if symbol.startswith('HK') else "USD")), # Prioritize parsed currency
                
                # Income - Prefer pre-mapped TTM fields if present
                "revenue_ttm": data.get('revenue_ttm') or data.get('revenue'),
                "net_income_ttm": data.get('net_income_ttm') or data.get('net_profit') or data.get('net_income_common_ttm'),
                "net_income_common_ttm": data.get('net_income_common_ttm') or data.get('net_profit'),
                "gross_profit_ttm": data.get('gross_profit_ttm') or data.get('gross_profit'),
                "operating_profit_ttm": data.get('operating_profit_ttm') or data.get('operating_profit'),
                "ebit_ttm": data.get('ebit_ttm') or data.get('ebit'),
                "r_and_d_expense_ttm": data.get('r_and_d_expense_ttm') or data.get('rd_expense'),
                "interest_expense_ttm": data.get('interest_expense_ttm') or data.get('interest_expense'),
                "non_recurring_profit_ttm": data.get('non_recurring_profit_ttm'),
                "eps": data.get('eps'),
                "eps_diluted": data.get('eps_diluted'),
                "shares_diluted": data.get('shares_diluted'),
                "filing_date": data.get('filing_date'),
                
                # Balance Sheet
                "total_assets": data.get('total_assets'),
                "total_liabilities": data.get('total_liabilities'),
                "total_debt": data.get('total_debt'),
                "cash_and_equivalents": data.get('cash_and_equivalents'),
                "common_equity_begin": data.get('common_equity_begin'),
                "common_equity_end": data.get('common_equity_end'),
                "accounts_receivable_end": data.get('accounts_receivable_end') or data.get('accounts_receivable'),
                "inventory_end": data.get('inventory_end') or data.get('inventory'),
                "accounts_payable_end": data.get('accounts_payable_end') or data.get('accounts_payable'),
                
                # Bank Metrics (will be NULL for non-banks)
                "npl_balance": data.get('npl_balance'),
                "npl_ratio": data.get('npl_ratio'),
                "provision_coverage": data.get('provision_coverage'),
                "core_tier1_ratio": data.get('core_tier1_ratio'),
                "net_interest_income": data.get('net_interest_income'),
                "net_fee_income": data.get('net_fee_income'),
                "provision_expense": data.get('provision_expense'),
                "total_loans": data.get('total_loans'),
                "loan_loss_allowance": data.get('loan_loss_allowance'),
                
                # Dividend & Cashflow
                "dividend_amount": data.get('dividend_amount') or data.get('dividend') or data.get('dividends_paid'),
                "dividend_per_share": data.get('dividend_per_share'),
                "shares_outstanding_common_end": data.get('shares_outstanding_common_end') or data.get('shares_outstanding'),
                "operating_cashflow_ttm": data.get('operating_cashflow_ttm') or data.get('operating_cashflow'),
                "free_cashflow_ttm": data.get('free_cashflow_ttm'),
                "capex_ttm": data.get('capex_ttm'),
                "non_recurring_profit_ttm": data.get('non_recurring_profit_ttm'),
                "short_term_debt": data.get('short_term_debt'),
                "long_term_debt": data.get('long_term_debt'),
                
                # Bank Specific
                "total_loans": data.get('total_loans'),
                "loan_loss_allowance": data.get('loan_loss_allowance'),
                "npl_balance": data.get('npl_balance'),
                "npl_ratio": data.get('npl_ratio'),
                "provision_coverage": data.get('provision_coverage'),
                "core_tier1_ratio": data.get('core_tier1_ratio'),
                "net_interest_income": data.get('net_interest_income'),
                "net_fee_income": data.get('net_fee_income'),
                "provision_expense": data.get('provision_expense'),
                "short_term_debt": data.get('short_term_debt'),
                "long_term_debt": data.get('long_term_debt'),
                
                "common_equity_begin": data.get('common_equity_begin'),
                "common_equity_end": data.get('common_equity_end'),
            }
            
            # Check if this specific record has any actual financial data
            core_keys = [
                "revenue_ttm", "net_income_ttm", "total_assets", "total_liabilities",
                "operating_cashflow_ttm", "gross_profit_ttm", "operating_profit_ttm", "eps"
            ]
            has_data = any(db_record.get(k) is not None for k in core_keys)
            
            if has_data:
                upsert_financials(session, db_record)
                session.commit() # Forced commit per record to ensure visibility
                count += 1
            else:
                print(f"          ⚠️ Skipping {fname} (No core metrics found)")
            if not has_core_metrics:
                core_keys = [
                    "revenue_ttm", "net_income_ttm", "total_assets", "total_liabilities",
                    "operating_cashflow_ttm", "gross_profit_ttm", "operating_profit_ttm"
                ]
                has_core_metrics = any(db_record.get(k) is not None for k in core_keys)
            
        except Exception as e:
            print(f"        ❌ Parse Error {fname}: {e}")
            
    print(f"      ✅ Successfully parsed {count} reports.")
    return {"parsed": count, "has_core_metrics": has_core_metrics}

def upsert_financials(session, data):
    """
    Insert or Update financial records in DB.
    Implements Smart Merge: Prevents Quarterly overwriting Annual.
    """
    if not data: return
    
    if data.get('as_of_date') == '2023-12-31' and '600309' in data.get('symbol', ''):
        print(f"DEBUG: Upserting 600309 for 2023-12-31. Revenue: {data.get('revenue_ttm')}")

    # Separate Recording: Key by (symbol, as_of_date, data_source)
    # This prevents different sources from overwriting each other.
    existing = session.exec(select(FinancialFundamentals).where(
        FinancialFundamentals.symbol == data['symbol'],
        FinancialFundamentals.as_of_date == data['as_of_date'],
        FinancialFundamentals.data_source == data.get('data_source')
    )).first()
    
    if existing:
        existing_type = getattr(existing, 'report_type', '')
        new_type = data.get('report_type', '')
        
        # Protective logic: Annual > Quarterly
        if existing_type == 'annual' and new_type == 'quarterly':
            return
            
        print(f"   🔄 Updating DB {data['symbol']} {data['as_of_date']}...")
        for k, v in data.items():
            # Only update if NEW value is not None, OR if existing value is None
            # This prevents a failed parse (None) from overwriting a previously successful parse
            existing_v = getattr(existing, k, None)
            if v is not None:
                setattr(existing, k, v)
    else:
        print(f"   ➕ Inserting DB {data['symbol']} {data['as_of_date']}...")
        new_record = FinancialFundamentals(**data)
        if data.get('capex_ttm'):
            print(f"      [PERSIST] capex_ttm assigned: {new_record.capex_ttm}")
        session.add(new_record)

def main():
    # 1. Environment Check & Self-Heal
    check_and_install_dependencies()
    
    # 2. Lazy Import of Fetchers (Safe now)
    global fetch_us_xbrl_data, fetch_hk_pdf, fetch_cn_pdf, fetch_yahoo_financials, fetch_fmp_financials, fetch_akshare_cn_financials_abstract, fetch_akshare_hk_financials, PDFFinancialParser
    
    from backend.fetchers.us_fetcher import fetch_us_xbrl_data
    from backend.fetchers.hk_fetcher import fetch_hk_pdf
    from backend.fetchers.cn_fetcher import fetch_cn_pdf
    from backend.fetchers.legacy_fetcher import (
        fetch_yahoo_financials, 
        fetch_fmp_financials,
        fetch_akshare_cn_financials_abstract,
        fetch_akshare_hk_financials
    )
    
    try:
        from backend.parsers.pdf_parser import PDFFinancialParser
    except ImportError:
        print("⚠️ Failed to import PDFFinancialParser even after check.")
        PDFFinancialParser = None

    parser = argparse.ArgumentParser(description='Unified Financials Fetcher')
    parser.add_argument('--market', type=str, choices=['CN', 'HK', 'US', 'ALL'], help='Market scope')
    parser.add_argument('--symbol', type=str, help='Specific symbol (e.g. US:STOCK:AAPL)')
    args = parser.parse_args()
    
    target_market = args.market
    target_symbol = args.symbol

    # Interactive Mode
    if not target_market and not target_symbol:
        print("\n" + "="*50)
        print("📊 Select Market to Fetch")
        print("="*50)
        print("  1. CN (A-Share) -> PDF Download + Legacy DB Fetch")
        print("  2. HK (Hong Kong) -> PDF Download + Legacy DB Fetch")
        print("  3. US (United States) -> SEC XBRL (Fallback to FMP/Yahoo)")
        print("  0. ALL Markets")
        print("="*50)
        c = input("Choice [0]: ").strip()
        if c == '1': target_market = 'CN'
        elif c == '2': target_market = 'HK'
        elif c == '3': target_market = 'US'
        else: target_market = 'ALL'

    print(f"\n🚀 Starting Fetch (Market: {target_market}, Symbol: {target_symbol or 'ALL'})...")

    with Session(engine) as session:
        # Build list of stocks
        query = select(Watchlist)
        if target_symbol:
            query = query.where(Watchlist.symbol == target_symbol)
        elif target_market != 'ALL':
            query = query.where(Watchlist.market == target_market)
            
        stocks = session.exec(query).all()
        total = len(stocks)
        print(f"📋 Processing {total} assets...")
        
        for idx, stock in enumerate(stocks, 1):
            # Skip non-equity assets (Index, Crypto, ETF, Trust, etc.)
            if any(x in stock.symbol for x in [':INDEX:', ':CRYPTO:', ':ETF:', ':TRUST:', ':BOND:']):
                continue
                
            print(f"\n[{idx}/{total}] Processing {stock.symbol} ({stock.name})...")
            
            try:
                # === DISPATCH ===
                # === MARKET ROUTING STRATEGY ===
                if stock.market == 'US':
                    print(f"   [US] Fetching structural data from SEC EDGAR (XBRL)...")
                    data_list = fetch_us_xbrl_data(stock.symbol)
                    
                    if not data_list:
                        print("   ⚠️ No XBRL data found. Switching to Legacy Channels (FMP/Yahoo)...")
                        data_list = fetch_fmp_financials(stock.symbol, market='US')
                        if not data_list:
                            data_list = fetch_yahoo_financials(stock.symbol, market='US', report_type='annual')
                            data_list.extend(fetch_yahoo_financials(stock.symbol, market='US', report_type='quarterly'))
                    
                    if data_list:
                        data_list.sort(key=lambda x: x['as_of_date'], reverse=True)
                        for d in data_list: upsert_financials(session, d)
                        session.commit()
                        print(f"   ✅ Saved {len(data_list)} records to DB (SEC/Legacy).")

                elif stock.market == 'CN':
                    print(f"   [CN] Fetching PDF reports from CNINFO...")
                    fetch_cn_pdf(stock.symbol, "data/reports")
                    
                    pdf_dir = os.path.join("data/reports", "CN", stock.symbol.split(':')[-1])
                    records_parsed = 0
                    parsed_has_core = False
                    if os.path.exists(pdf_dir):
                        result = process_pdf_directory(session, stock.symbol, pdf_dir)
                        records_parsed = result.get("parsed", 0)
                        parsed_has_core = result.get("has_core_metrics", False)
                        if records_parsed > 0: session.commit()
                    
                    if records_parsed == 0 or not parsed_has_core:
                        if records_parsed == 0:
                            print(f"   [CN] ⚠️ No data from PDF. Falling back to AkShare Abstract...")
                        else:
                            print(f"   [CN] ⚠️ Parsed PDF but missing core metrics. Falling back to AkShare Abstract...")
                        ak_data = fetch_akshare_cn_financials_abstract(stock.symbol)
                        for entry in ak_data: upsert_financials(session, entry)
                        session.commit()

                elif stock.market == 'HK':
                    # 1. Primary: CNINFO (Faster/Native HTTP)
                    print(f"   [HK] [Step 1] Fetching PDF from CNINFO mirror...")
                    fetch_cn_pdf(stock.symbol, "data/reports")
                    
                    hk_code = stock.symbol.split(':')[-1]
                    pdf_dir = os.path.join("data/reports", "HK", hk_code)
                    
                    # 2. Backup: HKEX (Selenium)
                    if not os.path.exists(pdf_dir) or not os.listdir(pdf_dir):
                        print(f"   [HK] [Step 2] CNINFO mirror empty. Launching HKEX Backup (Selenium)...")
                        fetch_hk_pdf(stock.symbol, "data/reports")
                    
                    records_parsed = 0
                    parsed_has_core = False
                    if os.path.exists(pdf_dir):
                        result = process_pdf_directory(session, stock.symbol, pdf_dir)
                        records_parsed = result.get("parsed", 0)
                        parsed_has_core = result.get("has_core_metrics", False)
                        if records_parsed > 0: session.commit()
                    
                    # 3. Fallback: AkShare/Yahoo Summary
                    if records_parsed == 0 or not parsed_has_core:
                        if records_parsed == 0:
                            print(f"   [HK] [Step 3] PDF extraction failed. Fetching summary from AkShare...")
                        else:
                            print(f"   [HK] [Step 3] PDF parsed but core metrics missing. Fetching summary from AkShare...")
                        ak_data = fetch_akshare_hk_financials(stock.symbol)
                        for entry in ak_data: upsert_financials(session, entry)
                        session.commit()
                
                else:
                    print(f"   [WLD] Generic market fallback: Yahoo Finance...")
                    yahoo_data = fetch_yahoo_financials(stock.symbol)
                    for entry in yahoo_data: upsert_financials(session, entry)
                    session.commit()
                    
            except Exception as e:
                print(f"   ❌ Error processing {stock.symbol}: {e}")
                
    print("\n✅ All tasks completed.")

if __name__ == "__main__":
    main()
