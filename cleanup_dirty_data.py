import sys
import os
from sqlmodel import Session, select
from backend.database import engine
from backend.models import FinancialFundamentals

def cleanup_dirty_data():
    """
    Purge records with obvious scale errors from pdf-parser.
    """
    with Session(engine) as session:
        # 1. Tencent (00700) - Revenue should not be in millions if it's quarterly/annual
        # Screenshot showed 4.3E+8 (4.3亿) which is wrong for Tencent (usually > 100B per quarter)
        dirty_tencent = session.exec(select(FinancialFundamentals).where(
            FinancialFundamentals.symbol == 'HK:STOCK:00700',
            FinancialFundamentals.data_source == 'pdf-parser',
            FinancialFundamentals.revenue_ttm < 50_000_000_000 # < 50B is suspicious for Tencent
        )).all()
        
        # 2. Alibaba (09988) - Revenue showed 2.6E+8 in screenshot
        dirty_alibaba = session.exec(select(FinancialFundamentals).where(
            FinancialFundamentals.symbol == 'HK:STOCK:09988',
            FinancialFundamentals.data_source == 'pdf-parser',
            FinancialFundamentals.revenue_ttm < 10_000_000_000 # < 10B is suspicious
        )).all()
        
        # 3. Massive Outliers (Trillions of profit etc)
        outliers = session.exec(select(FinancialFundamentals).where(
            FinancialFundamentals.data_source == 'pdf-parser',
            FinancialFundamentals.net_income_ttm > 5_000_000_000_000 # > 5T profit (imposssible even for ICBC)
        )).all()

        to_delete = dirty_tencent + dirty_alibaba + outliers
        count = len(to_delete)
        
        if count > 0:
            print(f"🧹 Found {count} dirty records to purge.")
            for rec in to_delete:
                print(f"   Removing: {rec.symbol} {rec.as_of_date} (Rev: {rec.revenue_ttm}, NI: {rec.net_income_ttm})")
                session.delete(rec)
            session.commit()
            print(f"✅ Purged {count} records successfully.")
        else:
            print("✨ No obvious dirty records found.")

if __name__ == "__main__":
    cleanup_dirty_data()
