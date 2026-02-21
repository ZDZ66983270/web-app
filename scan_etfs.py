
import os
import sys
from futu import *

def scan_etfs():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # List of some common HK ETFs
    etfs = [
        'HK.02800', 'HK.02828', 'HK.03033', 'HK.03110', 'HK.03067', 
        'HK.02840', 'HK.03032', 'HK.03188', 'HK.02822', 'HK.03140'
    ]
    
    print("\n--- Scanning ETFs for PE Data ---")
    ret, data = quote_ctx.get_market_snapshot(etfs)
    if ret == RET_OK:
        # Check all columns for anything PE-related
        pe_cols = [c for c in data.columns if 'pe' in c.lower()]
        print(f"PE Columns found: {pe_cols}")
        
        for _, row in data.iterrows():
            print(f"{row['code']} ({row['name']})")
            for col in pe_cols:
                print(f"  {col}: {row[col]}")
            if 'trust_dividend_yield' in row:
                print(f"  trust_dividend_yield: {row['trust_dividend_yield']}")
    else:
        print(f"Error: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    scan_etfs()
