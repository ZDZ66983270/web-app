import subprocess
import sys
import os

def run_fetch(market=None, symbol=None, max_retries=3):
    cmd = ["python3", "fetch_financials.py"]
    if market:
        cmd.extend(["--market", market])
    if symbol:
        cmd.extend(["--symbol", symbol])
    
    for i in range(max_retries):
        print(f"\n>>>> Attempt {i+1} for {symbol or market} <<<<")
        try:
            # We use check_call to detect failure, but fetch_financials.py 
            # might catch exceptions and exit with 0. 
            # So we check the actual output/state if possible, 
            # but for now we rely on the process exit code.
            subprocess.check_call(cmd)
            print(f"✅ Successfully completed {symbol or market}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Attempt {i+1} failed: {e}")
            if i == max_retries - 1:
                print(f"🛑 Max retries reached for {symbol or market}. Aborting.")
                return False
    return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', type=str)
    parser.add_argument('--symbol', type=str)
    args = parser.parse_args()
    
    run_fetch(market=args.market, symbol=args.symbol)
