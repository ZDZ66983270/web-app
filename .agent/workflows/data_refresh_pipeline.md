---
description: Standard Data Refresh Pipeline (Clean -> Download -> ETL -> Financials -> Valuation -> Export)
---

# Data Refresh Pipeline (Full Cycle)

Follow this sequence to fully refresh the system data.
> [!WARNING]
> Order is critical. Step 3 (ETL) MUST run before Step 5 (Valuation), otherwise Valuation data (PE/PB) will be overwritten/lost.

## 1. Clean Data (Optional)
Only run this if you want to start fresh or suspect data corruption.
```bash
python3 manage_data.py
# Select option to clean/reset data if prompted
```

## 2. Download Raw Market Data
Downloads OHLCV data from external sources (Yahoo/AkShare) into `RawMarketData`.
```bash
python3 download_full_history.py
```

## 3. ETL Processing (CRITICAL)
Processes `RawMarketData` into `MarketDataDaily`.
**Note**: This uses `INSERT OR REPLACE`. It will reset columns not in Raw Data (like PE/PB) to NULL.
```bash
python3 process_raw_data_optimized.py
```

## 4. Fetch Financial Fundamentals
Fetches Revenue, Net Income, etc. Independent step, but good to run before Valuation.
```bash
python3 fetch_financials.py
```

## 5. Fetch/Update Valuation (PE/PB/Yield) (CRITICAL)
Updates `MarketDataDaily` with PE, PE(TTM), PB, and Dividend Yield.
**Must run AFTER Step 3.**
```bash
python3 fetch_valuation_history.py
```

## 6. Database Health Check
Verifies record counts and latest timestamps.
```bash
python3 check_db_status.py
```

## 7. Export Data
Generates CSV files for external use/analysis.
```bash
# Export Financials
python3 export_financials_formatted.py

# Export Daily Market Data (includes PE/PE_TTM)
python3 export_daily_csv.py
```
