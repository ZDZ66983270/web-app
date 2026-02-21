
import sqlite3

def fix_history():
    db_path = 'backend/database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Correct shares for HK stocks (Approximate latest)
    shares_map = {
        'HK:STOCK:00700': 9270000000.0,
        'HK:STOCK:03968': 25220000000.0,
        'HK:STOCK:00005': 18500000000.0,
        'HK:STOCK:09988': 18600000000.0,
        'HK:STOCK:03690': 6220000000.0,
        'HK:STOCK:01919': 15900000000.0,
        'HK:STOCK:06099': 4827000000.0,
        'HK:STOCK:00998': 48935000000.0
    }
    
    print("🛠️ Fixing HK shares history...")
    for symbol, shares in shares_map.items():
        cursor.execute("UPDATE financialfundamentals SET shares_outstanding_common_end = ? WHERE symbol = ?", (shares, symbol))
        print(f"  ✅ Updated {symbol} to {shares:.0f} shares")
    
    # Fix Assets/Liabilities for 00700 if Equity is missing (Fallback for BPS)
    # Based on Q3 2024: Assets ~1,650B, Liabilities ~820B
    cursor.execute("UPDATE financialfundamentals SET total_assets = 1650000000000.0, total_liabilities = 820000000000.0 WHERE symbol = 'HK:STOCK:00700' AND total_assets IS NULL")
    
    conn.commit()
    conn.close()
    print("✨ Finished fixing history.")

if __name__ == "__main__":
    fix_history()
