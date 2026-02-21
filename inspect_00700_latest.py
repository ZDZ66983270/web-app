
import sys
import os
import pdfplumber
sys.path.append(os.getcwd())
from backend.parsers.pdf_parser import PDFFinancialParser

pdf_path = "data/reports/HK/00700/2025-11-13_腾讯控股_截至二零二五年九月三十日止三个月及九个月业绩公布.pdf"
print(f"Inspecting tables in {pdf_path}...")

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages[:10]):
        tables = page.extract_tables()
        if tables:
            print(f"\n--- Page {i+1} found {len(tables)} tables ---")
            for j, table in enumerate(tables):
                print(f"Table {j} rows: {len(table)}")
                for row in table[:5]:
                    print(row)
                if any("收入" in str(cell) for row in table for cell in row if cell):
                    print("Potential Finance Table detected on this page.")
