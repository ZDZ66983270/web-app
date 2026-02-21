from typing import List, Dict

# 银行专用关键词映射 (从 PDF 中提取)
# Key: 内部字段名 (consistent with fundamentals_bank.yaml)
# Value: List[List[str]] -> 优先级分组列表
#        每个子列表代表一组同义词（或 regex 模式），用于匹配 PDF 内容
#        优先级从前到后递减

BANK_KEYWORDS = {
    # 1. 资产负债表 (Scale)
    "total_assets": [
        ["资产总计", "资产总额", "Total Assets", "資產總額", "資產總值", "資產合計", "資產總計", "總資產"],
        ["资产合计"]
    ],
    "total_liabilities": [
        ["负债总计", "负债总额", "Total Liabilities", "負債總額", "負債合計", "負債總計", "總負債"],
        ["负债合计"]
    ],
    "common_equity_begin": [
        ["归属于本行股东权益 ... 本年初", "上年末归属于本行股东权益", "歸屬於本行股東權益 ... 本年初"],
        ["期初股东权益", "年初股东权益", "Equity at beginning", "期初股東權益", "年初股東權益"],
        ["归属于母公司股东权益期初余额", "股东权益合计 ... 本年初", "股東權益合計 ... 本年初"]
    ],
    "common_equity_end": [
        ["归属于本行股东权益 ... 本年末", "本年末归属于本行股东权益", "歸屬於本行股東權益 ... 本年末"],
        ["期末股东权益", "年末股东权益", "Equity at end", "期末股東權益", "年末股東權益"],
        ["归属于本行股东权益", "归属于普通股股东的权益", "歸屬於本行股東權益"],
        ["归属于母公司股东权益", "Total Equity Attributable to Equity Holders", "股东权益合计", "股東權益合計"]
    ],

    # 2. 利润表 (Income) - 银行业特殊
    "revenue": [
        ["营业收入合计", "营业收入总额", "营业总收入", "營業總收入", "營業收入合計"],
        ["营业收入", "Operating Income", "Revenue", "營業支出", "營業收入", "收益", "收入"],
        ["收入总额", "收入總額"]
    ],
    "net_profit": [
        ["归属于母公司股东的净利润", "Net Profit Attributable to Equity Holders", "歸屬於本行股東的溢利", "⺟公司普通股股東", "普通股股東應佔利潤"],
        ["归属于本行股东的净利润", "归属于本股东的净利润", "歸屬於本行股東的淨利潤", "除稅後利潤", "除税后利润", "期內溢利"],
        ["净利润", "Net Profit", "淨利潤", "溢利", "本年度溢利", "期內溢利"] 
    ],
    "net_interest_income": [
        ["利息净收入", "Net Interest Income", "利息淨收入", "利息收入淨額"]
    ],
    "net_fee_income": [
        ["手续费及佣金净收入", "Net Fee and Commission Income", "手續費及佣金淨收入", "服務費及佣金收入淨額"],
        ["净手续费及佣金收入", "淨手續費及佣金收入"]
    ],
    "provision_expense": [
        ["信用减值损失", "Credit Impairment Losses", "Provision for Impairment", "信⽤減值損失"],
        ["资产减值损失", "資產減值損失"] # 旧准则
    ],

    # 3. 资产质量
    "total_loans": [
        ["贷款和垫款总额", "发放贷款和垫款总额", "Total Loans and Advances"],
        ["发放贷款和垫款合计", "贷款和垫款合计"],
        ["发放贷款和垫款", "Loans and Advances to Customers", "Gross Loans"]
    ],
    "loan_loss_allowance": [
        ["贷款损失准备合计", "贷款减值准备合计"],
        ["贷款损失准备", "Loan Loss Allowance", "Allowance for Impairment Losses"],
        ["贷款减值准备"]
    ],
    "npl_balance": [
        ["不良贷款总额", "不良贷款余额合计"],
        ["不良贷款余额", "Non-performing Loan Balance", "Impaired Loans"],
        ["不良贷款"]
    ],
    "npl_ratio": [
        ["不良贷款率", "NPL Ratio", "Impaired Loan Ratio"],
        ["不良率"]
    ],
    "provision_coverage": [
        ["拨备覆盖率", "Provision Coverage Ratio", "Allowance Coverage Ratio"]
    ],
    "core_tier1_ratio": [
        ["核心一级资本充足率", "Core Tier 1 Capital Adequacy Ratio", "CET1 Ratio"]
    ],
    "tier1_capital_ratio": [
        ["一级资本充足率", "Tier 1 Capital Adequacy Ratio", "Tier 1 Ratio"]
    ],
    "capital_adequacy_ratio": [
        ["资本充足率", "Capital Adequacy Ratio", "CAR"]
    ],
    "allowance_to_loan": [
        ["贷款拨备率", "Allowance to Loan Ratio"]
    ],
    "overdue_90_loans": [
        ["逾期90天以上贷款", "Overdue 90 Days Loans"]
    ],

    # 4. 股票数据
    "eps": [
        ["基本每股收益", "Basic Earnings Per Share", "Basic EPS"],
        ["每股收益", "每股收益(元/股)", "每股净利润"]
    ],
    "shares_outstanding": [
        ["普通股股份总数(股)", "普通股股份总数", "期末股份总数", "股份總數", "普通股總數"],
        ["期末总股本", "Total Shares Outstanding", "Issued Share Capital", "已發行股本", "已發行股份"],
        ["总股本", "股本总额", "普通股总股本", "總股本"],
        ["股本", "Share Capital"]
    ],
    "dividends_paid": [
        ["现金分红总额(含税)", "现金分红总额", "分配现金红利总额", "Dividends Paid"],
        ["分配股利", "已支付股利"]
    ],
    "dividend_per_share": [
        ["每10股派现金", "每10股派发现金红利", "每10股派派", "每10股派息"],
        ["每股股利", "Dividend Per Share", "DPS", "每股派息"],
        ["每股现金分红", "每股分配", "分红方案：每股"]
    ],

    # 5. 现金流与债务
    "operating_cashflow": [
        ["经营活动产生的现金流量净额", "Net Cash from Operating Activities"],
        ["经营活动现金流净额"]
    ],
    "cash_and_equivalents": [
        ["现金及现金等价物余额", "Cash and Cash Equivalents at End of Period"],
        ["期末现金及现金等价物余额", "现金及现金等价物", "库存现金", "Balance of Cash and Cash Equivalents"],
        ["现金及等价物"]
    ],
    "total_debt": [
        ["有息负债"],
        # 银行没有典型的"有息负债"科目，通常需要计算
        # 这里仅列出为了兼容
        ["应付债券", "Bonds Payable"] 
    ],
    "short_term_debt": [
        ["短期借款", "Short-term borrowings"],
        ["向中央银行借款", "拆入资金", "同业及其他金融机构存放款项"]
    ],
    "long_term_debt": [
        ["长期借款", "Long-term borrowings"],
        ["应付债券", "已发行债券", "Bonds Payable"]
    ]
}

def get_keywords_for_bank(asset_id: str, metric_name: str) -> List[List[str]]:
    """
    根据资产 ID 和指标名获取关键词列表。
    目前逻辑比较简单，直接返回通用银行关键词。
    未来可以根据 asset_id (e.g. HK vs CN) 返回繁体/简体偏好的列表。
    """
    keywords = BANK_KEYWORDS.get(metric_name, [])
    
    # 简单的本地化增强示例
    if asset_id and "HK" in asset_id:
        # TODO: 可以动态添加繁体关键词
        pass
        
    return keywords
