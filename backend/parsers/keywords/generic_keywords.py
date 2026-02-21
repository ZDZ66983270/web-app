"""
通用企业财报关键词库 (Generic Enterprise Keywords)
==================================================

用途：
- 为非银行企业的财报解析提供关键词匹配
- 支持制造业、科技、消费、化工等行业
- 与银行关键词库（bank_keywords.py）互补

作者: Antigravity
日期: 2026-02-02
"""

# ========================================
# 利润表关键词 (Income Statement)
# ========================================

# 营业收入 (Revenue)
# 营业收入 (Revenue)
REVENUE_KEYWORDS = [
    "营业收入", "主营业务收入", "营业总收入", "營業額", "收益總額", "總收益", "總收入",
    "Operating Revenue", "Total Revenue", "Turnover", "Revenue",
    "销售收入", "营收", "营收总额", "營業收入"
]

# 营业成本 (Cost of Revenue)
COST_OF_REVENUE_KEYWORDS = [
    "营业成本", "主营业务成本", "销售成本",
    "Cost of Revenue", "Cost of Sales",
    "营业总成本"
]

# 毛利 (Gross Profit)
GROSS_PROFIT_KEYWORDS = [
    "毛利", "销售毛利",
    "Gross Profit",
    # 注意：通常需要计算 = 营业收入 - 营业成本
]

# 营业利润 (Operating Profit)
OPERATING_PROFIT_KEYWORDS = [
    "营业利润", "经营利润", "业务利润",
    "Operating Profit", "Operating Income",
    "EBIT"  # 息税前利润
]

# 利润总额 (Total Profit)
TOTAL_PROFIT_KEYWORDS = [
    "利润总额", "税前利润",
    "Total Profit", "Profit Before Tax",
    "EBT"
]

# 净利润 (Net Profit)
NET_PROFIT_KEYWORDS = [
    "净利润", "归属于母公司所有者的净利润", 
    "归属于母公司股东的净利润", "归母净利润",
    "Net Profit", "Net Income",
    "归属于上市公司股东的净利润", "期内溢利", "期内利润", "期内盈利", "年度溢利", "季度溢利", "本季度净利润",
    "期內溢利", "期內利潤", "期內盈利", "淨利潤", "年度溢利", "季度溢利"
]

# 研发费用 (R&D Expense)
RD_EXPENSE_KEYWORDS = [
    "研发费用", "研究开发费用", "研发支出",
    "R&D Expense", "Research and Development",
    "技术开发费"
]

# 销售费用 (Selling Expense)
SELLING_EXPENSE_KEYWORDS = [
    "销售费用", "销售及分销费用",
    "Selling Expense", "Sales Expense"
]

# 管理费用 (Administrative Expense)
ADMIN_EXPENSE_KEYWORDS = [
    "管理费用", "一般及行政费用",
    "Administrative Expense", "G&A Expense"
]

# 财务费用 (Finance Expense)
FINANCE_EXPENSE_KEYWORDS = [
    "财务费用", "利息费用", "利息支出",
    "Finance Expense", "Interest Expense"
]

# ========================================
# 资产负债表关键词 (Balance Sheet)
# ========================================

# 总资产 (Total Assets)
TOTAL_ASSETS_KEYWORDS = [
    "资产总计", "总资产", "资产合计", "資產總值", "資產總計", "資產合計", "總資產",
    "Total Assets"
]

# 总负债 (Total Liabilities)
TOTAL_LIABILITIES_KEYWORDS = [
    "负债合计", "总负债", "负债总计", "負債總額", "負債合計", "負債總計", "總負債",
    "Total Liabilities"
]

# 股东权益 (Shareholders' Equity)
EQUITY_KEYWORDS = [
    "股东权益合计", "所有者权益合计", "归属于母公司所有者权益合计",
    "Total Equity", "Shareholders' Equity",
    "归属于母公司股东权益合计"
]

# 货币资金 (Cash and Cash Equivalents)
CASH_KEYWORDS = [
    "货币资金", "现金及现金等价物", "现金",
    "Cash and Cash Equivalents", "Cash"
]

# 应收账款 (Accounts Receivable)
RECEIVABLES_KEYWORDS = [
    "应收账款", "应收票据及应收账款",
    "Accounts Receivable", "Trade Receivables"
]

# 存货 (Inventory)
INVENTORY_KEYWORDS = [
    "存货", "库存商品",
    "Inventory", "Inventories"
]

# 应付账款 (Accounts Payable)
PAYABLES_KEYWORDS = [
    "应付账款", "应付票据及应付账款",
    "Accounts Payable", "Trade Payables"
]

# 短期借款 (Short-term Debt)
SHORT_TERM_DEBT_KEYWORDS = [
    "短期借款", "短期债务",
    "Short-term Borrowings", "Short-term Debt"
]

# 长期借款 (Long-term Debt)
LONG_TERM_DEBT_KEYWORDS = [
    "长期借款", "长期债务", "长期应付款",
    "Long-term Borrowings", "Long-term Debt"
]

# ========================================
# 现金流量表关键词 (Cash Flow Statement)
# ========================================

