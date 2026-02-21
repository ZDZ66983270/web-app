
import os
import sys
from futu import *

def test_history_pe_comparison():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Test symbols: Stock vs ETF
    symbols = ['HK.00700', 'HK.02800', 'HK.03110']
    
    for symbol in symbols:
        print(f"\n--- History K-Line for {symbol} ---")
        ret, data, next_key = quote_ctx.request_history_kline(
            code=symbol,
            start='2024-01-01',
            end='2024-01-31',
            ktype=KLType.K_DAY,
            fields=[KL_FIELD.DATE_TIME, KL_FIELD.CLOSE, KL_FIELD.PE_RATIO]
        )
        if ret == RET_OK:
            print(f"Data for {symbol}:")
            print(data.head())
        else:
            print(f"Error for {symbol}: {data}")
            
    quote_ctx.close()

if __name__ == "__main__":
    test_history_pe_comparison()
