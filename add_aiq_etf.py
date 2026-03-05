import sys
import os
import pandas as pd
from datetime import datetime

# Add dummy sys.path for backend
sys.path.append('backend')
from data_fetcher_base import DataFetcher
from database import engine
from sqlmodel import Session, select
from models import Watchlist, MarketDataDaily, MarketSnapshot
from utils.symbol_utils import normalize_symbol_db

def register_asset(symbol, name, market):
    print(f"Registering {symbol}...")
    with Session(engine) as session:
        existing = session.exec(select(Watchlist).where(Watchlist.symbol == symbol)).first()
        if not existing:
            session.add(Watchlist(symbol=symbol, name=name, market=market))
            session.commit()
            print(f"✅ Registered {symbol}")
        else:
            print(f"ℹ️ {symbol} already exists")

def save_raw_data_to_db(df: pd.DataFrame, symbol: str, market: str) -> int:
    if df is None or df.empty:
        return 0
    
    count = 0
    db_symbol = normalize_symbol_db(symbol, market)
    
    with Session(engine) as session:
        existing_days = set(session.exec(
            select(MarketDataDaily.timestamp).where(
                MarketDataDaily.symbol == db_symbol,
                MarketDataDaily.market == market
            )
        ).all())

        for _, row in df.iterrows():
            close_val = float(row.get('收盘', row.get('close', row.get('Close', 0))))
            if pd.isna(close_val): close_val = 0.0

            def get_val(keys, default=0.0):
                for k in keys:
                    if k in row and not pd.isna(row.get(k)):
                        return float(row.get(k))
                return default

            open_val = get_val(['开盘', 'open', 'Open'], default=close_val)
            high_val = get_val(['最高', 'high', 'High'], default=close_val)
            low_val = get_val(['最低', 'low', 'Low'], default=close_val)

            try:
                date_value = str(row.get('时间', row.get('date', row.get('Date', ''))))
                if not date_value or date_value in existing_days:
                    continue
                
                record = MarketDataDaily(
                    symbol=db_symbol,
                    market=market,
                    timestamp=date_value,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=int(row.get('成交量', row.get('volume', row.get('Volume', 0)))),
                    turnover=float(row.get('成交额', row.get('turnover', 0))) if row.get('成交额', row.get('turnover')) else 0,
                    updated_at=datetime.now()
                )
                
                session.add(record)
                count += 1
            except Exception: continue
        
        if count > 0:
            session.commit()
    return count

def run_targeted_etl(symbol, market):
    print(f"🔄 Targeted ETL for {symbol} ({market})...")
    with Session(engine) as session:
        latest = session.exec(
            select(MarketDataDaily)
            .where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == market)
            .order_by(MarketDataDaily.timestamp.desc())
        ).first()
        
        if not latest:
            print("❌ No data for ETL")
            return
            
        prev_day = session.exec(
            select(MarketDataDaily)
            .where(MarketDataDaily.symbol == symbol, MarketDataDaily.market == market, MarketDataDaily.timestamp < latest.timestamp)
            .order_by(MarketDataDaily.timestamp.desc())
        ).first()

        change = latest.close - prev_day.close if prev_day else 0
        pct_change = (change / (prev_day.close or 1)) * 100 if prev_day else 0

        existing = session.exec(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol, MarketSnapshot.market == market)
        ).first()
        
        if existing:
            existing.price = latest.close
            existing.change = change
            existing.pct_change = pct_change
            existing.timestamp = latest.timestamp
            existing.updated_at = datetime.now()
            session.add(existing)
        else:
            snapshot = MarketSnapshot(
                symbol=symbol, market=market, price=latest.close,
                change=change, pct_change=pct_change, 
                timestamp=latest.timestamp, data_source='etl',
                fetch_time=datetime.now(), updated_at=datetime.now()
            )
            session.add(snapshot)
        
        session.commit()
        print(f"✅ Snapshot updated for {symbol}")

def main():
    SYMBOL = 'US:ETF:AIQ'
    YF_TICKER = 'AIQ'
    MARKET = 'US'
    NAME = 'Global X Artificial Intelligence ETF'
    
    register_asset(SYMBOL, NAME, MARKET)
    
    fetcher = DataFetcher()
    print(f"Syncing market data for {SYMBOL}...")
    df = fetcher.fetch_us_daily_data(YF_TICKER, period='10y')
    
    if df is not None and not df.empty:
        saved = save_raw_data_to_db(df, SYMBOL, MARKET)
        print(f"✅ Saved {saved} records for {SYMBOL}")
        run_targeted_etl(SYMBOL, MARKET)
    else:
        print(f"❌ Failed to fetch market data for {SYMBOL}")

if __name__ == "__main__":
    main()
