
import os
import sys
import time
from futu import *

def test_etf_pe_cur_kline():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.02800'
    
    print(f"🔗 Subscribing to {symbol}...")
    ret, data = quote_ctx.subscribe([symbol], [SubType.QUOTE, SubType.K_DAY], subscribe_push=False)
    if ret == RET_OK:
        print("✅ Subscription Successful!")
        
        print("\n📥 Requesting get_cur_kline...")
        ret_k, data_k = quote_ctx.get_cur_kline(symbol, num=5, ktype=KLType.K_DAY)
        if ret_k == RET_OK:
            print(data_k)
        else:
            print(f"Error kline: {data_k}")
            
    quote_ctx.close()

if __name__ == "__main__":
    test_etf_pe_cur_kline()
