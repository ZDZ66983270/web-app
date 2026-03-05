import sys
import os
import pandas as pd
from sqlmodel import Session, select

# Add backend to path
sys.path.append('backend')
from database import engine
from models import FinancialFundamentals

def check_pltr_completeness():
    SYMBOL = 'US:STOCK:PLTR'
    print(f"Checking financial data completeness for {SYMBOL}...")
    
    with Session(engine) as session:
        statement = select(FinancialFundamentals).where(FinancialFundamentals.symbol == SYMBOL).order_by(FinancialFundamentals.as_of_date.desc())
        results = session.exec(statement).all()
        
        if not results:
            print(f"❌ No financial data found for {SYMBOL} in database.")
            return

        data = []
        for r in results:
            # Count non-null financial metrics
            metrics = [
                r.revenue, r.net_income, r.total_assets, r.total_liabilities, r.total_equity,
                r.operating_cash_flow, r.capital_expenditure, r.cash_and_equivalents, r.total_debt
            ]
            non_null_count = sum(1 for m in metrics if m is not None)
            
            data.append({
                "Date": r.as_of_date,
                "Type": r.report_type,
                "Source": r.data_source,
                "Metrics (Filled/9)": f"{non_null_count}/9",
                "Revenue": f"${r.revenue/1e6:,.1f}M" if r.revenue else "Missing",
                "Net Income": f"${r.net_income/1e6:,.1f}M" if r.net_income else "Missing"
            })
            
        df = pd.DataFrame(data)
        print("\n--- Financial Data Summary ---")
        print(df.to_string(index=False))
        
        # Summary statistics
        annual_count = sum(1 for d in data if d['Type'] == 'annual')
        quarterly_count = sum(1 for d in data if d['Type'] == 'quarterly')
        print(f"\n📊 Total Records: {len(data)} (Annual: {annual_count}, Quarterly: {quarterly_count})")
        
        latest_date = df['Date'].max()
        print(f"📅 Latest Data Date: {latest_date}")

if __name__ == "__main__":
    check_pltr_completeness()
