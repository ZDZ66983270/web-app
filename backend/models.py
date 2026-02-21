"""
VERA Data Models & Schema (数据库架构核心)
==============================================================================

本模块定义了系统的所有持久化实体，基于 SQLModel (SQLAlchemy + Pydantic) 构建。
它是整个系统“数据语言”的基石，规定了从原始采集到清洗加工、最后到应用展现的每一层格式。

架构层次:
========================================

I. Core Market Data (核心行情层)
----------------------------------------
1. **MarketDataDaily**: **日线历史库**。
   - 存储归一化后的历史日线数据（OHLCV + 估值指标）。
   - 具备唯一约束 `(symbol, market, timestamp)`。
   - 用途: 回测、长周期图表展示、估值历史回溯。
2. **MarketSnapshot**: **生产实时快照**。
   - 每个资产仅保留最新一条记录。
   - 用途: 满足前端高频访问需求（如首页自选股列表）。
   - 特性: 盘中实时更新时仅触达此表。

II. Financial & Valuation (财务与估值层)
----------------------------------------
3. **FinancialFundamentals**: **财报基础数据库**。
   - 处理过后的 PIT (Point-in-Time) 财报指标（TTM 利润、总资产、股本等）。
   - 为 `valuation_calculator.py` 提供原始输入。
4. **ForexRate**: **汇率历史库**。
   - 存储核心货币对的历史汇率（如 USD/CNY），支持估值计算时的跨币种折算。

III. User & Analysis (用户与分析层)
----------------------------------------
5. **Watchlist**: **自选股配置表**。
   - 记录用户关注的资产列表，驱动后台的定时抓取任务。
6. **AssetAnalysisHistory**: **风险评估历史**。
   - 存储 AI 驱动的深度风险评估 JSON 结果和截图路径。

IV. Infrastructure (基础设施层)
----------------------------------------
7. **RawMarketData**: **原始数据缓冲区**。
   - 存储 API 返回的原始 JSON。
   - 它是 ETL 流水线的起点，支持数据追溯与重新加工。
8. **MacroData**: **宏观经济指标**。
   - 存储美债收益率、CPI 等宏观参数。

作者: Antigravity
日期: 2026-01-23
"""

from typing import Optional
from sqlmodel import Field, SQLModel, UniqueConstraint
from datetime import datetime

class MacroData(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    country: str = Field(index=True)  # CN or US
    month: str = Field(index=True)    # YYYY-MM
    indicator: str                    # e.g., "10y_bond"
    value: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ForexRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True)       # YYYY-MM-DD
    from_currency: str = Field(index=True) 
    to_currency: str = Field(index=True)
    rate: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AssetAnalysisHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    full_result_json: str  # Stores the entire JSON result from AI
    screenshot_path: Optional[str] = None



# ============================================================
# 📚 历史数据仓库 (Historical Data Warehouse)
# ============================================================
# 用途：
#   1. 存储所有历史日线数据（可追溯数年）
#   2. 实时数据也会UPSERT到这里（更新当天记录）
#   3. ETL计算涨跌幅时查询此表的前一日收盘价
# 
# 注意：前端不直接查询此表，应查询 MarketSnapshot
# ============================================================
class MarketDataDaily(SQLModel, table=True):
    # ✅ 添加唯一约束，防止重复记录
    __table_args__ = (
        UniqueConstraint('symbol', 'market', 'timestamp', name='uq_symbol_market_timestamp'),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    market: str = Field(index=True)  # CN, HK, US
    timestamp: str = Field(index=True)    # YYYY-MM-DD HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: Optional[float] = None # 成交额
    
    # Computed/Snapshot fields (Daily usually has these calculated)
    change: Optional[float] = None
    pct_change: Optional[float] = None
    prev_close: Optional[float] = None
    
    # Valuation & Indicators 
    pe: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    dividend_yield: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[float] = None

    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)



