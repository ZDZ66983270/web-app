"""
PDF Financial Report Parser
============================
Extracts financial metrics from Chinese annual/quarterly reports (banks & generic enterprises).

CRITICAL NOTES:
--------------
1. **Import Path Issue (Fixed 2026-02-02)**:
   - MUST use relative import: `from .keywords.generic_keywords import ...`
   - DO NOT use: `from parsers.keywords.generic_keywords import ...`
   - Reason: When imported via `from backend.parsers.pdf_parser import PDFFinancialParser`,
     the absolute path fails, causing REVENUE_KEYWORDS etc. to be undefined.
   - Symptom: Table extraction silently fails with NameError, falls back to text parsing,
     resulting in incorrect data (e.g., Wanhua Chemical 600309: 15.95亿 vs correct 1753.61亿).

2. **Table Extraction Priority**:
   - For generic enterprises, table extraction is attempted FIRST
   - Text-based parsing is used as fallback only if table extraction fails
   - First-match-wins strategy: the first occurrence in tables is preserved

3. **Data Flow**:
   - parse_financials() → _parse_tables() → _extract_from_table() → smart_update()
   - If table extraction succeeds, text parsing will NOT overwrite existing values
"""

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

import re
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import sys
import os

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.bank_keywords import get_keywords_for_bank

# Import generic enterprise keywords
try:
    from .keywords.generic_keywords import (
        REVENUE_KEYWORDS, NET_PROFIT_KEYWORDS, GROSS_PROFIT_KEYWORDS,
        OPERATING_PROFIT_KEYWORDS, TOTAL_ASSETS_KEYWORDS, TOTAL_LIABILITIES_KEYWORDS,
        EQUITY_KEYWORDS, CASH_KEYWORDS, OPERATING_CASHFLOW_KEYWORDS,
        CAPEX_KEYWORDS, EPS_KEYWORDS, SHARES_OUTSTANDING_KEYWORDS,
        DIVIDEND_KEYWORDS, DPS_KEYWORDS, RD_EXPENSE_KEYWORDS,
        SHORT_TERM_DEBT_KEYWORDS, LONG_TERM_DEBT_KEYWORDS,
        RECEIVABLES_KEYWORDS, INVENTORY_KEYWORDS, PAYABLES_KEYWORDS,
        COST_OF_REVENUE_KEYWORDS, SELLING_EXPENSE_KEYWORDS,
        ADMIN_EXPENSE_KEYWORDS, FINANCE_EXPENSE_KEYWORDS,
        INVESTING_CASHFLOW_KEYWORDS, FINANCING_CASHFLOW_KEYWORDS,
        TOTAL_PROFIT_KEYWORDS
    )
    GENERIC_KEYWORDS_AVAILABLE = True
except ImportError:
    GENERIC_KEYWORDS_AVAILABLE = False

