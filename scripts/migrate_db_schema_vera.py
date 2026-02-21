
import sys
import os
from sqlalchemy import create_engine, text

# Add backend to path (parent of scripts/backend -> ../backend)
# Correct: we are in scripts/, backend is in ../backend
# But running from root: sys.path.append('backend') is enough if running as `python3 scripts/script.py`?
# The script uses __file__. dirname(__file__) is .../scripts.
# We want .../backend.
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
from database import engine

def migrate():
    print("🚀 Starting Database Migration for VERA Upgrade...")
    
    with engine.connect() as conn:
        # 1. Create ForexRate table if not exists (handled by SQLModel usually, but manual here for safely)
        # Actually simplest way for new table is let SQLModel create it if we run the app, 
        # but for existing tables we need ALTER.
        
        # Check if ForexRate exists
        try:
            conn.execute(text("SELECT 1 FROM forexrate LIMIT 1"))
            print("✅ Table 'forexrate' already exists.")
        except Exception:
            print("✨ Creating 'forexrate' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS forexrate (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date VARCHAR NOT NULL,
                    from_currency VARCHAR NOT NULL,
                    to_currency VARCHAR NOT NULL,
                    rate FLOAT NOT NULL,
                    updated_at DATETIME NOT NULL
                );
            """))
            # Indices
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_forexrate_date ON forexrate (date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_forexrate_from_currency ON forexrate (from_currency)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_forexrate_to_currency ON forexrate (to_currency)"))

        # 2. Add columns to financialfundamentals
        # We need to check if they exist first to avoid error in SQLite
        
        cols_to_add = [
            ("net_income_common_ttm", "FLOAT"),
            ("eps_diluted", "FLOAT"),
            ("shares_diluted", "FLOAT"),
            ("filing_date", "VARCHAR")
        ]
        
        for col_name, col_type in cols_to_add:
            try:
                # Try simple select to check column
                conn.execute(text(f"SELECT {col_name} FROM financialfundamentals LIMIT 1"))
                print(f"✅ Column '{col_name}' already exists.")
            except Exception:
                print(f"✨ Adding column '{col_name}'...")
                conn.execute(text(f"ALTER TABLE financialfundamentals ADD COLUMN {col_name} {col_type}"))

        conn.commit()
    
    print("✅ Migration Complete.")

if __name__ == "__main__":
    migrate()
