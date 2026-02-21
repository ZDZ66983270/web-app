
import os
import sys
from futu import *

def probe_owner_plate():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.02800'
    print(f"\n--- Owner Plates for {symbol} ---")
    ret, data = quote_ctx.get_owner_plate([symbol])
    if ret == RET_OK:
        print(data)
        # If there are plates, get snapshot for them
        for plate_code in data['plate_code'].tolist():
            print(f"\n--- Snapshot for Plate {plate_code} ---")
            ret_s, data_s = quote_ctx.get_market_snapshot([plate_code])
            if ret_s == RET_OK:
                cols = ['code', 'name', 'pe_ratio', 'pe_ttm_ratio']
                existing = [c for c in cols if c in data_s.columns]
                print(data_s[existing].iloc[0].to_dict())
    else:
        print(f"Error: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    probe_owner_plate()
