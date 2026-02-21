
import os
import sys
from futu import *

def test_stock_filter_advanced():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Try to filter for specific ETF and get its fields
    # Note: Stock filter is for screening, but we can use it to fetch data for filtered stocks
    
    # SimpleFilter for PE_TTM
    # Note: StockField is used in FinancialFilter or as a column in result? 
    # Let's check get_stock_filter signature again.
    
    # Actually, let's try get_market_snapshot again but looking for ANY field that might be PE
    print("\n--- Market Snapshot for HK.02800 ---")
    ret, data = quote_ctx.get_market_snapshot(['HK.02800', 'HK.00700'])
    if ret == RET_OK:
        for idx, row in data.iterrows():
            print(f"\nStock: {row['code']} ({row['name']})")
            for col in data.columns:
                if 'pe' in col.lower() or 'ratio' in col.lower() or 'yield' in col.lower():
                    print(f"  {col}: {row[col]}")
    
    quote_ctx.close()

if __name__ == "__main__":
    test_stock_filter_advanced()
