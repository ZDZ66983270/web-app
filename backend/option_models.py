"""
期权数据模型扩展
添加到 backend/models.py 中
"""

from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, UniqueConstraint

class OptionData(SQLModel, table=True):
    """
    期权数据表 - 存储看跌期权的实时和历史数据
    
    设计原则:
    - 仅存储未过期的期权
    - 专注于近价看跌期权（用于风险对冲分析）
    - 支持美股和港股
    """
    __tablename__ = "option_data"
    __table_args__ = (
        UniqueConstraint("symbol", "option_symbol", "expiry_date", name="uq_option_snapshot"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 标的资产信息
    symbol: str = Field(index=True, description="标的资产代码 (如 US:STOCK:AAPL)")
    market: str = Field(index=True, description="市场 (US/HK)")
    underlying_price: float = Field(description="标的当前价格")
    
    # 期权合约信息
    option_symbol: str = Field(index=True, description="期权合约代码")
    option_type: str = Field(default="PUT", description="期权类型 (PUT/CALL)")
    strike: float = Field(description="执行价格")
    expiry_date: str = Field(index=True, description="到期日 YYYY-MM-DD")
    days_to_expiry: int = Field(description="距离到期天数")
    
    # 市场价格数据
    last_price: float = Field(description="最新成交价")
    bid: float = Field(description="买价")
    ask: float = Field(description="卖价")
    volume: int = Field(default=0, description="成交量")
    open_interest: int = Field(default=0, description="持仓量")
    
    # 希腊字母
    implied_volatility: Optional[float] = Field(default=None, description="隐含波动率")
    delta: Optional[float] = Field(default=None, description="Delta")
    gamma: Optional[float] = Field(default=None, description="Gamma")
    theta: Optional[float] = Field(default=None, description="Theta")
    vega: Optional[float] = Field(default=None, description="Vega")
    rho: Optional[float] = Field(default=None, description="Rho")
    
    # 理论定价
    theoretical_price: Optional[float] = Field(default=None, description="BS理论价格")
    
    # 元数据
    moneyness: float = Field(description="价值状态 (strike-underlying)/underlying")
    currency: str = Field(description="货币单位 (USD/HKD)")
    data_source: str = Field(default="yfinance", description="数据源")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

class OptionCSPCandidate(SQLModel, table=True):
    """
    CSP (Cash Secured Put) 候选期权表
    存储符合特定筛选条件（如DTE 45-90天, 价外3-7%）的Put期权
    """
    __tablename__ = "options_csp_candidates"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    expiry_date: str = Field(index=True)
    dte: int
    strike: float
    spot: float
    discount_pct: float = Field(description="(Spot - Strike) / Spot")
    
    mid_price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    
    # Greeks
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.now)

