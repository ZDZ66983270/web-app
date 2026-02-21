
import sys
import os
from sqlalchemy import create_engine, text

# Add backend to path (parent of scripts/backend -> ../backend)
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.database import engine

def migrate():
    print("🚀 Starting Database Migration (Add More Financial Fields)...")
    
    # Generic Template Fields + Bank Template + US Fetcher Fields
    # We add them as nullable floats
    cols_to_add = [
        # Income
        ("gross_profit_ttm", "FLOAT"),
        ("operating_profit_ttm", "FLOAT"),
        ("ebit_ttm", "FLOAT"),
        ("r_and_d_expense_ttm", "FLOAT"),
        ("interest_expense_ttm", "FLOAT"),
        ("non_recurring_profit_ttm", "FLOAT"),
        
        # Working Capital & Balance Sheet
        ("accounts_receivable_end", "FLOAT"),
        ("inventory_end", "FLOAT"),
        ("accounts_payable_end", "FLOAT"),
        ("common_equity_begin", "FLOAT"),
        ("common_equity_end", "FLOAT"), # Might duplicate total_equity in concept but useful
        
        # Cashflow
        ("capex_ttm", "FLOAT"),
        ("dividends_paid_cashflow", "FLOAT"),
        ("share_buyback_amount_ttm", "FLOAT"),
        
        # Bank Specific (Asset Quality)
        ("total_loans", "FLOAT"),
        ("loan_loss_allowance", "FLOAT"),
        ("npl_balance", "FLOAT"),
        ("npl_ratio", "FLOAT"),
        ("provision_coverage", "FLOAT"),
        ("core_tier1_ratio", "FLOAT"),
        ("provision_expense", "FLOAT"), # Income statement for banks
        ("net_interest_income", "FLOAT"),
        ("net_fee_income", "FLOAT"),
        
        # Per Share
        ("shares_outstanding_common_end", "FLOAT"),
        ("dividend_per_share", "FLOAT"),
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in cols_to_add:
            try:
                # Try simple select to check column
                conn.execute(text(f"SELECT {col_name} FROM financialfundamentals LIMIT 1"))
                print(f"✅ Column '{col_name}' already exists.")
            except Exception:
                print(f"✨ Adding column '{col_name}'...")
                try:
                    conn.execute(text(f"ALTER TABLE financialfundamentals ADD COLUMN {col_name} {col_type}"))
                except Exception as e:
                    print(f"   ❌ Failed to add {col_name}: {e}")

        conn.commit()
    
    print("✅ Migration Complete.")

if __name__ == "__main__":
    migrate()
