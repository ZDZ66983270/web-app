
import yfinance as yf
from sqlmodel import Session, select, text
from backend.models import Watchlist, MarketDataDaily
from backend.database import engine
import pandas as pd
from datetime import datetime

# Database connection is now imported from backend.database
# Disable SQL logging for cleaner output
engine.echo = False

def get_yahoo_symbol(canonical_id):
    parts = canonical_id.split(':')
    if len(parts) < 3:
        return canonical_id
    market, type_, symbol = parts[0], parts[1], parts[2]
    
    if market == 'US':
        return symbol
    elif market == 'HK':
        return f"{int(symbol):04d}.HK"
    elif market == 'CN':
        if symbol.startswith('6'):
            return f"{symbol}.SS"
        else:
            return f"{symbol}.SZ"
    return symbol

def verify_pe():
    results = []
    print(f"🔍 正在对比数据库 PE 与 Yahoo Finance 实时数据...")
    
    with Session(engine) as session:
        # Get all stocks from watchlist based on symbol string pattern
        stocks = session.exec(select(Watchlist).where(Watchlist.symbol.like('%:STOCK:%'))).all()
        
        for i, stock in enumerate(stocks):
            print(f"[{i+1}/{len(stocks)}] Checking {stock.symbol}...", end='\r')
            yahoo_ticker = get_yahoo_symbol(stock.symbol)
            
            # 1. Get DB PE
            # 1. Get DB PE (Prioritize TTM)
            latest_data = session.exec(
                select(MarketDataDaily)
                .where(MarketDataDaily.symbol == stock.symbol)
                .order_by(MarketDataDaily.timestamp.desc())
                .limit(1)
            ).first()
            
            db_pe = None
            pe_type = "N/A"
            
            if latest_data:
                # Prioritize TTM for fair comparison with Yahoo Trailing PE
                if latest_data.pe_ttm:
                    db_pe = float(latest_data.pe_ttm)
                    pe_type = "TTM"
                elif latest_data.pe:
                    db_pe = float(latest_data.pe)
                    pe_type = "Static"
                
                ts = latest_data.timestamp
                if hasattr(ts, 'strftime'):
                    db_date = ts.strftime('%Y-%m-%d')
                else:
                    db_date = str(ts)[:10]
            else:
                db_date = "N/A"
            
            # 2. Get Yahoo PE
            try:
                ticker = yf.Ticker(yahoo_ticker)
                full_info = ticker.info
                yahoo_pe = full_info.get('trailingPE')
                if yahoo_pe is None and 'trailingPE' not in full_info:
                     yahoo_pe = None 
            except Exception as e:
                yahoo_pe = None

            # 3. Compare
            diff_val = 0
            diff_str = "N/A"
            if db_pe is not None and yahoo_pe is not None and yahoo_pe != 0:
                diff_val = (db_pe - yahoo_pe) / yahoo_pe * 100
                diff_str = f"{diff_val:+.1f}%"
            
            results.append({
                'symbol': stock.symbol,
                'market': stock.market,
                'db_date': db_date,
                'db_pe': db_pe,
                'yahoo_pe': yahoo_pe,
                'diff_pct': diff_val if diff_str != "N/A" else None,
                'diff_str': diff_str
            })

    # Output
    print("\n" + "="*90)
    print(f"{'Symbol':<18} {'Mkt':<4} {'Date':<10} {'DB PE':>8} {'Yahoo PE':>10} {'Diff %':>8}")
    print(f"{'-'*18} {'-'*4} {'-'*10} {'-'*8} {'-'*10} {'-'*8}")
    
    for r in results:
        db_s = f"{r['db_pe']:.2f}" if r['db_pe'] is not None else "N/A"
        ya_s = f"{r['yahoo_pe']:.2f}" if r['yahoo_pe'] is not None else "N/A"
        print(f"{r['symbol']:<18} {r['market']:<4} {r['db_date']:<10} {db_s:>8} {ya_s:>10} {r['diff_str']:>8}")

    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv('pe_comparison.csv', index=False)
    print(f"\n✅ 对比完成，结果已保存至 pe_comparison.csv")

if __name__ == "__main__":
    verify_pe()