# 经营活动现金流 (Operating Cash Flow)
OPERATING_CASHFLOW_KEYWORDS = [
    "经营活动产生的现金流量净额", "经营活动现金流量净额",
    "经营性现金流", "经营现金流",
    "Net Cash from Operating Activities",
    "Operating Cash Flow"
]

# 投资活动现金流 (Investing Cash Flow)
INVESTING_CASHFLOW_KEYWORDS = [
    "投资活动产生的现金流量净额", "投资活动现金流量净额",
    "Net Cash from Investing Activities"
]

# 筹资活动现金流 (Financing Cash Flow)
FINANCING_CASHFLOW_KEYWORDS = [
    "筹资活动产生的现金流量净额", "筹资活动现金流量净额",
    "Net Cash from Financing Activities"
]

# 资本性支出 (Capital Expenditure)
CAPEX_KEYWORDS = [
    "购建固定资产、无形资产和其他长期资产支付的现金",
    "购建固定资产支付的现金",
    "Capital Expenditure", "Capex",
    "固定资产投资"
]

# ========================================
# 每股指标关键词 (Per-share Metrics)
# ========================================

# 每股收益 (EPS)
EPS_KEYWORDS = [
    "基本每股收益", "每股收益", "稀释每股收益",
    "Basic EPS", "Diluted EPS", "EPS",
    "基本每股盈利", "每股盈利", "每股盈餘", "基本每股盈餘"
]

# 每股净资产 (Book Value per Share)
BVPS_KEYWORDS = [
    "每股净资产", "归属于母公司股东的每股净资产",
    "Book Value per Share", "BVPS"
]

# 每股经营现金流 (Operating Cash Flow per Share)
OCF_PER_SHARE_KEYWORDS = [
    "每股经营活动产生的现金流量净额",
    "Operating Cash Flow per Share"
]

# ========================================
# 股本与分红关键词 (Shares & Dividends)
# ========================================

# 股本 (Shares Outstanding - Number of Shares)
SHARES_OUTSTANDING_KEYWORDS = [
    "普通股总数", "股份总数", "发行在外股份", "普通股股数", "期末总股本",
    "Number of Shares", "Total Number of Issued Shares", "Shares Outstanding",
    "已发行股份总数", "已发行股数", "已發行股份", "已發行股數", "股份總數"
]
# 警告：避免使用 "股本", "总股本", "实收资本", 因为在港股中它们通常代表金额而不是股数。

# 分红 (Dividends)
DIVIDEND_KEYWORDS = [
    "分配股利、利润或偿付利息支付的现金",
    "支付的股利", "现金分红",
    "Dividends Paid", "Cash Dividends"
]

# 每股股利 (Dividend per Share)
DPS_KEYWORDS = [
    "每股股利", "每股分红", "每股派息",
    "Dividend per Share", "DPS"
]

# ========================================
# 辅助函数
# ========================================

def get_all_keywords():
    """获取所有关键词的字典"""
    return {
        "revenue": REVENUE_KEYWORDS,
        "cost_of_revenue": COST_OF_REVENUE_KEYWORDS,
        "gross_profit": GROSS_PROFIT_KEYWORDS,
        "operating_profit": OPERATING_PROFIT_KEYWORDS,
        "total_profit": TOTAL_PROFIT_KEYWORDS,
        "net_profit": NET_PROFIT_KEYWORDS,
        "rd_expense": RD_EXPENSE_KEYWORDS,
        "selling_expense": SELLING_EXPENSE_KEYWORDS,
        "admin_expense": ADMIN_EXPENSE_KEYWORDS,
        "finance_expense": FINANCE_EXPENSE_KEYWORDS,
        "total_assets": TOTAL_ASSETS_KEYWORDS,
        "total_liabilities": TOTAL_LIABILITIES_KEYWORDS,
        "equity": EQUITY_KEYWORDS,
        "cash": CASH_KEYWORDS,
        "receivables": RECEIVABLES_KEYWORDS,
        "inventory": INVENTORY_KEYWORDS,
        "payables": PAYABLES_KEYWORDS,
        "short_term_debt": SHORT_TERM_DEBT_KEYWORDS,
        "long_term_debt": LONG_TERM_DEBT_KEYWORDS,
        "operating_cashflow": OPERATING_CASHFLOW_KEYWORDS,
        "investing_cashflow": INVESTING_CASHFLOW_KEYWORDS,
        "financing_cashflow": FINANCING_CASHFLOW_KEYWORDS,
        "capex": CAPEX_KEYWORDS,
        "eps": EPS_KEYWORDS,
        "bvps": BVPS_KEYWORDS,
        "ocf_per_share": OCF_PER_SHARE_KEYWORDS,
        "shares_outstanding": SHARES_OUTSTANDING_KEYWORDS,
        "dividend": DIVIDEND_KEYWORDS,
        "dps": DIVIDEND_KEYWORDS,
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

def is_bank_specific_keyword(keyword: str) -> bool:
    """
    判断关键词是否为银行专属
    
    Args:
        keyword: 关键词
    
    Returns:
        是否为银行专属关键词
    """
    bank_specific = [
        "贷款", "存款", "不良", "拨备", "资本充足率",
        "利息净收入", "手续费净收入", "核心一级资本"
    ]
    return any(bs in keyword for bs in bank_specific)
