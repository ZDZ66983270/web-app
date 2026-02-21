
from futu import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugHK")

def debug_stock(stock_code):
    print(f"\n🔍 Debugging {stock_code}...")
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    try:
        # 1. Snapshot
        ret, data = quote_ctx.get_market_snapshot([stock_code])
        if ret == RET_OK:
            print(f"✅ Snapshot OK: Name={data['name'][0]}, Price={data['last_price'][0]}")
        else:
            print(f"❌ Snapshot Failed: {data}")
            return

        # 2. Option Expirations
        ret, exp_df = quote_ctx.get_option_expiration_date(code=stock_code)
        if ret == RET_OK:
            print(f"✅ Expirations Found: {len(exp_df)} dates")
            print(f"   First 3: {exp_df['strike_time'].tolist()[:3]}")
            
            if not exp_df.empty:
                first_date = exp_df['strike_time'].iloc[0]
                print(f"\n🔍 Fetching Option Chain for {first_date}...")
                
                # 3. Option Chain
                ret, chain_df = quote_ctx.get_option_chain(
                    code=stock_code, 
                    start=first_date, 
                    end=first_date, 
                    option_type=OptionType.PUT
                )
                
                if ret == RET_OK:
                    print(f"✅ Option Chain Found: {len(chain_df)} contracts")
                    if not chain_df.empty:
                        print(f"   Sample: {chain_df[['code', 'name', 'strike_price']].head(2)}")
                else:
                    print(f"❌ Option Chain Failed: {chain_df}")
        else:
            print(f"❌ Expiration Failed: {exp_df}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    finally:
        quote_ctx.close()

if __name__ == "__main__":
    debug_stock('HK.03690') # Meituan
    debug_stock('HK.09988') # Alibaba
