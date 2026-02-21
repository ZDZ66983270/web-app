import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "database.db")
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    new_columns = [
        # Returns
        ('return_on_invested_capital', 'FLOAT'),
        
        # Shareholder returns
        ('buyback_amount', 'FLOAT'),
        ('treasury_shares', 'FLOAT'),
        
        # AI & CapEx Model
        ('capex_cash_additions_3m', 'FLOAT'),
        ('ppe_total_net', 'FLOAT'),
        ('ppe_servers_net', 'FLOAT'),
        ('ppe_buildings_net', 'FLOAT'),
        ('amortization_intangibles_6m', 'FLOAT'),
        ('lease_ppe_finance_net', 'FLOAT'),
        ('lease_rou_assets_operating', 'FLOAT'),
        ('lease_capex_operating_additions_6m', 'FLOAT'),
        ('strategic_ai_investment_funded', 'FLOAT'),
        
        # Enhanced Banking
        ('allowance_to_loan', 'FLOAT'),
        ('overdue_90_loans', 'FLOAT'),
        ('tier1_capital_ratio', 'FLOAT'),
        ('capital_adequacy_ratio', 'FLOAT')
    ]
    
    try:
        # Check existing columns in financialfundamentals
        cursor.execute("PRAGMA table_info(financialfundamentals)")
        existing_cols = [info[1] for info in cursor.fetchall()]
        
        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                print(f"Adding column '{col_name}' to financialfundamentals...")
                cursor.execute(f"ALTER TABLE financialfundamentals ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column '{col_name}' already exists.")
            
        conn.commit()
        print("✅ FinancialFundamentals migration successful.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
