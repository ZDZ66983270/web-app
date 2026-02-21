import os
import sys
import argparse
from sqlmodel import Session, select

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine
from backend.models import Watchlist
from fetch_financials import process_pdf_directory

def stage2_parse(target_market=None):
    with Session(engine) as session:
        query = select(Watchlist)
        if target_market:
            query = query.where(Watchlist.market == target_market)
        
        stocks = session.exec(query).all()
        # Filter: only CN and HK, and exclude INDEX/CRYPTO/ETF
        stocks = [s for s in stocks if s.market in ['CN', 'HK'] 
                  and ':INDEX:' not in s.symbol 
                  and ':CRYPTO:' not in s.symbol
                  and ':ETF:' not in s.symbol]
        
        total = len(stocks)
        print(f"🚀 [Stage 2.1] Starting Parsing Task for {total} assets (Market: {target_market or 'CN+HK'})")
        
        reports_root = "data/reports"
        
        for idx, stock in enumerate(stocks, 1):
            code = stock.symbol.split(':')[-1]
            market_folder = stock.market
            pdf_dir = os.path.join(reports_root, market_folder, code)
            
            if not os.path.exists(pdf_dir):
                print(f"\n[{idx}/{total}] ⚠️ Directory not found for {stock.symbol}: {pdf_dir}. Skipping.")
                continue
                
            print(f"\n[{idx}/{total}] Parsing {stock.symbol} ({stock.name}) in {pdf_dir}")
            
            success = False
            for attempt in range(1, 4):
                try:
                    if attempt > 1:
                        print(f"   >>> Re-attempting {attempt}...")
                    
                    # process_pdf_directory handles parsing and saving to DB
                    result = process_pdf_directory(session, stock.symbol, pdf_dir)
                    session.commit()
                    success = True
                    print(f"   ✅ Successfully parsed {stock.symbol}")
                    break
                except Exception as e:
                    print(f"   ❌ Attempt {attempt} failed for {stock.symbol}: {e}")
                    session.rollback()
                    if attempt == 3:
                        print(f"   🛑 Giving up on parsing {stock.symbol} after 3 attempts.")

    print("\n✅ Stage 2.1 Parsing Task Completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', type=str, choices=['CN', 'HK'], help='Specific market (optional)')
    args = parser.parse_args()
    
    stage2_parse(target_market=args.market)
