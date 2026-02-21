import yfinance as yf

def check_hk_options():
    symbols = ['0700.HK', '9988.HK', '0005.HK']
    print("Checking HK Options availability via yfinance...")
    
    for sym in symbols:
        print(f"\nChecking {sym}...")
        t = yf.Ticker(sym)
        try:
            opts = t.options
            print(f"Options Date: {opts}")
            if opts:
                 chain = t.option_chain(opts[0])
                 print(f"Sample Call: {chain.calls.head(1)}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_hk_options()
