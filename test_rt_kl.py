
import os
import sys
import time
from futu import *

def test_rt_kl_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.02800'
    print(f"\n--- Checking RT K-line PE for {symbol} ---")
    
    # Subscribing to K_DAY
    ret, data = quote_ctx.subscribe([symbol], [SubType.K_DAY], subscribe_push=False)
    if ret == RET_OK:
        ret, data = quote_ctx.get_rt_kline(symbol, 5, KLType.K_DAY)
        if ret == RET_OK:
            print(data[['time_key', 'pe_ratio']])
        else:
            print(f"Error get_rt_kline: {data}")
    else:
        print(f"Error subscribe: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    test_rt_kl_pe()
