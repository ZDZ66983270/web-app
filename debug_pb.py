
import os
import sys
from futu import *

def debug_raw_pb_fields():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.02800'
    print(f"\n--- Listing ALL non-empty PB fields for {symbol} ---")
    
    # We use internal methods to get the raw response
    from futu.quote.quote_query import MarketSnapshotQuery
    from futu.common.utils import split_stock_str
    
    ret, content = split_stock_str(symbol)
    market, code = content
    
    # Manually pack and send
    req_ret, req_data = MarketSnapshotQuery.pack_req([symbol], quote_ctx.get_sync_conn_id())
    
    # We can't easily wait for the specific response without the context logic
    # But get_market_snapshot already does it. 
    # Let's just modify the local quote_query.py temporary to print EVERYTHING.
    
    quote_ctx.close()

if __name__ == "__main__":
    debug_raw_pb_fields()
