import sys
import os
sys.path.append(os.getcwd())
from backend.parsers.pdf_parser import PDFFinancialParser

if len(sys.argv) < 2:
    print("Usage: python3 debug_pdf.py <pdf_path> [symbol]")
    sys.exit(1)

fpath = sys.argv[1]
symbol = sys.argv[2] if len(sys.argv) > 2 else "DEBUG"

print(f"Parsing {fpath}...")
parser = PDFFinancialParser(pdf_path=fpath, asset_id=symbol)
data = parser.parse_financials()

print("-" * 40)
print(f"Report Date: {data.get('report_date')}")
print(f"Revenue: {data.get('revenue')} (Raw: {data.get('revenue_ttm')})")
print(f"Net Income: {data.get('net_income')} (Raw: {data.get('net_income_ttm')})")
print(f"Total Assets: {data.get('total_assets')}")
print("-" * 40)
