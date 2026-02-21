
from sqlmodel import Session, select
from backend.database import engine
from backend.models import MarketDataDaily, Watchlist
import pandas as pd
from datetime import datetime

def check_latest_valuations():
    with Session(engine) as session:
        # Get all watchlist items and filter for STOCKs
        all_items = session.exec(select(Watchlist)).all()
        watchlist = [item for item in all_items if ':STOCK:' in item.symbol]
        symbols = [w.symbol for w in watchlist]
        
        results = []
        for symbol in symbols:
            stmt = select(MarketDataDaily).where(MarketDataDaily.symbol == symbol).order_by(MarketDataDaily.timestamp.desc()).limit(1)
            record = session.exec(stmt).first()
            
            if record:
                results.append({
                    'symbol': symbol,
                    'date': record.timestamp,
                    'pe_ttm': record.pe_ttm,
                    'pb': record.pb,
                    'ps': record.ps,
                    'is_complete': all([record.pe_ttm, record.pb, record.ps])
                })
        
        df = pd.DataFrame(results)
        if df.empty:
            print("No stock data found.")
            return
            
        print("\n📊 Valuation Health Check (Individual Stocks Only):")
        
        # Split into Complete and Incomplete
        complete = df[df['is_complete'] == True]
        incomplete = df[df['is_complete'] == False]
        
        if not incomplete.empty:
            print(f"\n⚠️  Missing Data detected for {len(incomplete)} stocks:")
            print(incomplete[['symbol', 'date', 'pe_ttm', 'pb', 'ps']].to_string(index=False))
        else:
            print("\n✅ All stocks have complete PE/PB/PS data.")
            
        print(f"\n📈 Summary Stats:")
        print(f"Total Stocks: {len(symbols)}")
        print(f"Complete: {len(complete)}")
        print(f"Missing PE_TTM: {df['pe_ttm'].isna().sum()}")
        print(f"Missing PB: {df['pb'].isna().sum()}")
        print(f"Missing PS: {df['ps'].isna().sum()}")

if __name__ == "__main__":
    check_latest_valuations()
