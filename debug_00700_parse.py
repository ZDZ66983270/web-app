
import sys
import os
sys.path.append(os.getcwd())
from backend.parsers.pdf_parser import PDFFinancialParser

pdf_path = "data/reports/HK/00700/2016-08-31_腾讯控股_中期报告2016.pdf"
print(f"Parsing {pdf_path}...")
parser = PDFFinancialParser(pdf_path=pdf_path)
data = parser.parse_financials()

print("\n--- RESULTS ---")
print(f"Revenue: {data.get('revenue_ttm')}")
print(f"Shares: {data.get('shares_outstanding_common_end')}")
print(f"Period: {data.get('report_date')}")
print(f"Type: {data.get('report_type')}")
print("\n--- LOGS ---")
for msg in data.get('debug_logs', []):
    print(msg)
