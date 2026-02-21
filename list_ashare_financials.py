import sqlite3
import pandas as pd
import sys

def list_ashare_financials():
    conn = sqlite3.connect('backend/database.db')
    
    query = """
    SELECT 
        w.name, 
        w.symbol, 
        f.as_of_date, 
        f.revenue_ttm, 
        f.net_income_ttm, 
        f.shares_outstanding_common_end,
        f.data_source
    FROM watchlist w
    JOIN financialfundamentals f ON w.symbol = f.symbol
    WHERE w.market = 'CN' 
    AND w.symbol LIKE 'CN:STOCK:%'
    AND f.as_of_date = (
        SELECT MAX(f2.as_of_date)
        FROM financialfundamentals f2
        WHERE f2.symbol = f.symbol
    )
    ORDER BY w.symbol;
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        
        # Calculate derived EPS if missing and shares are available
        def calculate_eps(row):
            if pd.notnull(row['net_income_ttm']) and pd.notnull(row['shares_outstanding_common_end']) and row['shares_outstanding_common_end'] > 0:
                return row['net_income_ttm'] / row['shares_outstanding_common_end']
            return None

        df['Derived EPS'] = df.apply(calculate_eps, axis=1)
        
        # Format columns
        # Revenue/NetIncome in Billions (亿)
        df['Revenue (亿)'] = df['revenue_ttm'].apply(lambda x: f"{x/1e8:.2f}" if pd.notnull(x) else "-")
        df['Net Income (亿)'] = df['net_income_ttm'].apply(lambda x: f"{x/1e8:.2f}" if pd.notnull(x) else "-")
        df['EPS'] = df['Derived EPS'].apply(lambda x: f"{x:.4f}" if pd.notnull(x) else "-")
        
        # Select display columns
        display_df = df[['name', 'symbol', 'as_of_date', 'Revenue (亿)', 'Net Income (亿)', 'EPS', 'data_source']]
        display_df.columns = ['公司', '代码', '最新报告期', '收入(亿)', '利润(亿)', 'EPS', '来源']
        
        print(display_df.to_string(index=False))
        
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_ashare_financials()
