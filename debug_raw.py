
import os
import sys
from futu import *

def debug_raw_snapshot():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.02800'
    print(f"\n--- Debugging Raw Snapshot for {symbol} ---")
    
    # We need to reach into the internal unpacker to see the raw record
    # Actually, I already added a print in quote_query.py but let's do it manually here
    
    ret, data = quote_ctx.get_market_snapshot([symbol])
    # The print in quote_query.py should trigger. 
    # But I want to check more fields.
    
    quote_ctx.close()

if __name__ == "__main__":
    debug_raw_snapshot()
