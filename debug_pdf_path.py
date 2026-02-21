
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/reports")
symbol = "HK:STOCK:00700"
code = symbol.split(':')[-1]
pdf_target_dir = os.path.join(DATA_DIR, 'HK', code)

print(f"Data Dir: {DATA_DIR}")
print(f"Target Dir: {pdf_target_dir}")
print(f"Exists: {os.path.exists(pdf_target_dir)}")

if os.path.exists(pdf_target_dir):
    print(f"Contents: {os.listdir(pdf_target_dir)}")
    
# Check PDF parser availability
try:
    from backend.parsers.pdf_parser import PDFFinancialParser
    print("Parser available")
except ImportError as e:
    print(f"Parser missing: {e}")
