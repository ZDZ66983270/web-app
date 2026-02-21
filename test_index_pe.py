
import os
import sys
import time
from futu import *

def test_index_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    symbol = 'HK.800000' # HSI
    
    print(f"🔗 Subscribing to {symbol}...")
    ret, data = quote_ctx.subscribe([symbol], [SubType.QUOTE], subscribe_push=False)
    if ret == RET_OK:
        print("✅ Subscription Successful!")
        
        print("\n📥 Requesting Snapshot...")
        ret_s, data_s = quote_ctx.get_market_snapshot([symbol])
        if ret_s == RET_OK:
            # Check for non-NaN values
            row = data_s.iloc[0]
            for col in data_s.columns:
                val = row[col]
                if pd.notna(val) and val != 0 and val != '' and val != False:
                    print(f"  {col}: {val}")
        else:
            print(f"Error Snapshot: {data_s}")
            
        print("\n📥 Requesting History K-Line...")
        ret_h, data_h, next_key = quote_ctx.request_history_kline(symbol, start='2024-01-01', end='2024-02-01', ktype=KLType.K_DAY)
        if ret_h == RET_OK:
            print(data_h.head())
        else:
            print(f"Error History: {data_h}")
    else:
        print(f"❌ Subscription Failed: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    test_index_pe()
