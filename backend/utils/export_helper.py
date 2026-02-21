import os
import pandas as pd
from sqlmodel import Session, select
from typing import List, Optional
from database import engine
from models import FinancialFundamentals, FINANCIAL_EXPORT_COLUMNS

def export_symbol_to_csv(symbol: str, filename: str, cutoff_date: str = "2010-01-01"):
    """
    Unified export function that maps all FinancialFundamentals fields to CSV.
    Ensures that both generic and bank-specific fields are exported.
    """
    with Session(engine) as session:
        statement = select(FinancialFundamentals).where(
            FinancialFundamentals.symbol == symbol,
            FinancialFundamentals.as_of_date >= cutoff_date
        ).order_by(FinancialFundamentals.as_of_date.desc(), FinancialFundamentals.data_source.desc())
        results = session.exec(statement).all()
        
    if not results:
        print(f"❌ No records found for {symbol} since {cutoff_date}")
        return

    # Source Consolidation Logic
    # If multiple rows exist for the same date, merge them preferring 'pdf-parser'
    merged_data = {}
    for r in results:
        dt = str(r.as_of_date)
        r_dict = r.model_dump()
        if dt not in merged_data:
            merged_data[dt] = r_dict
        else:
            # Merge: Prefer non-null values, and prefer 'pdf-parser' source
            current = merged_data[dt]
            # If the NEW record is from pdf-parser, it should generally win for metrics
            is_new_pdf = (r_dict.get('data_source') == 'pdf-parser')
            for k, v in r_dict.items():
                if v is not None:
                    # Update if current is None OR if this is a PDF source and current isn't
                    if current.get(k) is None or (is_new_pdf and k not in id_cols):
                        current[k] = v
            # Update source combined info
            if r_dict.get('data_source') not in current.get('data_source', ''):
                current['data_source'] = f"{current['data_source']}+{r_dict.get('data_source')}"

    data = list(merged_data.values())
    df = pd.DataFrame(data)

    # 2. Enforce 55-Column Standard Consistency
    # Avoid dynamic column dropping by reindexing with the master list from models
    
    # Ensure all columns exist (adds NaN for missing columns)
    df = df.reindex(columns=FINANCIAL_EXPORT_COLUMNS)

    # Export to CSV
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    full_path = os.path.join(output_dir, filename)

    df.to_csv(full_path, index=False, encoding='utf-8-sig')
    print(f"✅ Successfully exported {len(results)} records to {full_path} (Forced Alignment: 55 Columns)")
    return full_path