class StockInfo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, unique=True)
    name: str
    market: str = Field(index=True) # CN, HK, US
    list_date: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Watchlist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, unique=True)
    name: Optional[str] = None
    market: Optional[str] = None # CN, HK, US, inferred
    added_at: datetime = Field(default_factory=datetime.utcnow)

class RawMarketData(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # e.g. "yahoo", "akshare"
    symbol: str
    market: str
    period: str  # '1d', '1m'
    fetch_time: datetime = Field(default_factory=datetime.utcnow)
    payload: str  # JSON serialized string
    processed: bool = Field(default=False)
    error_log: Optional[str] = None


# ============================================================
# 📸 生产快照表 (Production Snapshot)
# ============================================================
# ============================================================
# 📸 生产快照表 (Production Snapshot)
# ============================================================
# 用途：
#   1. 存储每个symbol的最新行情状态（包括盘中实时状态）
#   2. 前端API查询此表获取实时数据（包括首页列表）
#   3. 盘中数据更新时，只更新此表，不写入 MarketDataDaily
# 
# 数据流：
#   - 盘中: 数据源 → (Raw) → MarketSnapshot
#   - 收盘后: 数据源 → (Raw) → MarketDataDaily → (更新) MarketSnapshot
# ============================================================
class MarketSnapshot(SQLModel, table=True):
    """
    统一市场行情快照表 - 替代 MarketDataDaily 和 MarketDataMinute
    每个 (symbol, market) 只保留最新快照
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 唯一标识
    symbol: str = Field(index=True)
    market: str = Field(index=True)  # CN, HK, US
    
    # 价格数据
    price: float                      # 最新价（等同于close）
    open: float
    high: float
    low: float
    prev_close: Optional[float] = None
    
    # 涨跌数据
    change: float
    pct_change: float                # 涨跌幅 %
    
    # 成交数据
    volume: int
    turnover: Optional[float] = None # 成交额
    
    # 估值指标（可选）
    pe: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    
    # 元数据
    timestamp: str                        # 数据时间 YYYY-MM-DD HH:MM:SS
    data_source: str                 # 'akshare', 'yfinance', 'tencent'
    fetch_time: datetime = Field(default_factory=datetime.utcnow)  # 获取时间
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # 更新时间
    
    class Config:
        # 唯一约束：每个symbol+market组合只能有一条记录
        # SQLModel会自动创建唯一索引
        table_args = {'sqlite_autoincrement': True}

# ============================================================
# 📊 财务基本面数据 (Financial Fundamentals)
# ============================================================
# 用途：
#   1. 存储个股的财务基本面数据（季度/年度/TTM）
#   2. 包含营收、利润、现金流、资产负债等核心指标
#   3. 通常由 fetch_financials.py 定期更新 (e.g. weekly/monthly)
# ============================================================
class FinancialFundamentals(SQLModel, table=True):
    """
    财务基本面数据表 (Financial Fundamentals)
    
    用途：
    - 存储个股的财务基本面数据（季度/年度/TTM）
    - 包含营收、利润、现金流、资产负债等核心指标
    - 支持通用企业和银行两类业务
    
    字段标准：
    - 参考: backend/config/generic_fundamentals_core.yaml
    - 通用企业核心字段：24 个（required=true 的字段）
    - 银行专属字段：9 个（仅银行业使用）
    """
    # Composite Unique Constraint: symbol + as_of_date + data_source
    # Allows multiple sources to coexist for the same date for record integrity
    __table_args__ = (
        UniqueConstraint('symbol', 'as_of_date', 'data_source', name='uq_fund_symbol_date_source'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)  # Corresponds to asset_id
    as_of_date: str = Field(index=True)   # YYYY-MM-DD
    report_type: str = Field(default='annual')  # 'annual' or 'quarterly'
    
    # ========================================
    # 通用企业核心字段 (Generic Enterprise Core Fields)
    # 参考: backend/config/generic_fundamentals_core.yaml
    # ========================================
    
    # --- 盈利与现金流 (Profitability & Cash Flow) ---
    revenue_ttm: Optional[float] = None  # YAML: revenue_ttm (aligned)
    net_income_ttm: Optional[float] = None
    net_income_common_ttm: Optional[float] = None  
    # YAML标准名: net_income_attributable_to_common_ttm (aliased)
    # 归属于普通股股东的净利润（TTM）
    
    gross_profit_ttm: Optional[float] = None  # YAML: gross_profit_ttm (aligned)
    operating_profit_ttm: Optional[float] = None  # YAML: operating_profit_ttm (aligned)
    ebit_ttm: Optional[float] = None  # YAML: ebit_ttm (aligned)
    r_and_d_expense_ttm: Optional[float] = None  # YAML: r_and_d_expense_ttm (aligned)
    interest_expense_ttm: Optional[float] = None  # YAML: interest_expense_ttm (aligned)
    non_recurring_profit_ttm: Optional[float] = None  # YAML: non_recurring_profit_ttm (aligned)
    
    eps: Optional[float] = None
    # YAML标准名: eps_ttm (aliased)
    # 每股收益（TTM），用于 PE 估值
 
    eps_diluted: Optional[float] = None # Added for VERA: Diluted EPS
    shares_diluted: Optional[float] = None # Added for VERA: Weighted Average Diluted Shares
    filing_date: Optional[str] = None # Added for VERA: PIT Compliance (YYYY-MM-DD)
    
    # --- 现金流 (Cash Flow) ---
    operating_cashflow_ttm: Optional[float] = None  # YAML: operating_cashflow_ttm (aligned)
    free_cashflow_ttm: Optional[float] = None  # YAML: free_cashflow_ttm (aligned)
    capex_ttm: Optional[float] = None  # YAML: capex_ttm (aligned)
    dividends_paid_cashflow: Optional[float] = None  # YAML: dividends_paid_cashflow (aligned)
    share_buyback_amount_ttm: Optional[float] = None  # YAML: share_buyback_amount_ttm (aligned)
    
    # --- 资产负债 (Balance Sheet) ---
    total_assets: Optional[float] = None  # YAML: total_assets (aligned)
    total_liabilities: Optional[float] = None  # YAML: total_liabilities (aligned)
    total_debt: Optional[float] = None  # YAML: total_debt (aligned)
    cash_and_equivalents: Optional[float] = None  # YAML: cash_and_equivalents (aligned)
    net_debt: Optional[float] = None
    
    # --- 营运资本 (Working Capital) ---
    accounts_receivable_end: Optional[float] = None  # YAML: accounts_receivable_end (aligned)
    inventory_end: Optional[float] = None  # YAML: inventory_end (aligned)
    accounts_payable_end: Optional[float] = None  # YAML: accounts_payable_end (aligned)
    common_equity_begin: Optional[float] = None
    common_equity_end: Optional[float] = None  # YAML: common_equity_end (aligned)
    
    # ========================================
    # 银行专属字段 (Bank-Specific Fields)
    # 仅适用于银行业，通用企业为 NULL
    # ========================================
    total_loans: Optional[float] = None
    loan_loss_allowance: Optional[float] = None
    npl_balance: Optional[float] = None
    npl_ratio: Optional[float] = None
    provision_coverage: Optional[float] = None
    core_tier1_ratio: Optional[float] = None
    provision_expense: Optional[float] = None
    net_interest_income: Optional[float] = None
    net_fee_income: Optional[float] = None
    short_term_debt: Optional[float] = None
    long_term_debt: Optional[float] = None
    
    # --- 杠杆与覆盖 (Leverage & Coverage) ---
    debt_to_equity: Optional[float] = None
    interest_coverage: Optional[float] = None
    current_ratio: Optional[float] = None
    
    # --- 股东回报 (Shareholder Returns) ---
    dividend_yield: Optional[float] = None
    dividend_amount: Optional[float] = None # Added: Total Dividends Paid (Absolute)
    dividend_per_share: Optional[float] = None  # YAML: dividend_per_share (aligned)
    shares_outstanding_common_end: Optional[float] = None  # YAML: shares_outstanding_common_end (aligned)
    payout_ratio: Optional[float] = None
    buyback_ratio: Optional[float] = None
    buyback_amount: Optional[float] = None # Added for VERA: Cash used for buybacks
    treasury_shares: Optional[float] = None # Added for VERA: Treasury Shares count/value
    
    # --- 资本回报 (Returns) ---
    return_on_invested_capital: Optional[float] = None # Added for VERA: ROIC
    
    # --- AI & CapEx Model (New Tier 1 Metrics) ---
    capex_cash_additions_3m: Optional[float] = None
    ppe_total_net: Optional[float] = None
    ppe_servers_net: Optional[float] = None
    ppe_buildings_net: Optional[float] = None
    amortization_intangibles_6m: Optional[float] = None
    lease_ppe_finance_net: Optional[float] = None
    lease_rou_assets_operating: Optional[float] = None
    lease_capex_operating_additions_6m: Optional[float] = None
    strategic_ai_investment_funded: Optional[float] = None

    # --- 增强银行指标 (Enhanced Banking) ---
    allowance_to_loan: Optional[float] = None
    overdue_90_loans: Optional[float] = None
    tier1_capital_ratio: Optional[float] = None
    capital_adequacy_ratio: Optional[float] = None

    
    # --- 元信息 (Meta) ---
    data_source: str = Field(default='yahoo')
    currency: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================================
# 📏 标准导出列清单 (55-Column Standard)
# ============================================================
FINANCIAL_EXPORT_COLUMNS = [
    # 1. 标识与元数据 (7)
    'symbol', 'as_of_date', 'report_type', 'filing_date', 'currency', 'data_source', 'created_at',
    
    # 2. 核心盈利指标 (10)
    'revenue_ttm', 'gross_profit_ttm', 'operating_profit_ttm', 'ebit_ttm',
    'net_income_ttm', 'net_income_common_ttm', 'non_recurring_profit_ttm',
    'r_and_d_expense_ttm', 'interest_expense_ttm', 'provision_expense',
    
    # 3. 现金流指标 (6)
    'operating_cashflow_ttm', 'capex_ttm', 'free_cashflow_ttm',
    'investing_cashflow_ttm', 'financing_cashflow_ttm', 'share_buyback_amount_ttm',
    
    # 4. 资产负债指标 (9)
    'total_assets', 'total_liabilities', 'total_debt', 'net_debt',
    'cash_and_equivalents', 'common_equity_end',
    'accounts_receivable_end', 'inventory_end', 'accounts_payable_end',
    
    # 5. 银行专属指标 (13)
    'total_loans', 'loan_loss_allowance', 'npl_balance', 'npl_ratio',
    'provision_coverage', 'core_tier1_ratio', 'net_interest_income', 'net_fee_income',
    'long_term_debt', 'allowance_to_loan', 'overdue_90_loans', 'tier1_capital_ratio', 'capital_adequacy_ratio',
    
    # 6. 每股与股利指标 (10)
    'eps', 'eps_diluted', 'dividend_per_share', 'dividend_amount', 'dividend_yield',
    'payout_ratio', 'shares_outstanding_common_end', 'buyback_amount', 'shares_diluted', 'treasury_shares',
    
    # 7. 效率与安全性指标 (10)
    'debt_to_equity', 'interest_coverage', 'current_ratio', 'buyback_ratio',
    'return_on_invested_capital', 'common_equity_begin', 'short_term_debt',
    'strategic_ai_investment_funded', 'ppe_total_net', 'ppe_servers_net',

    # 8. AI与算力专属 (6)
    'capex_cash_additions_3m', 'ppe_buildings_net', 'amortization_intangibles_6m',
    'lease_ppe_finance_net', 'lease_rou_assets_operating', 'lease_capex_operating_additions_6m'
]
