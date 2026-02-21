
import os
import sys
from futu import *

def probe_futu_more():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbols = ['HK.02800', 'HK.800000', 'HK.00700']
    
    print("\n--- Available Methods in OpenQuoteContext ---")
    methods = [m for m in dir(quote_ctx) if not m.startswith('_')]
    print(", ".join(methods))
    
    for symbol in symbols:
        print(f"\n--- Snapshot for {symbol} ---")
        ret, data = quote_ctx.get_market_snapshot([symbol])
        if ret == RET_OK:
            val_cols = ['pe_ratio', 'pe_ttm_ratio', 'pb_ratio', 'dividend_ratio_ttm', 'trust_dividend_yield', 'total_market_val']
            # Filter columns that exist
            existing = [c for c in val_cols if c in data.columns]
            print(data[existing].iloc[0].to_dict())
        else:
            print(f"Error: {data}")

    print("\n--- History K-Line for HK.800000 ---")
    ret_h, data_h = quote_ctx.get_history_kline('HK.800000', start='2024-01-01', end='2024-01-10', ktype=KType.K_DAY)
    if ret_h == RET_OK:
        print(f"Columns: {data_h.columns.tolist()}")
        if 'pe_ratio' in data_h.columns:
            print(f"PE Ratio Sample: {data_h['pe_ratio'].tolist()[:5]}")
    else:
        print(f"Error: {data_h}")
        
    quote_ctx.close()

if __name__ == "__main__":
    probe_futu_more()
