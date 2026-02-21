import sqlite3
import pandas as pd
import sys

symbol = sys.argv[1] if len(sys.argv) > 1 else 'CN:STOCK:600309'

try:
    conn = sqlite3.connect('backend/database.db')
    query = f"""
    SELECT as_of_date, revenue_ttm, net_income_ttm, total_assets, shares_outstanding_common_end, data_source
    FROM financialfundamentals
    WHERE symbol = '{symbol}'
    ORDER BY as_of_date DESC
    LIMIT 5
    """
    df = pd.read_sql_query(query, conn)
    print(f"Latest Financials for {symbol}:")
    print(df.to_string())
    conn.close()
except Exception as e:
    print(e)
