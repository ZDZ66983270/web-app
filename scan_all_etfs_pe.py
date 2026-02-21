
import os
import sys
from futu import *

def scan_top_etf_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Get all ETFs
    ret, data = quote_ctx.get_stock_basicinfo(Market.HK, stock_type=SecurityType.ETF)
    if ret != RET_OK:
        print(f"Error fetching ETF list: {data}")
        quote_ctx.close()
        return
        
    all_codes = data['code'].tolist()
    print(f"Scanning {len(all_codes)} ETFs for PE data...")
    
    found_any = False
    # Batch snapshots (max 200 per call)
    for i in range(0, len(all_codes), 200):
        batch = all_codes[i:i+200]
        ret_s, data_s = quote_ctx.get_market_snapshot(batch)
        if ret_s == RET_OK:
            # Check for non-NaN in pe_ratio or pe_ttm_ratio
            with_pe = data_s[(data_s['pe_ratio'] > 0) | (data_s['pe_ttm_ratio'] > 0)]
            if not with_pe.empty:
                print(f"🔥 Found {len(with_pe)} ETFs with PE in batch {i//200}:")
                print(with_pe[['code', 'pe_ratio', 'pe_ttm_ratio']])
                found_any = True
        else:
            print(f"Error in batch {i//200}: {data_s}")
            
    if not found_any:
        print("No ETFs in the entire HK market returned PE in snapshot.")
        
    quote_ctx.close()

if __name__ == "__main__":
    scan_top_etf_pe()
