import sys
import os
import argparse
from sqlmodel import Session, select

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine
from backend.models import Watchlist
from backend.fetchers.cn_fetcher import fetch_cn_pdf
from backend.fetchers.hk_fetcher import fetch_hk_pdf

def stage1_download(target_market=None):
    with Session(engine) as session:
        query = select(Watchlist)
        if target_market:
            query = query.where(Watchlist.market == target_market)
        
        stocks = session.exec(query).all()
        # Filter: only CN and HK, and exclude INDEX/CRYPTO (individual stocks only)
        stocks = [s for s in stocks if s.market in ['CN', 'HK'] 
                  and ':INDEX:' not in s.symbol 
                  and ':CRYPTO:' not in s.symbol
                  and ':ETF:' not in s.symbol]
        
        total = len(stocks)
        print(f"🚀 [Stage 1] Starting Download Task for {total} assets (Market: {target_market or 'CN+HK'})")
        
        for idx, stock in enumerate(stocks, 1):
            print(f"\n[{idx}/{total}] Processing {stock.symbol} ({stock.name}) - Market: {stock.market}")
            
            success = False
            for attempt in range(1, 4):
                try:
                    print(f"   >>> Attempt {attempt}...")
                    if stock.market == 'CN':
                        # fetch_cn_pdf also handles HK mirror on CNINFO
                        fetch_cn_pdf(stock.symbol, "data/reports")
                        success = True # If no exception, consider it an attempt made
                    elif stock.market == 'HK':
                        # Step 1: CNINFO Mirror
                        print(f"      [Step 1] CNINFO Mirror...")
                        fetch_cn_pdf(stock.symbol, "data/reports")
                        
                        hk_code = stock.symbol.split(':')[-1]
                        pdf_dir = os.path.join("data/reports", "HK", hk_code)
                        
                        # Step 2: HKEX Backup if needed
                        if not os.path.exists(pdf_dir) or not os.listdir(pdf_dir):
                            print(f"      [Step 2] HKEX Backup (Selenium)...")
                            fetch_hk_pdf(stock.symbol, "data/reports")
                        
                        success = True
                    
                    if success:
                        print(f"   ✅ Finished processing {stock.symbol}")
                        break
                except Exception as e:
                    print(f"   ❌ Attempt {attempt} failed for {stock.symbol}: {e}")
                    if attempt == 3:
                        print(f"   🛑 Giving up on {stock.symbol} after 3 attempts.")

    print("\n✅ Stage 1 Download Task Completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', type=str, choices=['CN', 'HK'], help='Specific market (optional)')
    args = parser.parse_args()
    
    stage1_download(target_market=args.market)
