
import sys
sys.path.append('backend')
from database import engine
from models import MarketDataDaily, FinancialFundamentals
from sqlmodel import Session, select
import pandas as pd

def test_ps_calc(symbol):
    with Session(engine) as session:
        # 1. 获取最新营收
        stmt_fin = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        fin = session.exec(stmt_fin).first()
        if not fin or not fin.revenue_ttm:
            print(f"❌ 找不到营收数据: {symbol}")
            return
            
        print(f"✅ 找到营收: {fin.revenue_ttm} (日期: {fin.as_of_date}, 来源: {fin.data_source})")
        
        # 2. 获取总股本 (优先从财务获取)
        shares = fin.shares_outstanding_common_end or fin.shares_diluted
        if not shares:
            print(f"⚠️ 找不到股本数据，尝试从 snapshot 获取市值推算...")
            return
            
        print(f"✅ 找到股本: {shares}")
        
        # 3. 获取日线价格
        stmt_price = select(MarketDataDaily).where(MarketDataDaily.symbol == symbol).order_by(MarketDataDaily.timestamp.desc()).limit(5)
        prices = session.exec(stmt_price).all()
        
        for p in prices:
            mkt_cap = p.close * shares
            ps = mkt_cap / fin.revenue_ttm
            print(f"📅 {p.timestamp} | Price: {p.close} | Calc PS: {ps:.3f}")

if __name__ == "__main__":
    test_ps_calc('HK:STOCK:00700')
    test_ps_calc('HK:STOCK:01919')
