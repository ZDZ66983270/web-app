import sqlite3
import os

DB_PATH = "backend/database.db"

def migrate_db():
    print(f"Checking database at {DB_PATH}...")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Migrate MarketDataDaily
    try:
        print("Migrating MarketDataDaily...")
        cursor.execute("PRAGMA table_info(MarketDataDaily)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'pe_ttm' not in columns:
            cursor.execute("ALTER TABLE MarketDataDaily ADD COLUMN pe_ttm FLOAT")
            print("✅ Added pe_ttm to MarketDataDaily")
        else:
            print("ℹ️  pe_ttm already exists in MarketDataDaily")
            
    except Exception as e:
        print(f"❌ Error migrating MarketDataDaily: {e}")

    # 2. Migrate MarketSnapshot
    try:
        print("Migrating MarketSnapshot...")
        cursor.execute("PRAGMA table_info(MarketSnapshot)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'pe_ttm' not in columns:
            cursor.execute("ALTER TABLE MarketSnapshot ADD COLUMN pe_ttm FLOAT")
            print("✅ Added pe_ttm to MarketSnapshot")
        else:
            print("ℹ️  pe_ttm already exists in MarketSnapshot")
            
    except Exception as e:
        print(f"❌ Error migrating MarketSnapshot: {e}")

    conn.commit()
    conn.close()
    print("All done.")

if __name__ == "__main__":
    migrate_db()
