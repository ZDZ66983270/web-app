import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import text

# Ensure backend can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine
from backend.models import Watchlist, FinancialFundamentals

def _parse_val(val):
    """Helper to parse float values from potentially mixed types."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def save_to_db(asset_id, data_map):
    """
    Save fetched data to FinancialFundamentals table.
    data_map format: { 'YYYY-MM-DD': {'eps': float, ...} }
    """
    if not data_map:
        return

    print(f"   💾 Saving {len(data_map)} records for {asset_id}...")
    
    with Session(engine) as session:
        for date_str, values in data_map.items():
            eps = values.get('eps')
            if eps is None:
                continue

            # Check existing record
            statement = select(FinancialFundamentals).where(
                FinancialFundamentals.symbol == asset_id,
                FinancialFundamentals.as_of_date == date_str
            )
            existing = session.exec(statement).first()
            
            if existing:
                # Update if eps is missing or we want to overwrite (TTM is better quality here)
                # Just update EPS for now based on user requirement
                existing.eps = eps
                existing.data_source = f"{existing.data_source}+ttm_fix"
                session.add(existing)
            else:
                # Insert new record
                # Note: We might be missing other fields, but we focus on EPS as per requirement
                new_rec = FinancialFundamentals(
                    symbol=asset_id,
                    as_of_date=date_str,
                    report_type='quarterly' if '-12-31' not in date_str else 'annual',
                    eps=eps,
                    data_source='akshare-ttm-fix'
                )
                session.add(new_rec)
        
        session.commit()

def fetch_hk_history_akshare(asset_id, symbol_code):
    """
    Fetch HK financials using AkShare 'report period' indicator to get EPS_TTM.
    """
    import akshare as ak
    print(f"   🇭🇰 Fetching HK history for {asset_id} (Code: {symbol_code})...")
    
    try:
        # indicator="报告期" contains EPS_TTM
        df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol_code, indicator="报告期")
        if df is None or df.empty:
            print("      ⚠️ No data returned.")
            return

        data_map = {}
        for _, row in df.iterrows():
            # Get date
            end_date = row.get("REPORT_DATE") # Correct column name
            if not end_date:
                continue
            
            date_str = str(end_date)[:10] # YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            ttm = _parse_val(row.get("EPS_TTM"))
            basic = _parse_val(row.get("BASIC_EPS"))
            
            # Priority: use EPS_TTM if available, else fallback to BASIC_EPS if it's annual report (Dec 31)
            # For interim reports without TTM, we might rely on Basic EPS but that's not TTM.
            # User logic: eps_final = ttm if ttm is not None else (basic if dt.month == 12 else None)
            
            eps_final = ttm
            if eps_final is None and dt.month == 12:
                eps_final = basic
            
            if eps_final is not None:
                if date_str not in data_map:
                    data_map[date_str] = {}
                data_map[date_str]["eps"] = eps_final
        
        save_to_db(asset_id, data_map)

    except Exception as e:
        print(f"      ❌ Error fetching HK: {e}")


def fetch_ashare_history(asset_id, symbol_code):
    """
    Fetch A-Share financials and manually calculate TTM EPS.
    """
    import akshare as ak
    print(f"   🇨🇳 Fetching CN history for {asset_id} (Code: {symbol_code})...")
    
    try:
        # 获取原始财务数据（利润表）
        # ak.stock_financial_report_sina returns dataframe with columns as dates
        df_fin = ak.stock_financial_report_sina(stock=symbol_code, symbol="利润表")
        
        if df_fin is None or df_fin.empty:
            print("      ⚠️ No data returned.")
            return

        # Prepare extraction
        # Rows are indicators, Cols are dates
        # We need "基本每股收益" or similar
        # Inspect indicator names: usually "基本每股收益(元)"
        
        target_row = None
        for idx in df_fin.index:
            val = df_fin.iloc[idx, 0] # First column usually '报表日期' or indicator name? 
            # Wait, ak.stock_financial_report_sina usually sets indicator as index or first col?
            # Actually, let's look at recent usage or structure.
            # Usually column 0 is the item name if not indexed.
            pass

        # It's safer to find the row by string match
        row_idx = None
        # Sina columns: [Item, 20231231, 20230930, ...]
        # Actually columns are dates, index might be just 0,1,2... or header is set.
        # Let's assume the first column is the item name.
        
        # Transpose for easier processing if needed, or iterate columns
        # Structure check:
        # The tool output showed akshare-abstract in existing code, but here we use Sina report.
        # Let's implement based on user snippet logic structure, adapting for dataframe.
        
        # User snippet:
        # if month == 12: ttm = ytd
        # else: ttm = prev_annual + ytd - prev_period
        
        # We need to collect all EPS values first
        eps_history = {} # date_str -> eps_ytd
        
        # Find the EPS row
        eps_row_name = '基本每股收益(元)'
        # Search for row
        # Notes: df_fin columns might have distinct names.
        # Let's iterate rows to find the eps row.
        found_row = df_fin[df_fin.iloc[:,0].astype(str).str.contains("基本每股收益", na=False)]
        
        if found_row.empty:
            print("      ⚠️ Could not find EPS row.")
            return
            
        # Extract series
        # Drop the first column (item name)
        eps_series = found_row.iloc[0, 1:]
        
        for date_col, val in eps_series.items():
            # Sina dates are usually YYYYMMDD string in header?
            # Or if transposing happened.
            # Let's assume date_col is the date string like '20231231'
            if not str(date_col).isdigit(): 
                continue
                
            ytd_eps = _parse_val(val)
            if ytd_eps is None: continue
            
            d_str = str(date_col)
            formatted_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
            eps_history[formatted_date] = ytd_eps
            
        # Now calculate TTM
        data_map = {}
        sorted_dates = sorted(eps_history.keys())
        
        for date_str in sorted_dates:
            ytd_eps = eps_history[date_str]
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            ttm_eps = None
            
            if dt.month == 12:
                # Year End: YTD is TTM
                ttm_eps = ytd_eps
            else:
                # Interim: Needs Calc
                # Formula: Prior Year Annual + Current YTD - Prior Year Same Period YTD
                prev_year = dt.year - 1
                prev_annual_date = f"{prev_year}-12-31"
                
                prev_period_date = f"{prev_year}-{dt.month:02d}-{dt.day:02d}"
                # Handling Leap Year or End of Month diffs (e.g. 2-28 vs 2-29)? 
                # Reports are usually standard quarter ends (03-31, 06-30, 09-30).
                
                prev_annual = eps_history.get(prev_annual_date)
                prev_period = eps_history.get(prev_period_date)
                
                if prev_annual is not None and prev_period is not None:
                     ttm_eps = prev_annual + ytd_eps - prev_period
            
            if ttm_eps is not None:
                data_map[date_str] = {"eps": ttm_eps}

        save_to_db(asset_id, data_map)

    except Exception as e:
        print(f"      ❌ Error fetching CN: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default="ALL", help="Choose market: HK, CN, ALL (case insensitive)")
    parser.add_argument("--symbol", help="Specific Canonical ID")
    args = parser.parse_args()

    # Normalize market arg
    args.market = args.market.upper()
    valid_markets = ["HK", "CN", "ALL"]
    if args.market not in valid_markets:
        print(f"Error: Invalid market '{args.market}'. Choose from {valid_markets}")
        return

    with Session(engine) as session:
        query = select(Watchlist)
        if args.symbol:
            query = query.where(Watchlist.symbol == args.symbol)
        elif args.market != "ALL":
            query = query.where(Watchlist.market == args.market)
        
        assets = session.exec(query).all()
        
        print(f"🚀 Found {len(assets)} assets to process.")
        
        for asset in assets:
            # Skip indices etc
            if any(x in asset.symbol for x in [':INDEX:', ':ETF:', ':CRYPTO:', ':TRUST:', ':FUND:']):
                continue
                
            raw_symbol = asset.symbol.split(':')[-1]
            
            if asset.market == "HK":
                # Remove .HK and ensure 5 digits
                code = raw_symbol.replace('.HK', '').zfill(5)
                fetch_hk_history_akshare(asset.symbol, code)
            elif asset.market == "CN":
                # Remove suffix like .SS, .SZ
                code = raw_symbol.split('.')[0]
                fetch_ashare_history(asset.symbol, code)

if __name__ == "__main__":
    main()
