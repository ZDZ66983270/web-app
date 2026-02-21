import sys
import os
import pandas as pd
from sqlmodel import Session, select

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine
from backend.models import FinancialFundamentals, FINANCIAL_EXPORT_COLUMNS

def export_to_csv(symbol=None):
    """
    Export financial data from DB to CSV.
    """
    with Session(engine) as session:
        query = select(FinancialFundamentals)
        if symbol:
            query = query.where(FinancialFundamentals.symbol == symbol)
        
        results = session.exec(query).all()
        if not results:
            print(f"⚠️ No financial records found for {symbol or 'ALL'} in database.")
            return
        
        # Convert to list of dicts for DataFrame
        data_list = []
        for r in results:
            # We use the row dictionary but filter/order by FINANCIAL_EXPORT_COLUMNS
            row_dict = r.dict()
            data_list.append(row_dict)
        
        df = pd.DataFrame(data_list)
        
        # --- NEW: Source-based Priority Merging ---
        # 1. Define source priority (Higher is better)
        source_priority = {
            'akshare-hk-annual': 100,
            'akshare-cn-abstract': 90,
            'pdf-parser': 80,
            'sec-edgar': 70,
            'fmp': 60,
            'yahoo': 50
        }
        df['priority'] = df['data_source'].map(lambda x: source_priority.get(x, 0))
        
        # 2. Sort by symbol, as_of_date, and priority (desc)
        df = df.sort_values(by=['symbol', 'as_of_date', 'priority'], ascending=[True, True, False])
        
        # 3. Drop duplicates, keeping the highest priority source for each (symbol, as_of_date)
        before_count = len(df)
        df = df.drop_duplicates(subset=['symbol', 'as_of_date'], keep='first')
        after_count = len(df)
        print(f"🔄 Merged {before_count} records into {after_count} high-quality unique entries.")
        
        # 4. Clean up temporary column
        df = df.drop(columns=['priority'])
        
        # Ensure all standard columns exist (even if empty)
        for col in FINANCIAL_EXPORT_COLUMNS:
            if col not in df.columns:
                df[col] = None
                
        # Filter and reorder columns
        df = df[FINANCIAL_EXPORT_COLUMNS]
        
        # Output directory
        output_dir = "data/exports"
        os.makedirs(output_dir, exist_ok=True)
        
        if symbol:
            safe_symbol = symbol.replace(':', '_')
            output_file = os.path.join(output_dir, f"{safe_symbol}_financials.csv")
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"✅ Exported {len(df)} records for {symbol} to {output_file}")
        else:
            output_file = os.path.join(output_dir, "all_financials.csv")
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"✅ Exported total {len(df)} records for ALL symbols to {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', type=str, help='Specific symbol to export')
    args = parser.parse_args()
    
    export_to_csv(symbol=args.symbol)