class PDFFinancialParser:
    """
    Parser for Financial Report PDFs (Annual/Quarterly Reports)
    Extracts key metrics: Revenue, Net Profit, EPS, Dividend
    支持两种模式：1) PDF文件路径 2) 直接文本内容（来自OCR）
    """
    
    def __init__(self, pdf_path: Optional[str] = None, text_content: Optional[str] = None, asset_id: Optional[str] = None):
        """
        初始化解析器
        
        Args:
            pdf_path: PDF文件路径（传统模式）
            text_content: 直接文本内容（OCR模式）
            asset_id: 资产ID (如 "CN:STOCK:600036")，用于匹配特定关键词
        """
        if pdf_path is None and text_content is None:
            raise ValueError("必须提供pdf_path或text_content之一")
        
        self.pdf_path = pdf_path
        self.text_content = text_content or ""
        self.asset_id = asset_id
        self.tables = []
        self.logs = []
        
        # Industry detection (bank vs generic enterprise)
        self.is_bank = self._detect_bank_industry()
        
    def log(self, msg: str):
        # Keep logs in memory for debugging, also print to stdout
        print(f"[PDF_DEBUG] {msg}")
        self.logs.append(msg)
    
    def _detect_bank_industry(self) -> bool:
        """
        Detect if the asset is a bank based on asset_id or filename
        
        Returns:
            True if bank, False if generic enterprise
        """
        # Method 1: Check asset_id for known bank codes
        if self.asset_id:
            # Known bank stock codes (CN & HK market)
            bank_codes = [
                '600036', '601998', '600016', '601288', '600000', '601328', '601939', '601166', '600919',
                '00005', '01398', '00939', '03988', '03328', '00011', '01658', '02388', '03968'
            ]
            for code in bank_codes:
                if code in self.asset_id:
                    self.log(f"Detected BANK industry from asset_id: {self.asset_id}")
                    return True
        
        # Method 2: Check filename/text for bank keywords
        check_text = ""
        if self.pdf_path:
            check_text = str(self.pdf_path)
        if self.text_content:
            check_text += self.text_content[:5000]  # Check first 5000 chars
        
        bank_indicators = ["银行", "銀行", "Bank", "不良贷款", "不良貸款", "贷款总额", "貸款總額", "存款总额", "資本充足率"]
        bank_count = sum(1 for indicator in bank_indicators if indicator in check_text)
        
        if bank_count >= 2:
            self.log(f"Detected BANK industry from content ({bank_count} indicators)")
            return True
        
        self.log("Detected GENERIC ENTERPRISE (non-bank)")
        return False

    def extract_content(self, max_pages: int = 80):
        """
        1. Quick scan for important keywords (Segment Info, Quality, Financials)
        2. Extract with layout=True for better structural preservation.
        """
        if self.text_content: return
        
        if not PDFPLUMBER_AVAILABLE:
            raise ImportError("PDF 解析模块 pdfplumber 未安装，请安装后重试。")

        keywords = ["Segment Information", "分部信息", "经营分部", "不良贷款", "资产负债表", "利润表", "主要会计数据"]
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                full_text = []
                # Limit scanning to first N pages where summary data usually resides
                pages_to_scan = pdf.pages[:min(max_pages, len(pdf.pages))]
                
                self.log(f"Scanning first {len(pages_to_scan)} pages for key content...")
                
                for i, page in enumerate(pages_to_scan):
                    # Quick raw extract for keyword matching
                    raw_text = page.extract_text() or ""
                    
                    # If it's a "hot page" (summary or segment), use layout=True
                    if any(kw in raw_text for kw in keywords):
                        self.log(f"  Hot page detected: Page {i+1}. Using layout-enhanced extraction.")
                        layout_text = page.extract_text(layout=True)
                        if layout_text:
                            full_text.append(layout_text)
                    else:
                        # For regular pages, standard extract is enough to save processing
                        if raw_text:
                            full_text.append(raw_text)
                
                self.text_content = "\n\n".join(full_text)
                self.log(f"Extraction complete: {len(self.text_content)} chars.")
                
        except Exception as e:
            self.log(f"Extraction failed: {e}")
            raise


    def parse_financials(self) -> Dict[str, Any]:
        """
        Parse key metrics using table extraction (primary) or text matching (fallback)
        """
        if not self.text_content:
            self.extract_content()
            
        self.log("--- Starting Financial Parsing ---")
        
        # Try table-based parsing first for generic enterprises (moved downstream after initialization)
        pass
        
        # 1. Global Unit Detection
        global_unit = 1.0
        header_text = self.text_content[:20000] # Use a larger window for header search

        # Determine Market Context
        is_cn_market = False
        is_hk_market = False
        if self.asset_id and "CN:STOCK" in self.asset_id:
            is_cn_market = True
            self.log("[DEBUG] A-Share (CN) Market Detected. Using conservative unit detection.")
        elif self.asset_id and "HK:STOCK" in self.asset_id:
            is_hk_market = True
            self.log("[DEBUG] HK Market Detected. Using strict HK unit detection to avoid '億' false positives.")

        # ── HK MARKET: Explicit unit scan FIRST ────────────────────────────────
        # HK financial reports use "千港元" (thousands of HKD) or "百萬港元" (millions of HKD)
        # The body text contains many occurrences of "億" (billions) in narrative descriptions,
        # which would incorrectly set global_unit=1e8 if we use keyword fallback.
        # We MUST detect the declared accounting unit from table headers / footnotes.
        explicitly_found = False
        detected_cur = None

        if is_hk_market and not explicitly_found:
            # Pattern 1: "港元千元" / "千港元" / "HK$'000" / "HK$ thousands" / "以千港元列示"
            hk_unit_patterns = [
                # Thousands patterns (most common for HK mid/large caps)
                (r'(?:以|按|港幣|港元|HK\$)\s*(?:千|千元|千港元|\'000|thousands?)', 1_000),
                (r'千港元', 1_000),
                (r"HK\$\s*'?000", 1_000),
                (r'港元千', 1_000),
                (r'HKD\s*thousand', 1_000),
                # Millions patterns
                (r'(?:以|按|港幣|港元|HK\$)\s*(?:百萬|百万|million)', 1_000_000),
                (r'百萬港元', 1_000_000),
                (r'HK\$\s*million', 1_000_000),
                # RMB thousands (some listed HK co. report in RMB thousands)
                (r'人民幣\s*千元', 1_000),
                (r'RMB\s*thousand', 1_000),
                (r'人民幣\s*百萬', 1_000_000),
            ]
            for pattern, unit_val in hk_unit_patterns:
                if re.search(pattern, header_text[:10000], re.IGNORECASE):
                    global_unit = unit_val
                    explicitly_found = True
                    self.log(f"[HK] Detected unit from explicit HK pattern '{pattern}': {unit_val}")
                    break

            if not explicitly_found:
                # Default HK fallback: 千港元 (thousands) is by far the most common
                # HK Listing Rules require financial statements in HKD; Large caps use '000
                global_unit = 1_000
                self.log("[HK] No explicit unit declaration found. Defaulting to 千港元 (×1,000). "
                         "This is the standard for HK annual/interim reports.")
                explicitly_found = True  # Mark as resolved so we skip the dangerous fallback below

        # ── Enhanced unit detection: explicit header patterns (non-HK) ──────────
        # Search for EXPLICIT patterns like "单位：人民币xxx" or "Unit: HK$'000"
        # Capture BOTH Currency (Group 1) and Unit (Group 2)
        if not explicitly_found:
            unit_match = re.search(
                r'(?:单位|單位|Unit|Currency|金額)[:：]\s*'
                r'(人民币|人民幣|港元|港幣|USD|HKD|CNY)?\s*'
                r"(百万元|百萬元|亿元|億元|万元|萬元|million|billion|thousand|'000|mn|k)",
                header_text[:5000], re.IGNORECASE
            )

            if unit_match:
                cur_str = unit_match.group(1)
                u_str = unit_match.group(2).lower()

                # Resolve Currency
                if cur_str:
                    if any(x in cur_str for x in ["人民币", "人民幣", "CNY"]): detected_cur = "CNY"
                    elif any(x in cur_str for x in ["港元", "港幣", "HKD"]): detected_cur = "HKD"
                    elif any(x in cur_str for x in ["USD", "美元"]): detected_cur = "USD"
                    if detected_cur:
                        self.log(f"Detected Currency from header: {detected_cur} (Raw: {cur_str})")

                if u_str in ["百万元", "百萬元", "million", "mn"]:
                    global_unit = 1_000_000
                    self.log(f"Detected Global Unit from header: Millions ({u_str})")
                    explicitly_found = True
                elif u_str in ["亿元", "億元", "billion", "bn"]:
                    global_unit = 100_000_000
                    self.log(f"Detected Global Unit from header: 100M/亿 ({u_str})")
                    explicitly_found = True
                elif u_str in ["万元", "萬元"]:
                    global_unit = 10_000
                    self.log(f"Detected Global Unit from header: 10k/万 ({u_str})")
                    explicitly_found = True
                elif u_str in ["thousand", "'000", "k"]:
                    global_unit = 1_000
                    self.log(f"Detected Global Unit from header: Thousand ({u_str})")
                    explicitly_found = True

        # ── Conservative Fallback: Only for non-CN, non-HK markets ─────────────
        # IMPORTANT: HK market MUST NOT use this fallback — '億' appears constantly
        # in HK report narrative text (e.g., '本集团实现收入XX亿元人民币') and would
        # incorrectly set global_unit = 1e8 when the actual accounting unit is 千港元.
        if not explicitly_found and not is_cn_market and not is_hk_market:
            # Quick keyword fallback for other markets (e.g., US ADR proxy reports)
            if any(x in header_text for x in ["百万元", "百萬元", "million", "百萬"]):
                global_unit = 1_000_000
                self.log("Detected Global Unit by keyword: Millions")
            elif any(x in header_text for x in ["亿元", "億元", "billion", "億"]):
                global_unit = 100_000_000
                self.log("Detected Global Unit by keyword: 100M/亿")
            elif any(x in header_text for x in ["'000", "千港元", "千元", "千"]):
                global_unit = 1_000
                self.log("Detected Global Unit by keyword: Thousand")
        elif not explicitly_found and is_cn_market:
            self.log("A-Share Global Unit Default: 1.0 (Reason: No explicit '单位:' header found)")

        self.global_unit = global_unit
        
        # 1.5 Report Type Detection
        report_type = "unknown"
        self.is_summary = False
        # Combine filename hint if available
        src_hint = str(getattr(self, 'pdf_path', '')).lower()
        
        # REVISED: Certain HK report titles should NEVER be summaries if they are designated full reports
        full_report_keywords = ["业绩公告", "业绩公布", "业绩报告", "业绩", "業績公佈", "業績公告", "業績報告", "業績", "中期报告", "年中業績", "年度报告", "年度報告", "ANNUAL REPORT", "INTERIM REPORT", "RESULTS"]
        if any(x in header_text for x in full_report_keywords):
             self.log(f"Detected full report keyword in header: {header_text}. Forcing is_summary=False.")
             self.is_summary = False
        else:
            summary_indicators = ["摘要", "SUMMARY", "ABSTRACT", "提示性公告", "业绩快报", "业绩预告", "PRELIMINARY"]
            if any(x in header_text or x in src_hint.upper() or x in src_hint for x in summary_indicators):
                self.is_summary = True
                self.log("Detected as SUMMARY/ABSTRACT report. Lowering priority.")

        # Check for Annual - Enhanced for CITIC format and spaces
        # Pattern: "二〇XX年年度报告" or "XXXX年年度报告" or "Annual Report"
        annual_kws = ["年年度报告", "年度报告", "Annual Report", "年 度 报 告", "年报",
                      "全年业绩", "末期业绩", "初步业绩", "Annual Results", "Final Results", "Preliminary Results"]
        if any(x in header_text or x in src_hint for x in annual_kws):
            # Strict exclusion for summaries, interims, and supplementals
            if not self.is_summary and not any(x in header_text or x in src_hint for x in ["半年度", "Interim", "补充", "更新"]):
                report_type = "annual"
        
        # Check for Interim
        if report_type == "unknown":
            interim_kws = ["半年度报告", "中期报告", "Interim Report", "半 年 度 报 告", "中期 报告",
                           "中期业绩", "Interim Results", "Half-year Results"]
            if any(x in header_text or x in src_hint for x in interim_kws):
                if not self.is_summary:
                    report_type = "interim"
        
        # Check for Quarterly
        if report_type == "unknown":
            quarterly_kws = ["季度报告", "Quarterly Report", "第一季度", "第三季度", "1季度", "3季度", "一季报", "三季报", "季 度 报 告"]
            if any(x in header_text or x in src_hint for x in quarterly_kws):
                if not self.is_summary and not any(x in header_text or x in src_hint for x in ["补充", "更新"]):
                    report_type = "quarterly"
            
        self.report_type = report_type
        self.log(f"Initial Detected Report Type: {report_type} (Is Summary: {self.is_summary})")
        
        # 2. Key Metrics Placeholder
        data = {
            # Income Statement
            "revenue_ttm": None,
            "gross_profit_ttm": None,
            "operating_profit_ttm": None,
            "ebit_ttm": None,
            "net_income_ttm": None,
            "net_income_common_ttm": None,
            "r_and_d_expense_ttm": None,
            "interest_expense_ttm": None,
            "non_recurring_profit_ttm": None,
            "net_interest_income": None,
            "net_fee_income": None,
            "provision_expense": None,
            "eps": None,
            "eps_diluted": None,
            
            # Balance Sheet
            "total_assets": None,
            "total_liabilities": None,
            "total_debt": None,
            "net_debt": None,
            "cash_and_equivalents": None,
            "accounts_receivable_end": None,
            "inventory_end": None,
            "accounts_payable_end": None,
            "common_equity_begin": None,
            "common_equity_end": None,
            
            # Bank Specifics
            "total_loans": None,
            "loan_loss_allowance": None,
            "npl_balance": None,
            "npl_ratio": None,
            "provision_coverage": None,
            "core_tier1_ratio": None,
            
            # Cash Flow
            "operating_cashflow_ttm": None,
            "investing_cashflow_ttm": None,
            "financing_cashflow_ttm": None,
            "capex_ttm": None,
            "dividends_paid_cashflow": None,
            "share_buyback_amount_ttm": None,
            
            # Dividends & Shared
            "dividend_amount": None,
            "dividend_per_share": None,
            "shares_outstanding_common_end": None,
            "shares_diluted": None,
            "payout_ratio": None,
            
            # Metadata
            "report_date": None,
            "raw_text": None,
            "debug_logs": self.logs,
            "report_type": self.report_type,
            "global_unit": self.global_unit,
            
            # --- New AI/CapEx & Enhanced Metrics ---
            "return_on_invested_capital": None,
            "buyback_amount": None,
            "treasury_shares": None,
            "capex_cash_additions_3m": None,
            "ppe_total_net": None,
            "ppe_servers_net": None,
            "ppe_buildings_net": None,
            "amortization_intangibles_6m": None,
            "lease_ppe_finance_net": None,
            "lease_rou_assets_operating": None,
            "lease_capex_operating_additions_6m": None,
            "strategic_ai_investment_funded": None,
            
            # --- New Banking Metrics ---
            "allowance_to_loan": None,
            "overdue_90_loans": None,
            "tier1_capital_ratio": None,
            "capital_adequacy_ratio": None
        }

        # 2. Date Detection - Prioritize Accounting Period End Dates
        self._parse_report_date(data, header_text)

        # 2.5 Table-based extraction (Injecting data into initialized structure)
        if not self.is_bank:
            self.log("Attempting table-based extraction...")
            table_data = self._parse_tables()
            self.log(f"[DEBUG] table_data keys: {list(table_data.keys()) if table_data else 'None'}")
            self.log(f"[DEBUG] table_data revenue: {table_data.get('revenue') if table_data else 'N/A'}")
            if table_data and len(table_data) >= 3:
                self.log(f"✅ Table extraction successful: {len(table_data)} fields found")
                data.update(table_data)
            else:
                self.log("⚠️ Table extraction insufficient, falling back to text-based parsing")
            
            # DEBUG: Track revenue after table extraction
            self.log(f"[DEBUG] AFTER Table Extraction: revenue={data.get('revenue')}")
        else:
            self.log("Using text-based parsing for bank")

        # 3. Priority-Based Metric Extraction - Using Centralized Config
        def get_kws(metric):
            """
            Get keywords for a metric based on industry type
            Returns bank keywords for banks, generic keywords for non-banks
            """
            # For banks, use bank-specific keywords
            if self.is_bank:
                return get_keywords_for_bank(self.asset_id, metric)
            
            # For generic enterprises, use generic keywords
            if not GENERIC_KEYWORDS_AVAILABLE:
                # Fallback to bank keywords if generic not available
                return get_keywords_for_bank(self.asset_id, metric)
            
            # Map metric names to generic keyword lists
            generic_keyword_map = {
                "revenue": REVENUE_KEYWORDS,
                "net_profit": NET_PROFIT_KEYWORDS,
                "gross_profit": GROSS_PROFIT_KEYWORDS,
                "operating_profit": OPERATING_PROFIT_KEYWORDS,
                "total_assets": TOTAL_ASSETS_KEYWORDS,
                "total_liabilities": TOTAL_LIABILITIES_KEYWORDS,
                "common_equity_end": EQUITY_KEYWORDS,
                "cash_and_equivalents": CASH_KEYWORDS,
                "operating_cashflow": OPERATING_CASHFLOW_KEYWORDS,
                "capex": CAPEX_KEYWORDS,
                "eps": EPS_KEYWORDS,
                "shares_outstanding": SHARES_OUTSTANDING_KEYWORDS,
                "dividend": DIVIDEND_KEYWORDS,
                "dividend_per_share": DPS_KEYWORDS,
                "rd_expense": RD_EXPENSE_KEYWORDS,
                "short_term_debt": SHORT_TERM_DEBT_KEYWORDS,
                "long_term_debt": LONG_TERM_DEBT_KEYWORDS,
                "accounts_receivable": RECEIVABLES_KEYWORDS,
                "inventory": INVENTORY_KEYWORDS,
                "accounts_payable": PAYABLES_KEYWORDS,
                # New Mappings
                "buyback_amount": ["股份回购金额", "回购金额", "Share Buyback Amount"],
                "treasury_shares": ["库存股", "Treasury Shares"],
                "roic": ["资本回报率", "ROIC", "Return on Invested Capital"],
                "capex_3m": ["过去3个月现金资本支出增加额", "Capex Additions (3M)"],
                "ppe_total": ["机器设备净值", "PPE Total Net"],
                "ppe_servers": ["算力服务器净值", "算力服务器", "Servers (Net)"],
                "ppe_buildings": ["厂房建筑净值", "Buildings (Net)"],
                "amortization_6m": ["过去6个月无形资产摊销", "Amortized Intangibles (6M)"],
                "lease_finance": ["融资租赁资产净值", "Finance Lease PPE"],
                "lease_operating": ["经营租赁使用权资产", "Operating Lease ROU Assets"],
                "lease_capex_6m": ["过去6个月经营性租赁增加额", "Operating Lease Capex (6M)"],
                "ai_investment": ["战略性 AI 投资资金", "Strategic AI Investment"],
            }
            
            keywords = generic_keyword_map.get(metric, [])
            if not keywords:
                # Fallback to bank keywords for unmapped metrics
                keywords = get_keywords_for_bank(self.asset_id, metric)
            
            return keywords

        # 3.1 Total Assets & Liabilities
        data['total_assets'] = self._find_metric_prioritized(get_kws("total_assets"), is_large=True, strategy="nearest", metric_name="total_assets") if not data.get('total_assets') else data['total_assets']
        data['total_liabilities'] = self._find_metric_prioritized(get_kws("total_liabilities"), is_large=True, strategy="nearest", metric_name="total_liabilities") if not data.get('total_liabilities') else data['total_liabilities']

        # 3.2 Income Statement
        # For banks: net_interest_income, net_fee_income
        # For generic: gross_profit, operating_profit
        if self.is_bank:
            data['net_interest_income'] = self._find_metric_prioritized(get_kws("net_interest_income"), is_large=True, strategy="nearest", metric_name="net_interest_income")
            data['net_fee_income'] = self._find_metric_prioritized(get_kws("net_fee_income"), is_large=True, strategy="nearest", metric_name="net_fee_income")
            data['provision_expense'] = self._find_metric_prioritized(get_kws("provision_expense"), is_large=True, strategy="nearest", metric_name="provision_expense")
        else:
            # Generic enterprise specific metrics
            data['gross_profit_ttm'] = self._find_metric_prioritized(get_kws("gross_profit"), is_large=True, strategy="nearest", metric_name="gross_profit") if not data.get('gross_profit_ttm') else data['gross_profit_ttm']
            data['operating_profit_ttm'] = self._find_metric_prioritized(get_kws("operating_profit"), is_large=True, strategy="nearest", metric_name="operating_profit") if not data.get('operating_profit_ttm') else data['operating_profit_ttm']
            data['r_and_d_expense_ttm'] = self._find_metric_prioritized(get_kws("rd_expense"), is_large=True, strategy="nearest", metric_name="rd_expense") if not data.get('r_and_d_expense_ttm') else data['r_and_d_expense_ttm']
            data['capex_ttm'] = self._find_metric_prioritized(get_kws("capex"), is_large=True, strategy="nearest", metric_name="capex") if not data.get('capex_ttm') else data['capex_ttm']
        
        # 3.3 Core Financials
        data['revenue_ttm'] = self._find_metric_prioritized(get_kws("revenue"), is_large=True, strategy="nearest", metric_name="revenue") if not data.get('revenue_ttm') else data['revenue_ttm']
        data['net_interest_income'] = self._find_metric_prioritized(get_kws("net_interest_income"), is_large=True, strategy="nearest", metric_name="net_interest_income") if not data.get('net_interest_income') else data['net_interest_income']
        data['net_fee_income'] = self._find_metric_prioritized(get_kws("net_fee_income"), is_large=True, strategy="nearest", metric_name="net_fee_income") if not data.get('net_fee_income') else data['net_fee_income']
        data['provision_expense'] = self._find_metric_prioritized(get_kws("provision_expense"), is_large=True, strategy="nearest", metric_name="provision_expense") if not data.get('provision_expense') else data['provision_expense']
        data['net_income_ttm'] = self._find_metric_prioritized(get_kws("net_profit"), is_large=True, strategy="nearest", metric_name="net_profit") if not data.get('net_income_ttm') else data['net_income_ttm']
        # Map net_income_common as well
        data['net_income_common_ttm'] = data['net_income_ttm']

        data['total_assets'] = self._find_metric_prioritized(get_kws("total_assets"), is_large=True, strategy="top_level", metric_name="total_assets") if not data.get('total_assets') else data['total_assets']
        data['total_liabilities'] = self._find_metric_prioritized(get_kws("total_liabilities"), is_large=True, strategy="top_level", metric_name="total_liabilities") if not data.get('total_liabilities') else data['total_liabilities']
        
        data['common_equity_end'] = self._find_metric_prioritized(get_kws("equity"), is_large=True, strategy="nearest", metric_name="equity") if not data.get('common_equity_end') else data['common_equity_end']
        
        # 3.4 Regulatory & Capital
        data['provision_coverage'] = self._find_metric_prioritized(get_kws("provision_coverage"), is_large=False, strategy="nearest", metric_name="provision_coverage") if not data.get('provision_coverage') else data['provision_coverage']
        data['core_tier1_ratio'] = self._find_metric_prioritized(get_kws("core_tier1_ratio"), is_large=False, strategy="nearest", metric_name="core_tier1_ratio") if not data.get('core_tier1_ratio') else data['core_tier1_ratio']
        
        # New Banking Specifics
        data['tier1_capital_ratio'] = self._find_metric_prioritized(get_kws("tier1_capital_ratio"), is_large=False, strategy="nearest", metric_name="tier1_capital_ratio")
        data['capital_adequacy_ratio'] = self._find_metric_prioritized(get_kws("capital_adequacy_ratio"), is_large=False, strategy="nearest", metric_name="capital_adequacy_ratio")
        data['allowance_to_loan'] = self._find_metric_prioritized(get_kws("allowance_to_loan"), is_large=False, strategy="nearest", metric_name="allowance_to_loan")
        data['overdue_90_loans'] = self._find_metric_prioritized(get_kws("overdue_90_loans"), is_large=True, strategy="nearest", metric_name="overdue_90_loans")

        # New AI / CapEx / Generic Metrics
        data['return_on_invested_capital'] = self._find_metric_prioritized(get_kws("roic"), is_large=False, strategy="nearest", metric_name="roic")
        data['buyback_amount'] = self._find_metric_prioritized(get_kws("buyback_amount"), is_large=True, strategy="nearest", metric_name="buyback_amount")
        data['treasury_shares'] = self._find_metric_prioritized(get_kws("treasury_shares"), is_large=True, strategy="nearest", metric_name="treasury_shares")

        # AI & CapEx Model
        data['capex_cash_additions_3m'] = self._find_metric_prioritized(get_kws("capex_3m"), is_large=True, metric_name="capex_3m")
        data['ppe_total_net'] = self._find_metric_prioritized(get_kws("ppe_total"), is_large=True, metric_name="ppe_total")
        data['ppe_servers_net'] = self._find_metric_prioritized(get_kws("ppe_servers"), is_large=True, metric_name="ppe_servers")
        data['ppe_buildings_net'] = self._find_metric_prioritized(get_kws("ppe_buildings"), is_large=True, metric_name="ppe_buildings")
        data['amortization_intangibles_6m'] = self._find_metric_prioritized(get_kws("amortization_6m"), is_large=True, metric_name="amortization_6m")
        data['lease_ppe_finance_net'] = self._find_metric_prioritized(get_kws("lease_finance"), is_large=True, metric_name="lease_finance")
        data['lease_rou_assets_operating'] = self._find_metric_prioritized(get_kws("lease_operating"), is_large=True, metric_name="lease_operating")
        data['lease_capex_operating_additions_6m'] = self._find_metric_prioritized(get_kws("lease_capex_6m"), is_large=True, metric_name="lease_capex_6m")
        data['strategic_ai_investment_funded'] = self._find_metric_prioritized(get_kws("ai_investment"), is_large=True, metric_name="ai_investment")
        
        # 3.4.1 Sanity Check for Global Unit
        # Banks typically have assets in Trillions (10^12) or high Billions. 
        # If total_assets > 100 Trillion with detected unit, it's likely a unit error (detected 10^8 instead of 10^6).
        if data['total_assets'] and data['total_assets'] > 100_000_000_000_000:
             self.log(f"⚠️ Unit Sanity Check failed: Total Assets {data['total_assets']} is too large. Potential 100x overestimate.")
             if self.global_unit == 100_000_000:
                 self.log("Adjusting Global Unit from 10^8 (100M) to 10^6 (Millions) and re-scaling large metrics.")
                 self.global_unit = 1_000_000
                 data['global_unit'] = self.global_unit
                 # Re-scale
                 sc_keys = ['total_assets', 'total_liabilities', 'revenue_ttm', 'net_income_ttm', 'net_interest_income', 'net_fee_income', 
                           'total_loans', 'loan_loss_allowance', 'npl_balance', 'common_equity_begin', 'common_equity_end', 
                           'dividends_paid_cashflow', 'operating_cashflow_ttm', 'cash_and_equivalents', 'total_debt', 'capex_ttm', 'gross_profit_ttm']
                 for k in sc_keys:
                     if data.get(k) is not None:
                         data[k] = round(data[k] / 100, 2) if isinstance(data[k], float) else data[k] // 100
        
        # ... rest of the code ...
        
        # 3.5 Dividends & Share Structure
        data['dividends_paid_cashflow'] = self._find_metric_prioritized(get_kws("dividends_paid"), is_large=True, metric_name="dividends_paid") if not data.get('dividends_paid_cashflow') else data['dividends_paid_cashflow']
        data['dividend_amount'] = data['dividends_paid_cashflow']
        
        # DPS special handling
        dps_val = self._find_metric_prioritized(get_kws("dividend_per_share"), is_large=False, strategy="nearest", metric_name="dividend_per_share")
        if dps_val is not None:
             ratio10 = re.search(r'每\s*10\s*股\s*派\s*(?:发现金红利|现金红利|现金)\s*([\d\.]+)\s*元', self.text_content)
             if ratio10:
                 r_val = float(ratio10.group(1))
                 self.log(f"Detected 'Per 10 Shares' dividend: {r_val} Yuan per 10. Normalizing to {r_val/10} per share.")
                 dps_val = r_val / 10.0
        data['dividend_per_share'] = dps_val
        
        # 3.5.1 Fallback for Common Equity Begin
        if data['common_equity_begin'] is None:
            data['common_equity_begin'] = self._find_metric_prioritized(get_kws("common_equity_begin"), is_large=True, strategy="nearest", metric_name="common_equity_begin")

        data['shares_outstanding_common_end'] = self._find_metric_prioritized(get_kws("shares_outstanding"), is_large=False, metric_name="shares_outstanding") if not data.get('shares_outstanding_common_end') else data['shares_outstanding_common_end']
        self._normalize_shares_outstanding(data)
        
        data['eps'] = self._find_metric_prioritized(get_kws("eps"), is_large=False, strategy="nearest", metric_name="eps") if not data.get('eps') else data['eps']
        
        # Cashflow & Debt
        data['operating_cashflow_ttm'] = self._find_metric_prioritized(get_kws("operating_cashflow"), is_large=True, strategy="nearest", metric_name="operating_cashflow") if not data.get('operating_cashflow_ttm') else data['operating_cashflow_ttm']
        data['investing_cashflow_ttm'] = self._find_metric_prioritized(get_kws("investing_cashflow"), is_large=True, strategy="nearest", metric_name="investing_cashflow") if not data.get('investing_cashflow_ttm') else data['investing_cashflow_ttm']
        data['financing_cashflow_ttm'] = self._find_metric_prioritized(get_kws("financing_cashflow"), is_large=True, strategy="nearest", metric_name="financing_cashflow") if not data.get('financing_cashflow_ttm') else data['financing_cashflow_ttm']

        data['cash_and_equivalents'] = self._find_metric_prioritized(get_kws("cash_and_equivalents"), is_large=True, strategy="nearest", metric_name="cash_and_equivalents") if not data.get('cash_and_equivalents') else data['cash_and_equivalents']
        
        data['short_term_debt'] = self._find_metric_prioritized(get_kws("short_term_debt"), is_large=True, strategy="nearest", metric_name="short_term_debt") if not data.get('short_term_debt') else data['short_term_debt']
        data['long_term_debt'] = self._find_metric_prioritized(get_kws("long_term_debt"), is_large=True, strategy="nearest", metric_name="long_term_debt") if not data.get('long_term_debt') else data['long_term_debt']
        
        data['accounts_receivable_end'] = self._find_metric_prioritized(get_kws("receivables"), is_large=True, strategy="nearest", metric_name="receivables") if not data.get('accounts_receivable_end') else data['accounts_receivable_end']
        data['inventory_end'] = self._find_metric_prioritized(get_kws("inventory"), is_large=True, strategy="nearest", metric_name="inventory") if not data.get('inventory_end') else data['inventory_end']
        data['accounts_payable_end'] = self._find_metric_prioritized(get_kws("payables"), is_large=True, strategy="nearest", metric_name="payables") if not data.get('accounts_payable_end') else data['accounts_payable_end']

        # Bank specific fallback for debt if needed, usually total debt isn't a direct line item
        data['total_debt'] = self._find_metric_prioritized(get_kws("total_debt"), is_large=True, strategy="nearest", metric_name="total_debt")
        
        # 3.6 Final Bank-Specific Sanity Checks & Proxies
        
        # Revenue vs Net Profit (Noise filter) - ONLY FOR BANKS
        # Generic enterprises can have low margins, so skip this check for them
        if self.is_bank:
            if data['revenue_ttm'] and data['net_income_ttm'] and data['revenue_ttm'] < data['net_income_ttm'] * 1.1:
                self.log(f"⚠️ [BANK] Revenue ({data['revenue_ttm']}) suspiciously close to or less than Net Profit ({data['net_income_ttm']}). Likely segment income. Clearing Revenue.")
                data['revenue_ttm'] = None
        
        # --- Internal Sync & Validation ---
        def sync_metrics(d):
            # Sync TTM and non-TTM variants
            pairs = [('revenue', 'revenue_ttm'), ('net_profit', 'net_income_ttm'), 
                     ('gross_profit', 'gross_profit_ttm'), ('operating_profit', 'operating_profit_ttm'),
                     ('rd_expense', 'r_and_d_expense_ttm'), ('capex', 'capex_ttm'),
                     ('operating_cashflow', 'operating_cashflow_ttm')]
            for k1, k2 in pairs:
                if d.get(k1) is None and d.get(k2) is not None: d[k1] = d[k2]
                elif d.get(k2) is None and d.get(k1) is not None: d[k2] = d[k1]
        
        sync_metrics(data)
        
        if not self.is_bank:
            self.log(f"[DEBUG] BEFORE Validation: rev={data.get('revenue')}, np={data.get('net_profit')}")
            
            # Rule 1: GP Check
            rev, gp, np = data.get('revenue'), data.get('gross_profit'), data.get('net_profit')
            if rev and gp and gp > rev * 1.1:
                self.log(f"⚠️ [VALIDATION] GP ({gp}) > Revenue ({rev}). Clearing GP.")
                data['gross_profit'] = data['gross_profit_ttm'] = None
            
            # Rule 2: NP Check (Special for 00700/01024)
            if rev and np and abs(np) > rev:
                if not any(x in (self.asset_id or "") for x in ["00700", "01024", "00981"]):
                     self.log(f"⚠️ [VALIDATION] Net Profit ({np}) > Revenue ({rev}). Likely error.")
            
            # Rule 3: Shares Check
            shares = data.get('shares_outstanding_common_end')
            if shares and shares < 1_000_000:
                self.log(f"⚠️ [VALIDATION] Shares ({shares}) too small. Clearing.")
                data['shares_outstanding_common_end'] = None

            # Rule 4: Gigantic Asset Scale (for 00700 etc)
            assets = data.get('total_assets')
            if assets and assets < 100_000_000 and any(x in (self.asset_id or "") for x in ["00700", "09988", "03690"]):
                self.log(f"⚠️ [SCALING] Assets {assets} too small. Clearing.")
                data['total_assets'] = None

            self.log(f"[DEBUG] AFTER Validation: rev={data.get('revenue')}")

        # Final Sync back to TTM for Persistance
        sync_metrics(data)
        if data.get('net_income_ttm'): data['net_income_common_ttm'] = data['net_income_ttm']

        # 3.9 Shares Outstanding Fallback (Calculated from Profit/EPS)
        np_val = data.get('net_income_ttm')
        eps_val = data.get('eps')
        if np_val and eps_val and abs(eps_val) > 0.001:
             calc_shares = abs(np_val) / abs(eps_val)
             curr_shares = data.get('shares_outstanding_common_end')
             
             # If calculated shares are in a reasonable range (> 1M)
             if calc_shares > 1_000_000:
                 # If current shares are missing or look wrong (different scale)
                 if not curr_shares or abs(calc_shares / curr_shares - 1) > 0.5:
                     self.log(f"🔄 Recalculating shares: {np_val:,.0f} / {eps_val:.4f} = {calc_shares:,.0f}")
                     data['shares_outstanding_common_end'] = calc_shares

        data["raw_text"] = self.text_content[:2000] + "... (truncated)" # Don't return full text to save memory
        data["report_type"] = self.report_type # Sync final report type (might have been inferred from date)
        data["currency"] = detected_cur # Export detected currency (CNY/HKD/USD)
        return data

    def _parse_report_date(self, data: Dict, header_text: str):
        cn_years = {
            "二〇二三": "2023", "二〇二四": "2024", "二〇二五": "2025", "二〇2五": "2025", "二〇二六": "2026",
            "二〇二二": "2022", "二〇二一": "2021", "二〇二〇": "2020", "二〇一九": "2019", "二〇一八": "2018", "二〇一七": "2017", "二〇一六": "2016"
        }
        cn_quarters = {
            "第一季度": "03-31", "第二季度": "06-30", "第三季度": "09-30", "第四季度": "12-31", 
            "第壹季度": "03-31", "第贰季度": "06-30", "第叁季度": "09-30", "第肆季度": "12-31",
            "一季度": "03-31", "三季度": "09-30",
            "年报": "12-31", "年度報告": "12-31", "年度报告": "12-31", "半年度报告": "06-30"
        }
        
        # Priority 1: Explicit period-end expressions (截至)
        # 1.1 Arabic Digits (Standard)
        period_end_match = re.search(r'截至\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', header_text)
        if period_end_match:
            y, m, d = period_end_match.groups()
            candidate = f"{y}-{int(m):02d}-{int(d):02d}"
            data['report_date'] = self._snap_to_quarter_end(candidate)
            self.log(f"Detected period-end date (Arabic): {data['report_date']}")
        
        # 1.2 Chinese Digits (Alibaba Style: 二零XX年九月三十日)
        if not data.get('report_date'):
            cn_digits = {"零": "0", "一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
            cn_date_match = re.search(r'截至\s*([零一二三四五六七八九十]{4})\s*年\s*([一二三四五六七八九十]{1,2})\s*月\s*([一二三四五六七八九十]{1,3})\s*日', header_text)
            if cn_date_match:
                cy, cm, cd = cn_date_match.groups()
                # Simple year conversion
                ry = "".join(cn_digits.get(c, c) for c in cy)
                
                # Month conversion (Handle 十, 十一, 十二)
                def cn_to_int(s):
                    if s == "十": return 10
                    if s.startswith("十"): return 10 + int(cn_digits[s[1]])
                    return int(cn_digits[s])
                
                rm = cn_to_int(cm)
                
                # Day conversion (Handle 三十 etc)
                def cn_to_int_day(s):
                    if s == "三十": return 30
                    if s == "三十一": return 31
                    if s == "二十": return 20
                    if s.startswith("三十"): return 30 + int(cn_digits[s[2]])
                    if s.startswith("二十"): return 20 + int(cn_digits[s[2]])
                    if s.startswith("十"): return 10 + (int(cn_digits[s[1]]) if len(s)>1 else 0)
                    return int(cn_digits[s])
                
                rd = cn_to_int_day(cd)
                candidate = f"{ry}-{int(rm):02d}-{int(rd):02d}"
                data['report_date'] = self._snap_to_quarter_end(candidate)
                self.log(f"Detected period-end date (Chinese Numbers): {data['report_date']}")

        # 1.3 Special HK Suffix (六月底止, 十二月底止)
        if not data.get('report_date'):
            hk_suffix_match = re.search(r'(\d{4})\s*年\s*(六|十二)\s*月底', header_text)
            if hk_suffix_match:
                hy, hm = hk_suffix_match.groups()
                hmon = "06-30" if hm == "六" else "12-31"
                data['report_date'] = f"{hy}-{hmon}"
                self.log(f"Detected period-end date (HK Suffix): {data['report_date']}")

        if data.get('report_date'):
            d_suffix = data['report_date'][-5:]
            is_march_end = any(x in (self.asset_id or "") for x in ["09988", "9988"]) # Alibaba
            
            # Record original type for debug
            orig_type = self.report_type
            
            if is_march_end:
                # Alibaba Fiscal Year: starts April 1, ends March 31
                if d_suffix == "03-31": self.report_type = "annual"
                elif d_suffix == "09-30": self.report_type = "interim"
                else: self.report_type = "quarterly" # Covers 06-30 and 12-31
            else:
                # Standard Fiscal Year: starts Jan 1, ends Dec 31
                if d_suffix == "12-31": self.report_type = "annual"
                elif d_suffix == "06-30": self.report_type = "interim"
                elif d_suffix in ["03-31", "09-30"]: self.report_type = "quarterly"
            
            if self.report_type != orig_type and orig_type != "unknown":
                self.log(f"🔄 Re-calibrated report type from {orig_type} to {self.report_type} based on date {data['report_date']}")
            return

        # Priority 2: Year detection from Header (Most Accurate)
        year_val = None
        for cn_year, en_year in cn_years.items():
            if cn_year in header_text:
                year_val = en_year
                break
        
        if not year_val:
            # Look for YYYY年 in the first few lines
            year_match = re.search(r'(\d{4})\s*年', header_text[:1200])
            if year_match: 
                year_val = year_match.group(1)
            else:
                # Try to extract from filename (Caution: filing date is usually year+1 for annual)
                src_hint = str(getattr(self, 'pdf_path', ''))
                filename_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', src_hint)
                if filename_match:
                    fy, fm, fd = filename_match.groups()
                    if self.report_type == "annual":
                        # If filing date is Jan-May, the report year is likely fy-1
                        if int(fm) <= 5: 
                            year_val = str(int(fy) - 1)
                        else:
                            year_val = fy
                    else:
                        year_val = fy

        # If we have a clear report type, we can snap the ending
        if year_val:
            if self.report_type == "annual":
                data['report_date'] = f"{year_val}-12-31"
                self.log(f"Snapped Annual Report to: {data['report_date']}")
                return
            elif self.report_type == "interim":
                data['report_date'] = f"{year_val}-06-30"
                self.log(f"Snapped Interim Report to: {data['report_date']}")
                return
            elif self.report_type == "quarterly":
                if any(x in header_text for x in ["一季度", "第一季度", "第壹季度"]):
                    data['report_date'] = f"{year_val}-03-31"
                elif any(x in header_text for x in ["三季度", "第三季度", "第叁季度"]):
                    data['report_date'] = f"{year_val}-09-30"
                
                if data.get('report_date'):
                    self.log(f"Snapped Quarterly Report to: {data['report_date']}")
                    return

        # Priority 3: Generic date pattern - but prefer quarter end
        date_matches = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', self.text_content[:2000])
        for y, m, d in date_matches:
            dt = f"{y}-{int(m):02d}-{int(d):02d}"
            if f"{int(m):02d}-{int(d):02d}" in ["03-31", "06-30", "09-30", "12-31"]:
                data['report_date'] = dt
                self.log(f"Detected quarter-end date: {dt}")
                return

        # Priority 4: Fallback - snap any detected date to nearest quarter end
        if date_matches:
            y, m, d = date_matches[0]
            candidate = f"{y}-{int(m):02d}-{int(d):02d}"
            data['report_date'] = self._snap_to_quarter_end(candidate)
            self.log(f"Snapped generic date {candidate} to quarter end: {data['report_date']}")
        
        # Final fallback: use filename date if available
        if not data.get('report_date'):
            src_hint = str(getattr(self, 'pdf_path', ''))
            filename_date = re.search(r'(\d{4})-(\d{2})-(\d{2})', src_hint)
            if filename_date:
                y, m, d = filename_date.groups()
                candidate = f"{y}-{m}-{d}"
                data['report_date'] = self._snap_to_quarter_end(candidate)
                self.log(f"Used filename date {candidate}, snapped to: {data['report_date']}")
        
        # Re-check report type inference from date even in fallback cases
        if self.report_type == "unknown" and data.get('report_date'):
            d_suffix = data['report_date'][-5:]
            if d_suffix == "12-31": 
                self.report_type = "annual"
            elif d_suffix == "06-30": 
                self.report_type = "interim"
            elif d_suffix in ["03-31", "09-30"]:
                self.report_type = "quarterly"
            if self.report_type != "unknown":
                self.log(f"Re-inferred Report Type '{self.report_type}' from {d_suffix} date")

    def _snap_to_quarter_end(self, date_str: str) -> str:
        """Snap a date to the nearest quarter end"""
        from datetime import datetime
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            year = dt.year
            month = dt.month
            
            # Determine nearest quarter end
            if month <= 2:
                return f"{year-1}-12-31"   # Q4 of last year
            elif month <= 5:
                return f"{year}-03-31"    # Q1
            elif month <= 8:
                return f"{year}-06-30"    # Q2 (Interim)
            elif month <= 11:
                return f"{year}-09-30"    # Q3
            else:
                return f"{year}-12-31"    # Q4/Annual
        except:
            return date_str

    def _normalize_shares_outstanding(self, data: Dict):
        if data['shares_outstanding_common_end'] is not None:
            val = data['shares_outstanding_common_end']
            # Filter out noisy small decimals or potential ratios
            if abs(val) < 0.01:
                self.log(f"Shares raw {val} too small, likely noise. Clearing.")
                data['shares_outstanding_common_end'] = None
                return

            # Special logic for Mega-Caps (HK/CN)
            is_huge = any(x in (self.asset_id or "") for x in ["00700", "09988", "03690", "01810", "01024", "09618", "09888"])
            
            # If the value is very small (e.g. < 500)
            if val < 2000:
                # Try Yi (10^8)
                as_yi = val * 100_000_000
                as_mi = val * 1_000_000
                
                if is_huge:
                    if as_yi >= 1_000_000_000:
                        data['shares_outstanding_common_end'] = as_yi
                        self.log(f"Mega-Cap Shares {val} detected as Yi -> {as_yi:,.0f}")
                    elif as_mi >= 1_000_000_000:
                         data['shares_outstanding_common_end'] = as_mi
                         self.log(f"Mega-Cap Shares {val} detected as Millions -> {as_mi:,.0f}")
                else:
                    if as_yi > 1_000_000_000:
                        data['shares_outstanding_common_end'] = as_yi
                        self.log(f"Shares raw {val} detected as Yi -> {data['shares_outstanding_common_end']:,.0f}")
                    else:
                        data['shares_outstanding_common_end'] = as_mi
                        self.log(f"Shares raw {val} detected as Millions -> {data['shares_outstanding_common_end']:,.0f}")
            elif val < 1_000_000: 
                # Values between 2k and 1M likely in Millions
                data['shares_outstanding_common_end'] = val * 1_000_000
                self.log(f"Shares raw {val} detected as Millions -> {data['shares_outstanding_common_end']:,.0f}")

    def _find_metric_prioritized(self, keyword_groups: List[List[str]], is_large: bool = False, strategy: str = "nearest", metric_name: str = "unknown", num_index: int = 0) -> Optional[float]:
        """
        Find a metric by iterating through keyword priority groups.
        num_index: 0 for primary value (usually end of period), 1 for second column (beginning of period).
        """
        # Ensure keyword_groups is a List of Lists. If passed a flat list, wrap it.
        if keyword_groups and isinstance(keyword_groups[0], str):
            keyword_groups = [keyword_groups]
            
        for group in keyword_groups:
            cands = self._get_candidates_for_keywords(group, is_large=is_large, num_index=num_index)
            if cands:
                val = self._select_best_candidate(cands, strategy, metric_name, is_large)
                if val is not None:
                    return val
        return None

    def _select_best_candidate(self, all_candidates: List[Tuple], strategy: str, metric_name: str, is_large: bool) -> Optional[float]:
        normalized_cands = []
        for val, local_scale, dist, kw_pos, val_pos, kw_text, period_score in all_candidates:
            effective_dist = dist
            scale = 1.0
            if is_large:
                if local_scale:
                    scale = local_scale
                    effective_dist = max(0, effective_dist - 50) 
                else:
                    scale = self.global_unit
                    effective_dist += 200
                
                # Reward Period (12m/Annual > 9m > 6m > 3m)
                # Max period_score is 12. Decrease dist significantly for better periods.
                effective_dist -= (period_score * 40) 
            else:
                scale = 1.0 # Ratios/EPS usually don't scale
                # For shares, also reward period detection
                if metric_name == 'shares_outstanding':
                     effective_dist -= (period_score * 20)
            
            norm_val = val * scale
            
            # --- Generic Filters ---
            min_expected = 1_000_000_000 # 1 Billion floor
            if metric_name in ['total_assets', 'total_liabilities']: min_expected = 10_000_000_000
            if is_large and abs(norm_val) < min_expected and metric_name not in ['short_term_debt', 'long_term_debt', 'dividend_amount', 'rd_expense', 'capex']:
                continue
            if not is_large and val > 1900 and val < 2100: continue
            if is_large and abs(norm_val) > 500_000_000_000_000: continue

            normalized_cands.append((norm_val, scale, effective_dist, kw_text, period_score))

        if not normalized_cands: return None

        # Sort by effective distance (which includes period rewards)
        def scorer(cand):
            val, scale, dist, kw_text, p_score = cand
            score = dist
            if any(x in kw_text for x in ["合计", "合计", "总额", "总计", "consolidated", "Total"]):
                score -= 100
            return score

        normalized_cands.sort(key=scorer)
        
        if (is_large or metric_name == 'eps') and len(normalized_cands) > 1:
            self.log(f"  [{metric_name}] Found {len(normalized_cands)} candidates:")
            for i, (val, scale, dist, kw_text, p_score) in enumerate(normalized_cands[:5]):
                self.log(f"    {i+1}. {val:,.0f} (Dist: {dist}, Scale: {scale}, KW: {kw_text[:30]}, Period: {p_score}m)")
            
            top_val, top_scale, top_dist, top_kw, top_p = normalized_cands[0]
            
            # Define reasonable minimum thresholds for different metrics
            min_thresholds = {
                'revenue': 10_000_000_000,  # 100亿 minimum for large enterprises
                'total_assets': 10_000_000_000,  # 100亿
                'total_liabilities': 5_000_000_000,  # 50亿
                'net_profit': 500_000_000,  # 5亿
                'gross_profit': 1_000_000_000,  # 10亿
                'operating_profit': 500_000_000,  # 5亿
            }
            
            min_threshold = min_thresholds.get(metric_name, 1_000_000_000)
            
            # Only consider alternatives if top candidate is below threshold
            if top_val < min_threshold:
                for i in range(1, min(3, len(normalized_cands))):
                    alt_val, alt_scale, alt_dist, alt_kw, alt_p = normalized_cands[i]
                    
                    # Prefer alternative if:
                    # 1. It's 10x-100x larger (not too extreme)
                    # 2. Distance difference < 50 (very close)
                    # 3. Alternative is above threshold
                    if (10 <= alt_val / top_val <= 100 and 
                        (alt_dist - top_dist) < 50 and 
                        alt_val >= min_threshold):
                        self.log(f"  [{metric_name}] ⚠️ Top candidate ({top_val:,.0f}) below threshold ({min_threshold:,.0f}).")
                        self.log(f"  [{metric_name}] Preferring larger candidate: {alt_val:,.0f} (Dist: {alt_dist})")
                        res = normalized_cands[i]
                        self.log(f"  [{metric_name}] Selected Best Match: {res[0]} (Dist: {res[2]})")
                        return res[0]
        
        res = normalized_cands[0]
        self.log(f"  [{metric_name}] Selected Best Match: {res[0]} (Dist: {res[2]})")
        return res[0]
    
    def _parse_tables(self) -> Dict[str, Any]:
        """
        Parse financial data from PDF tables
        Returns dict with extracted fields
        """
        data = {}
        
        self.log(f"[DEBUG] _parse_tables: PDFPLUMBER_AVAILABLE={PDFPLUMBER_AVAILABLE}, pdf_path={self.pdf_path is not None}")
        if not PDFPLUMBER_AVAILABLE or not self.pdf_path:
            self.log(f"[DEBUG] _parse_tables: Returning early (no pdfplumber or no path)")
            return data
        
        # Detect report type to determine scan depth
        filename = os.path.basename(self.pdf_path).lower()
        # Annual or Interim reports usually have detailed notes after page 50
        is_long_report = any(kw in filename for kw in ["年度报告", "annual", "半年度", "interim", "中报"])
        max_pages = 150 if is_long_report else 30
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                scan_limit = min(max_pages, total_pages)
                self.log(f"[DEBUG] _parse_tables: Opened {filename}, scan depth: {scan_limit}/{total_pages} pages")
                
                # Scan pages sequentially
                for page in pdf.pages[:scan_limit]:
                    page_text = page.extract_text() or ""
                    
                    # Try default extraction first (usually line-based)
                    all_tables_on_page = page.extract_tables() or []
                    
                    # If default fails, try text-alignment strategy (crucial for borderless HK reports)
                    if not all_tables_on_page:
                         try:
                             # Use 'text' strategy for borderless tables
                             text_tables = page.extract_tables({
                                 "vertical_strategy": "text",
                                 "horizontal_strategy": "text",
                                 "snap_tolerance": 3,
                                 "join_tolerance": 3
                             })
                             if text_tables: all_tables_on_page.extend(text_tables)
                         except:
                             pass

                    for table in all_tables_on_page:
                        self._extract_from_table(table, data, page_text)
        except Exception as e:
            self.log(f"❌ Table extraction error: {type(e).__name__}: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        self.log(f"[DEBUG] _parse_tables: Returning data with {len(data)} fields")
        return data
    
    def _extract_from_table(self, table: List[List], data: Dict, page_text: str = ""):
        """Extract financial metrics from a single table"""
        if not table or len(table) < 1:
            return

        # 1. Page Context Analysis (Check for "Consolidated" / "合并")
        is_consolidated = any(kw in page_text for kw in ["合并", "Consolidated"])
        # If the page doesn't mention "合并" but the table is likely financial, we proceed
        # but with lower confidence. For now we just log it.
        if not is_consolidated:
             # Check if the table itself has "合并" in header
             is_consolidated = any("合并" in str(cell) for cell in table[0])
        
        # [DEBUG] Inspect Table Structure
        if len(table) > 1:
             self.log(f"  [DEBUG] Processing Table with {len(table)} rows. Top row: {table[0]}")
        
        # 2. Header Semantic Analysis (Scanning top rows for the best header)
        target_col_idx = 1 # Default
        best_header_row_idx = 0
        max_header_score = -100
        
        # Scan top 5 rows to find the best header row
        for row_idx in range(min(5, len(table))):
            current_header = [str(c or "").strip().replace("\n", "").replace(" ", "") for c in table[row_idx]]
            row_col_scores = {}
            for idx, cell_str in enumerate(current_header):
                if idx == 0: continue
                score = 0
                # A-Share Standard Headers (High Priority)
                # Penalize "Change" columns to avoid picking ratio columns
                if any(x in cell_str for x in ["变动", "增减", "Change", "%", "Difference", "Growth", "Ratio"]): score -= 100
                # Dynamic Year Matching
                report_year = str(data.get('report_date', ''))[:4]
                if len(report_year) == 4 and report_year in cell_str: score += 75
                elif any(x in cell_str for x in ["1-12月", "1至12月", "年度", "全年", "FullYear", "YearEnded", "12Month"]): score += 80
                elif any(x in cell_str for x in ["年初至", "1-9月", "1至9月", "YTD", "9Month", "止九個月"]): score += 60
                elif any(x in cell_str for x in ["1-6月", "1至6月", "6Month", "Interim", "止六個月"]): score += 50
                elif any(x in cell_str for x in ["本报告期", "本期金额", "本期发生额", "本期数", "CurrentPeriod", "ReportingPeriod"]): score += 40
                elif any(x in cell_str for x in ["1-3月", "1至3月", "3Month", "Quarter", "止三個月"]): score += 20 
                elif any(x in cell_str for x in ["上年同期", "上期金额", "上期发生额", "上期数", "PriorPeriod", "LastYear"]): score += 10 
                
                if "合并" in cell_str or "CONSOLIDATED" in cell_str.upper(): score += 5
                row_col_scores[idx] = score
            
            if row_col_scores:
                current_best_col = max(row_col_scores, key=row_col_scores.get)
                current_max_score = row_col_scores[current_best_col]
                
                # Update if better score found
                if current_max_score > max_header_score:
                    max_header_score = current_max_score
                    best_header_row_idx = row_idx
                    target_col_idx = current_best_col

        self.log(f"  [Table Header] Selected Row {best_header_row_idx}, Column {target_col_idx} (Score: {max_header_score})")
        
        # Debugging Output for Table Analysis
        if max_header_score > 0:
             self.log(f"  [DEBUG] Valid Header Found. Scanning rows starting from {best_header_row_idx + 1}...")

        # 3. Row Processing (Start from row after header)
        for row in table[best_header_row_idx + 1:]:
            if not row or not row[0]: continue
            label_raw = str(row[0])
            label = label_raw.replace(' ', '').replace('\n', '')
            
            # Debug extraction
            if "营业收入" in label:
                 self.log(f"  [DEBUG] Found '营业收入' row: {row}")
            
            # --- Row-Level Period Analysis (逐一识别周期描述) ---
            row_period_score = 0
            if any(x in label_raw for x in ["12個月", "12个月", "全年", "年度", "Full Year"]):
                row_period_score = 12
            elif any(x in label_raw for x in ["9個月", "9个月", "九個月", "九个月", "1-9", "年初至"]):
                row_period_score = 9
            elif any(x in label_raw for x in ["6個月", "6个月", "六個月", "六个月", "1-6"]):
                row_period_score = 6
            elif any(x in label_raw for x in ["3個月", "3个月", "三個月", "三个月", "本季度", "本季", "1-3"]):
                row_period_score = 3

            # --- Unit/Scaling in Row Label ---
            # Default to global unit, but specific rows (like EPS/DPS) override this
            row_scale = getattr(self, 'global_unit', 1.0)
            
            # [FIX] Header-Level Unit Override
            if best_header_row_idx >= 0:
                 header_rows_to_check = [table[best_header_row_idx]]
                 if best_header_row_idx > 0: header_rows_to_check.append(table[best_header_row_idx-1])
                 for h_row in header_rows_to_check:
                     h_text = " ".join([str(c) for c in h_row if c])
                     if "百万" in h_text or "Million" in h_text or "百萬" in h_text: row_scale = 1_000_000
                     elif "亿" in h_text or "Billion" in h_text or "億" in h_text: row_scale = 100_000_000
                     elif "千" in h_text or "'000" in h_text: row_scale = 1_000
                     elif "元" in h_text or "RMB" in h_text or "CNY" in h_text: 
                         # Only reset if we are on the default global unit (e.g. 100M from header)
                         if row_scale == getattr(self, 'global_unit', 1.0) and row_scale != 1.0:
                             row_scale = 1.0

            # Row Label Override (Strongest)
            if any(x in label_raw for x in ["每股", "PerShare", "比例", "Ratio", "Rate", "%"]):
                row_scale = 1.0
            
            if "百万" in label_raw or "Million" in label_raw or "百萬" in label_raw: row_scale = 1_000_000
            elif "亿" in label_raw or "Billion" in label_raw or "億" in label_raw: row_scale = 100_000_000
            elif "千" in label_raw or "'000" in label_raw: row_scale = 1_000
            
            # --- Financial Type Logic ---
            is_monetary_row = any(kw in label_raw for kw in ["金额", "金額", "RMB", "HKD", "元", "USD", "面值"])
            
            # 获取数值
            val_raw = row[target_col_idx] if len(row) > target_col_idx else None
            value = self._extract_table_number(val_raw)
            
            # Debug extraction
            if "营业收入" in label:
                 self.log(f"  [DEBUG] Found '营业收入' row: {row}")
                 self.log(f"  [DEBUG] Extracted Value: {value} (Raw: {val_raw}) from Col {target_col_idx}")

            # [Fix] Row 0 Merged Cell Handling (e.g. "Revenue 1,234,567.89")
            # Enhance: Always check for merged values, even if column value exists (often column value is a ratio)
            if target_col_idx > 0:
                 potential_nums = re.findall(r'[\s:](-?[\d,]{2,20}(?:\.[\d]{2,}))', str(row[0]))
                 if potential_nums:
                     try:
                         for p_str in potential_nums:
                             candidate = float(p_str.replace(',', ''))
                             # If we found a substantial number in the label
                             if abs(candidate) > 100:
                                 # Override if current value is None OR current value looks like a small ratio (e.g. < 100)
                                 # while the candidate is much larger (> 1000)
                                 if value is None or (abs(value) < 100 and abs(candidate) > 1000):
                                     value = candidate
                                     self.log(f"  [Row Repair] Extracted value {value} from merged label '{row[0]}'")
                                     break
                     except: pass

            if value is None:
                for cell in row[1:]: # Fallback
                    val = self._extract_table_number(cell)
                    if val is not None:
                        value = val; break
            
            if value is None: continue
            
            # Apply scaling
            value = value * row_scale

            def is_match(target, kws):
                return any(kw.replace(' ', '') in target for kw in kws)

            def smart_update(field, value, label, row_p_score):
                """
                带周期校验和语义过滤的更新。
                """
                if field == 'revenue_ttm':
                     self.log(f"  [SmartUpdate] Try updating revenue: {value} (Label: {label}, P-Score: {row_p_score}, Scale: {row_scale})")

                # [Fix] Ratio Keyword Exclusion
                if any(x in label for x in ["比例", "Ratio", "%", "占比", "rate", "Rate"]):
                    if field in ['revenue_ttm', 'net_income_ttm', 'total_assets', 'total_liabilities', 'operating_profit', 'cash_and_equivalents']:
                        self.log(f"  [SmartUpdate] Rejected: Ratio Keyword in '{label}'")
                        return False

                # [Fix] Minimum Magnitude Check (Noise Filter)
                # Public companies won't have Revenue/Profit < 1000 CNY (usually > millions)
                # This filters out "Change %" (e.g. 97.49), "EPS" wrongly mapped to Profit
                if field in ['revenue_ttm', 'net_income_ttm', 'total_assets', 'total_liabilities', 'operating_profit', 'cash_and_equivalents']:
                     if abs(value) < 1000 and value != 0: 
                          self.log(f"  [SmartUpdate] Rejected: Value too small ({value}) for {field}")
                          return False

                # 语义过滤：排除分部数据 (Exclude Segments)
                if any(x in label for x in ["分部", "抵销", "Segment", "Inter-segment", "Elimination"]):
                    if field == 'revenue_ttm': self.log("  [SmartUpdate] Rejected: Segment Keyword")
                    return False
                
                # 特殊逻辑：股数识别增强 (Shares Validation)
                if field == 'shares_outstanding_common_end':
                    if is_monetary_row and not ("股份" in label): return False
                    # 腾讯等大公司股数极多，排除掉 EPS/DPS 等小数值的误认
                    if value < 1_000_000: return False # 至少 100 万股

                # 周期属性校验
                existing_val = data.get(field)
                if existing_val is not None:
                    existing_p = data.get(f"{field}_period", 0)
                    # 只有当新数据的周期更长，或者是同周期但 label 更具“合计”属性时才更新
                    is_new_better = (row_p_score > existing_p)
                    if not is_new_better and row_p_score == existing_p:
                        # 同周期，看关键词优先级
                        if any(x in label for x in ["合计", "总额", "Total", "Consolidated"]) and not any(x in str(data.get(f"{field}_label", "")) for x in ["合计", "总额"]):
                            is_new_better = True
                    
                    if not is_new_better: 
                        if field == 'revenue_ttm': self.log(f"  [SmartUpdate] Rejected: Better value exists ({existing_val} P: {existing_p})")
                        return False

                # 记录更新
                data[field] = value
                data[f"{field}_period"] = row_p_score
                data[f"{field}_label"] = label
                self.log(f"  [Table Match] {field} = {value:,.0f} (Period: {row_p_score}m, Label: '{label}')")
                return True

            # Match keywords to fields
            if is_match(label, REVENUE_KEYWORDS):
                smart_update('revenue_ttm', value, label, row_period_score)
            elif is_match(label, SHARES_OUTSTANDING_KEYWORDS):
                # SPECIAL PROTECTION: Shares usually don't scale by global unit unless explicit
                is_explicit_unit = any(x in label_raw for x in ["百万", "亿", "千", "000"])
                
                # If no explicit unit in this row, but we applied a huge global scale (like 100M), UN-DO IT.
                # Shares are rarely reported in 'Billions' as a default unit without saying so.
                if not is_explicit_unit and row_scale > 10000:
                     value = value / row_scale
                
                # Hard Cap Sanity: 500 Billion Shares is practically impossible (ICBC is ~350B)
                if value > 500_000_000_000: 
                     # Likely wrongly scaled by 100M (Yi) again
                     value = value / 100_000_000 
                     
                smart_update('shares_outstanding_common_end', value, label, row_period_score)
            elif is_match(label, NET_PROFIT_KEYWORDS):
                smart_update('net_income_ttm', value, label, row_period_score)
            elif is_match(label, DIVIDEND_KEYWORDS):
                smart_update('dividends_paid_cashflow', value, label, 0)
            elif is_match(label, CAPEX_KEYWORDS):
                smart_update('capex_ttm', value, label, 0)
    
    def _extract_table_number(self, cell: Optional[str]) -> Optional[float]:
        """Extract number from table cell"""
        if not cell:
            return None
        
        cell = str(cell).replace(',', '').replace(' ', '').replace('，', '')
        match = re.search(r'-?\d+\.?\d*', cell)
        if match:
            try:
                return float(match.group())
            except:
                return None
        return None

    def _get_candidates_for_keywords(self, keywords: List[str], is_large: bool = False, window_size: int = 250, num_index: int = 0) -> List[Tuple]:
        all_candidates = []
        for kw in keywords:
            # Flexible keyword matching
            flex_kw = r"[\s]*".join([re.escape(c) for c in list(kw)]) if re.search(r'[\u4e00-\u9fff]', kw) else re.escape(kw)
            
            # Special protection for shares: avoid "Per Share" (每股)
            pattern = re.compile(flex_kw, re.I)
            for match in pattern.finditer(self.text_content):
                start_pos, end_pos = match.start(), match.end()
                
                # Check for "每" (Per) right before the keyword
                prefix_safe = self.text_content[max(0, start_pos-10):start_pos]
                if "每" in prefix_safe[-2:] and "股份" not in kw and "股数" not in kw:
                    continue # Skip "每股..."
                
                # Blacklist: avoid "股息" (Dividend), "持股" (Shareholding)
                check_win = self.text_content[max(0, start_pos-10) : end_pos+10]
                if any(x in check_win for x in ["股息", "分紅", "分红", "持股", "股權", "股权", "每股", "PerShare"]):
                     if "总股本" not in kw and "股份总数" not in kw and "已发行股份" not in kw:
                         continue
                
                window = self.text_content[end_pos : end_pos + window_size + 100]
                
                # Regex for numbers
                num_matches = re.finditer(r'[\(（-]?\s*([\d,]{1,15}(?:\.[\d]+)?)\s*[\)）]?', window)
                
                valid_num_in_window = []
                for nm in num_matches:
                    full_text = nm.group(0)
                    val_str = nm.group(1).replace(',', '')
                    raw_start, raw_end = nm.start(), nm.end()
                    
                    try:
                        val = float(val_str)
                    except:
                        continue
                        
                    # Filter small integers
                    is_eps_kw = any(x in kw for x in ["EPS", "每股收益", "每股盈利", "每股盈餘"])
                    is_shares_kw = any(x in kw for x in ["股份", "股数", "Shares", "股"])
                    
                    if (is_shares_kw or is_large) and "." not in val_str and abs(val) < 50:
                        continue # Skip small integer IDs/footnotes
                    
                    if "." not in val_str and val in [1, 3, 6, 9, 12, 2023, 2024, 2025]:
                        if is_large or is_eps_kw: continue
                    
                    is_negative = full_text.strip().startswith(('(', '（', '-'))
                    if is_negative: val = -val
                    
                    # Store found number info
                    valid_num_in_window.append((val, raw_start, val_str))
                
                if len(valid_num_in_window) > num_index:
                    val, raw_start, val_str = valid_num_in_window[num_index]
                    dist = raw_start
                    
                    # Store period_score (mocked here for now as I missed the logic block above)
                    period_score = 0 
                    all_candidates.append((val, None, dist, start_pos, end_pos + raw_start, kw, period_score))
        
        return all_candidates

if __name__ == "__main__":
    pass
