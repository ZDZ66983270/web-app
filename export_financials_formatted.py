
import os
import pandas as pd
import argparse
from sqlmodel import Session, select
from backend.database import engine
from backend.models import FinancialFundamentals, Watchlist

def export_formatted(target_symbol=None):
    print("🚀 Exporting formatted financials...")
    if target_symbol:
        print(f"🎯 Target Symbol: {target_symbol}")
    
    with Session(engine) as session:
        # Load all watchlist items for symbol mapping (includes stocks, ETFs, and indices)
        watchlist_items = session.exec(select(Watchlist)).all()
        
        # Map: identifying_key (Canonical ID or pure symbol) -> (Canonical ID, Name)
        key_to_meta = {}
        
        for item in watchlist_items:
            # item.symbol is Canonical ID
            meta = (item.symbol, item.name or item.symbol)
            key_to_meta[item.symbol] = meta
            
            # Also map pure symbol if available (e.g. 09988 from HK:STOCK:09988)
            pure_symbol = item.symbol.split(':')[-1]
            if pure_symbol not in key_to_meta:
                key_to_meta[pure_symbol] = meta

        # Fetch all financial fundamentals that have data
        stmt = select(FinancialFundamentals).where(
            (FinancialFundamentals.revenue_ttm != None) | 
            (FinancialFundamentals.total_assets != None)
        ).where(FinancialFundamentals.as_of_date != '2025-12-27') # Filter out TTM snapshot
        
        if target_symbol:
            stmt = stmt.where(FinancialFundamentals.symbol == target_symbol)
            
        stmt = stmt.order_by(FinancialFundamentals.symbol, FinancialFundamentals.as_of_date.desc())
        
        funds = session.exec(stmt).all()
        
        data = []
        for fund in funds:
            # Try to get Canonical ID and Name
            canonical_id, name = key_to_meta.get(fund.symbol, (fund.symbol, "Unknown"))
            
            # If still unknown and not in key_to_meta, we might want to skip or keep as is
            # For this task, we want everything in the export to be mapped correctly
            if name == "Unknown" and fund.symbol not in key_to_meta:
                continue
                
            row = fund.model_dump()
            row['symbol'] = canonical_id  # Update symbol to Canonical ID
            row['name'] = name
            data.append(row)
            
        from backend.models import FINANCIAL_EXPORT_COLUMNS
        
        # 1. Expand data into full DataFrame
        df = pd.DataFrame(data)
        
        if df.empty:
            print("❌ No data found.")
            return

        # --- Define field categories ---
        # Monetary fields to scale (billion units)
        money_fields = [
            'revenue_ttm', 'gross_profit_ttm', 'operating_profit_ttm', 'ebit_ttm',
            'net_income_ttm', 'net_income_common_ttm', 'non_recurring_profit_ttm',
            'r_and_d_expense_ttm', 'interest_expense_ttm', 'provision_expense',
            'operating_cashflow_ttm', 'capex_ttm', 'free_cashflow_ttm',
            'investing_cashflow_ttm', 'financing_cashflow_ttm', 'share_buyback_amount_ttm',
            'total_assets', 'total_liabilities', 'total_debt', 'net_debt',
            'cash_and_equivalents', 'common_equity_end', 'common_equity_begin',
            'accounts_receivable_end', 'inventory_end', 'accounts_payable_end',
            'total_loans', 'loan_loss_allowance', 'npl_balance', 'dividend_amount',
            'buyback_amount', 'short_term_debt', 'long_term_debt'
        ]
        
        # Ratio fields to round
        ratio_fields = [
            'debt_to_equity', 'dividend_yield', 'payout_ratio', 'buyback_ratio',
            'current_ratio', 'interest_coverage', 'return_on_invested_capital',
            'npl_ratio', 'provision_coverage', 'core_tier1_ratio', 
            'tier1_capital_ratio', 'capital_adequacy_ratio'
        ]

        # 2. Apply Scaling and Formatting
        for col in money_fields:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: round(x / 100000000, 2) if pd.notnull(x) else None)
                # Keep original name for now to match FINANCIAL_EXPORT_COLUMNS, 
                # but we'll add (亿) to the header later
        
        for col in ratio_fields:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: round(x, 2) if pd.notnull(x) else None)

        # 3. Final Column Selection & Ordering
        # Base metadata
        base_cols = ['symbol', 'name', 'currency', 'as_of_date', 'report_type']
        
        # All columns from FINANCIAL_EXPORT_COLUMNS (excluding those already in base_cols)
        indicator_cols = [c for c in FINANCIAL_EXPORT_COLUMNS if c not in base_cols]
        
        # Final set of columns to export
        ordered_cols = base_cols + indicator_cols
        
        # Filter to only existing columns
        final_cols = [c for c in ordered_cols if c in df.columns]
        df = df[final_cols]
        
        # 4. Clean Header Names
        # Add (亿) to monetary fields
        header_map = {col: f"{col} (亿)" for col in money_fields if col in df.columns}
        df.rename(columns=header_map, inplace=True)
        
        # Remove _ttm suffix for cleaner looks
        df.columns = [c.replace('_ttm', '') for c in df.columns]
        
        # 2. Fix Encoding (UTF-8-SIG for Excel)
        output_dir = "outputs"
        
        if target_symbol:
            safe_symbol = target_symbol.replace(':', '_')
            output_file = os.path.join(output_dir, f"financials_overview_{safe_symbol}.csv")
        else:
            output_file = os.path.join(output_dir, "financials_overview_v2.csv")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"✅ Exported {len(df)} records to {output_file}")
        print("   (Numbers scaled to '亿', Encoding: utf-8-sig)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export Financial Data')
    parser.add_argument('--symbol', type=str, help='Canonical ID to filter (e.g. US:STOCK:AAPL)')
    args = parser.parse_args()
    
    export_formatted(args.symbol)
