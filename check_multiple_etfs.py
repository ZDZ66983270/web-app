
import os
import sys
from futu import *

def check_multiple_etf_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # 盈富基金, 恒生中国企业, 南方恒生科技, GlobalX恒生高股息, 南方A50
    etfs = ['HK.02800', 'HK.02828', 'HK.03033', 'HK.03110', 'HK.02822']
    
    print("\n--- Checking History K-line PE for multiple ETFs ---")
    for symbol in etfs:
        ret, data, nk = quote_ctx.request_history_kline(symbol, start='2024-01-01', end='2024-01-31', ktype=KLType.K_DAY)
        if ret == RET_OK:
            pe_values = data['pe_ratio'].unique().tolist()
            print(f"{symbol}: Unique PE values = {pe_values}")
        else:
            print(f"{symbol}: Error {data}")
            
    quote_ctx.close()

if __name__ == "__main__":
    check_multiple_etf_pe()
