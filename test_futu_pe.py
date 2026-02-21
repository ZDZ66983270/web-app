
import sys
import pandas as pd
from futu import *

def test_futu_connection():
    try:
        print("🔗 Connecting to Futu OpenD (127.0.0.1:11111)...")
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        print("✅ Connection Successful!")
        
        symbol = 'HK.02800'
        print(f"📥 Requesting History Kline for {symbol}...")
        
        # Request Daily K-line (No fields arg, it returns fixed columns)
        ret, data, page_req_key = quote_ctx.request_history_kline(
            code=symbol,
            start='2016-01-13',
            end='2026-01-13',
            ktype=KLType.K_DAY,
            autype=AuType.QFQ,
            max_count=3000
        )
        
        if ret == RET_OK:
            print(f"✅ Data Received: {len(data)} rows")
            print("Columns:", data.columns.tolist())
            
            if 'pe_ratio' in data.columns:
                print("\nPreview (First 5 rows):")
                print(data[['time_key', 'close', 'pe_ratio']].head())
                
                print("\nPreview (Last 5 rows):")
                print(data[['time_key', 'close', 'pe_ratio']].tail())

                # Latest PE
                latest = data.iloc[-1]
                print(f"\n🔥 LATEST DATA ({latest['time_key']}):")
                print(f"   Close: {latest['close']}")
                print(f"   PE Ratio: {latest['pe_ratio']}")
                
                zeros = (data['pe_ratio'] == 0).sum()
                print(f"\n⚠️ Zero PE Ratios: {zeros}")
            else:
                print("❌ 'pe_ratio' column NOT found in response.")
            
            # --- Test Snapshot ---
            print(f"\n📸 Requesting Snapshot for {symbol}...")
            ret_s, data_s = quote_ctx.get_market_snapshot([symbol])
            if ret_s == RET_OK:
                print("✅ Snapshot Received!")
                cols = ['code', 'update_time', 'last_price', 'pe_ratio', 'pe_ttm_ratio']
                available = [c for c in cols if c in data_s.columns]
                print(data_s[available].iloc[0])
            else:
                print(f"❌ Snapshot Error: {data_s}")
            
        else:
            print(f"❌ Error: {data}")
            
        quote_ctx.close()
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_futu_connection()
