
import os
import sys
from futu import *

def probe_multiple_etfs():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    etfs = ['HK.02800', 'HK.02828', 'HK.03033', 'HK.03110', 'HK.00700']
    
    print(f"\n--- Probing Snapshots ---")
    ret, data = quote_ctx.get_market_snapshot(etfs)
    if ret == RET_OK:
        cols = ['code', 'name', 'pe_ratio', 'pe_ttm_ratio', 'dividend_ratio_ttm', 'trust_dividend_yield']
        existing = [c for c in cols if c in data.columns]
        print(data[existing])
        
        # Check if any ETF has non-NaN pe_ratio
        for _, row in data.iterrows():
            if pd.notna(row['pe_ratio']) and row['pe_ratio'] != 0:
                print(f"🔥 FOUND PE for {row['code']} ({row['name']}): {row['pe_ratio']}")
    else:
        print(f"Error: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    probe_multiple_etfs()
