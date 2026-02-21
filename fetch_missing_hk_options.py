
import sys
import time
import logging
from futu import *
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Watchlist
from backend.option_models import OptionData
from datetime import datetime, timedelta

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FixHKOptions")

def get_missing_hk_stocks():
    with Session(engine) as session:
        # Get all HK stocks from watchlist
        all_hk = session.exec(select(Watchlist).where(Watchlist.symbol.like("HK:STOCK:%"))).all()
        all_symbols = [s.symbol for s in all_hk]
        
        # Get existing option data
        existing = session.exec(select(OptionData.symbol).where(OptionData.market == 'HK').distinct()).all()
        existing_symbols = set(existing)
        
        # Identify missing or potentially incomplete
        # We process ALL to be safe, but highlight missing
        missing = [s for s in all_symbols if s not in existing_symbols]
        
        logger.info(f"📋 Total HK Stocks: {len(all_symbols)}")
        logger.info(f"✅ Existing Options: {len(existing_symbols)}")
        logger.info(f"❌ Missing Options: {len(missing)} -> {missing}")
        
        return all_symbols

def robust_fetch_hk_option(symbol):
    futu_code = f"HK.{symbol.split(':')[-1]}"
    logger.info(f"\nExample: Processing {symbol} ({futu_code})...")
    
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    try:
        # 1. Get Snapshot (Check if valid)
        ret, data = quote_ctx.get_market_snapshot([futu_code])
        if ret != RET_OK:
            logger.error(f"❌ Snapshot Failed for {futu_code}: {data}")
            return False
            
        price = data['last_price'][0]
        logger.info(f"   💰 Price: {price}")
        time.sleep(0.5)
        
        # 2. Get Expirations
        ret, exp_df = quote_ctx.get_option_expiration_date(code=futu_code)
        if ret != RET_OK:
            logger.error(f"❌ Expirations Failed: {exp_df}")
            return False
            
        # Target: 1, 2, 3 months
        today = datetime.now()
        target_dates = []
        for m in [1, 2, 3]:
            target_dt = today + timedelta(days=30*m)
            # Find closest
            valid_dates = pd.to_datetime(exp_df['strike_time']).tolist()
            closest = min(valid_dates, key=lambda d: abs((d - target_dt).days))
            if closest > today:
                target_dates.append(closest.strftime('%Y-%m-%d'))
        
        # Deduplicate
        target_dates = sorted(list(set(target_dates)))
        logger.info(f"   📅 Targets: {target_dates}")
        
        total_saved = 0
        
        # 3. Iterate Dates
        for date in target_dates:
            time.sleep(0.5) # Rate limit
            
            ret, chain = quote_ctx.get_option_chain(code=futu_code, start=date, end=date, option_type=OptionType.PUT)
            if ret != RET_OK:
                logger.warning(f"   ⚠️ Chain Failed for {date}: {chain}")
                continue
                
            if chain.empty:
                logger.warning(f"   ⚠️ No options for {date}")
                continue

            # Filter Near Money (ATM)
            chain['strike'] = chain['strike_price']
            chain['distance'] = abs(chain['strike'] - price)
            near_puts = chain.nsmallest(5, 'distance') # Get top 5 to be safe
            
            # Get Snapshots for Options
            codes = near_puts['code'].tolist()
            time.sleep(0.5) # Rate limit
            
            ret, snaps = quote_ctx.get_market_snapshot(codes)
            if ret != RET_OK:
                logger.warning(f"   ⚠️ Option Snaps Failed: {snaps}")
                continue
                
            # Save to DB
            with Session(engine) as session:
                merged = pd.merge(near_puts, snaps, on='code')
                for _, row in merged.iterrows():
                    # Calculate Exp Days
                    exp_date = datetime.strptime(date, '%Y-%m-%d')
                    days = (exp_date - today).days
                    
                    # Construct Data
                    opt = OptionData(
                        symbol=symbol,
                        market='HK',
                        underlying_price=price,
                        option_symbol=row['code'],
                        option_type='PUT',
                        strike=row['strike'],
                        expiry_date=date,
                        days_to_expiry=days,
                        last_price=row['last_price'],
                        bid=row.get('bid_price', 0),
                        ask=row.get('ask_price', 0),
                        volume=int(row.get('volume', 0)),
                        open_interest=int(row.get('open_interest', 0)),
                        implied_volatility=row.get('option_implied_volatility'),
                        delta=row.get('option_delta'),
                        gamma=row.get('option_gamma'),
                        vega=row.get('option_vega'),
                        theta=row.get('option_theta'),
                        rho=row.get('option_rho'),
                        moneyness=(row['strike'] - price)/price,
                        currency='HKD',
                        data_source='futu-fix',
                        updated_at=datetime.now()
                    )
                    
                    # Upsert
                    existing = session.exec(select(OptionData).where(
                        OptionData.symbol==opt.symbol, 
                        OptionData.option_symbol==opt.option_symbol
                    )).first()
                    
                    if existing:
                        for k, v in opt.model_dump(exclude={'id','created_at'}).items():
                            setattr(existing, k, v)
                    else:
                        session.add(opt)
                    
                    total_saved += 1
                session.commit()
                
        logger.info(f"   ✅ Saved {total_saved} options for {symbol}")
        return True

    except Exception as e:
        logger.error(f"❌ Exception for {symbol}: {e}")
        return False
    finally:
        quote_ctx.close()

def main():
    targets = get_missing_hk_stocks()
    
    print(f"\n🚀 Starting Robust HK Option Fetch for {len(targets)} stocks...")
    
    for i, symbol in enumerate(targets):
        print(f"\n[{i+1}/{len(targets)}] Processing {symbol}...")
        robust_fetch_hk_option(symbol)
        time.sleep(2) # Inte-stock delay
        
    print("\n✅ All Done!")

if __name__ == "__main__":
    main()
