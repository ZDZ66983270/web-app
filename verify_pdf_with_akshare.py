import akshare as ak
import pandas as pd
import sqlite3
import sys
import time
from datetime import datetime

# Common headers
print("🔍 Starting A-Share PDF Data Verification using AkShare...")

# 1. Get Latest PDF Data from DB
conn = sqlite3.connect('backend/database.db')
query = """
SELECT 
    symbol, 
    as_of_date, 
    revenue_ttm, 
    net_income_ttm, 
    total_assets 
FROM financialfundamentals 
WHERE data_source = 'pdf-parser' 
AND symbol LIKE 'CN:STOCK:%'
ORDER BY symbol
"""
df_db = pd.read_sql_query(query, conn)
conn.close()

if df_db.empty:
    print("⚠️ No PDF data found in database to verify.")
    sys.exit(0)

print(f"📋 Found {len(df_db)} PDF records in DB to verify.")

# Group by symbol to efficient processing
grouped = df_db.groupby('symbol')

def get_akshare_data(symbol_code):
    try:
        # symbol_code e.g. "600536"
        df = ak.stock_financial_abstract(symbol=symbol_code)
        if df is None or df.empty: return None
        return df
    except Exception as e:
        print(f"   ❌ AkShare error for {symbol_code}: {e}")
        return None

results = []

for symbol, group in grouped:
    code = symbol.split(':')[-1]
    print(f"\n🔍 Verifying {symbol} ({len(group)} records)...")
    
    # Fetch AkShare Data ONCE per stock
    ak_df = get_akshare_data(code)
    if ak_df is None:
        print(f"   ⚠️ AkShare returned no data for {code}")
        continue
        
    # AkShare columns are dates like '20250930'
    # We loop through DB records for this stock
    for idx, row in group.iterrows():
        db_date_str = row['as_of_date'] # YYYY-MM-DD
        ak_date_key = db_date_str.replace('-', '') # YYYYMMDD
        
        # Check if date exists in AkShare columns
        if ak_date_key not in ak_df.columns:
            print(f"   ⚠️ Date {db_date_str} not found in AkShare")
            continue
            
        # Helper to get value
        def get_val(indicator):
            # AkShare Abstract indicators
            # 营业总收入, 归母净利润, 股东权益合计(净资产) -> Need to deriving Total Assets?
            # Abstract has '资产负债率', '股东权益合计(净资产)'.
            # Assets = Equity / (1 - DebtRatio)
            r = ak_df[ak_df['指标'] == indicator]
            if r.empty: return None
            try:
                return float(r.iloc[0][ak_date_key])
            except: return None

        ak_revenue = get_val('营业总收入')
        ak_net_income = get_val('归母净利润')
        
        # Total Assets calculation
        ak_equity = get_val('股东权益合计(净资产)')
        ak_debt_ratio = get_val('资产负债率')
        ak_assets = None
        if ak_equity and ak_debt_ratio is not None:
             if ak_debt_ratio < 100:
                 ak_assets = ak_equity / (1 - ak_debt_ratio/100.0)

        # Comparisons
        diffs = []
        
        # Revenue
        db_rev = row['revenue_ttm']
        if db_rev and ak_revenue:
            # Check magnitude (Unit mismatch?)
            # PDF usually full unit. AkShare usually full unit.
            # Calc Check: |DB - AK| / AK
            pct = abs(db_rev - ak_revenue) / (abs(ak_revenue) + 0.1)
            if pct > 0.05: # > 5% diff
                diffs.append(f"Revenue Mismatch: DB={db_rev/1e8:.2f}亿 vs AK={ak_revenue/1e8:.2f}亿 (Diff: {pct*100:.1f}%)")
        
        # Net Income
        db_ni = row['net_income_ttm']
        if db_ni and ak_net_income:
            pct = abs(db_ni - ak_net_income) / (abs(ak_net_income) + 0.1)
            if pct > 0.05:
                diffs.append(f"NetIncome Mismatch: DB={db_ni/1e8:.2f}亿 vs AK={ak_net_income/1e8:.2f}亿 (Diff: {pct*100:.1f}%)")

        # Total Assets
        db_assets = row['total_assets']
        if db_assets and ak_assets:
            pct = abs(db_assets - ak_assets) / (abs(ak_assets) + 0.1)
            if pct > 0.05:
                # Assets might be rough estimate in AkShare abstract
                diffs.append(f"Assets Mismatch: DB={db_assets/1e8:.2f}亿 vs AK(Est)={ak_assets/1e8:.2f}亿 (Diff: {pct*100:.1f}%)")

        if diffs:
            print(f"   ❌ Discrepancy for {db_date_str}:")
            for d in diffs:
                print(f"      - {d}")
                results.append({'symbol': symbol, 'date': db_date_str, 'issue': d})
        else:
            print(f"   ✅ {db_date_str} Verified")

    time.sleep(1) # Gentle rate limit

print("\n" + "="*50)
print("🚩 Verification Summary")
print("="*50)
if not results:
    print("✅ All checked records match AkShare data (within 5% tolerance)!")
else:
    print(f"❌ Found {len(results)} discrepancies:")
    for r in results:
        print(f"[{r['symbol']} @ {r['date']}] {r['issue']}")
