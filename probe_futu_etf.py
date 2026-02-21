
import os
import sys
from futu import *

def probe_futu_etf_valuation(symbol='HK.02800'):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    print(f"\n--- Probing Snapshot for {symbol} ---")
    ret, data = quote_ctx.get_market_snapshot([symbol])
    if ret == RET_OK:
        print(f"Columns available: {data.columns.tolist()}")
        # Print all columns that have non-NaN values
        non_nan = data.dropna(axis=1)
        print(f"Non-NaN columns: {non_nan.columns.tolist()}")
        
        # Check specific PE/Yield fields
        for col in data.columns:
            if 'pe' in col.lower() or 'ratio' in col.lower() or 'yield' in col.lower() or 'ttm' in col.lower():
                print(f"  {col}: {data.iloc[0][col]}")
    else:
        print(f"❌ Snapshot Error: {data}")

    quote_ctx.close()

if __name__ == "__main__":
    probe_futu_etf_valuation('HK.02800')
    probe_futu_etf_valuation('HK.00700')
