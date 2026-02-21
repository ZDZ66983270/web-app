import yaml
import os
import sys
import pandas as pd

# Add backend to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from models import FinancialFundamentals

from sqlmodel import Session, create_engine, select

def check_completeness(symbol: str):
    # Actual fields in FinancialFundamentals for Banks
    fields = [
        "total_assets", "total_liabilities", "common_equity_begin", "common_equity_end",
        "revenue_ttm", "net_income_ttm", "net_interest_income", "net_fee_income", "provision_expense",
        "total_loans", "loan_loss_allowance", "npl_balance", "npl_ratio", "provision_coverage",
        "core_tier1_ratio", "eps", "shares_outstanding_common_end", "dividend_amount", "dividend_per_share",
        "operating_cashflow_ttm", "cash_and_equivalents", "total_debt", "short_term_debt", "long_term_debt"
    ]
    
    # Database connection
    db_path = "backend/database.db"
    if not os.path.exists(db_path):
        db_path = "web-app/backend/database.db"
    engine = create_engine(f"sqlite:///{db_path}")
    
    with Session(engine) as session:
        statement = select(FinancialFundamentals).where(FinancialFundamentals.symbol == symbol).order_by(FinancialFundamentals.as_of_date.desc())
        results = session.exec(statement).all()
        
    if not results:
        print(f"No records found for {symbol}")
        return

    data = []
    for r in results:
        row = {"date": r.as_of_date}
        for field in fields:
            val = getattr(r, field, None)
            row[field] = "✅" if val is not None else "❌"
        data.append(row)

    df = pd.DataFrame(data)
    
    # Calculate coverage per field
    coverage = {}
    for field in fields:
        count = sum(1 for d in data if d[field] == "✅")
        coverage[field] = f"{count}/{len(data)}"
    
    # Sort dates to show recent first
    df = df.sort_values("date", ascending=False)
    
    print(f"\nData Completeness Report for {symbol} ({len(results)} records):\n")
    # Show only top 20 for brevity if needed, but here we want completeness
    print(df.to_markdown(index=False))
    
    print("\nSummary Coverage per Metric:")
    for field, cov in coverage.items():
        print(f"  - {field}: {cov}")

if __name__ == "__main__":
    check_completeness("CN:STOCK:601998")
