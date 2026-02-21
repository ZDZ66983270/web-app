
import sys
import os
import pdfplumber
sys.path.append(os.getcwd())

pdf_path = "data/reports/HK/00700/2025-11-13_腾讯控股_截至二零二五年九月三十日止三个月及九个月业绩公布.pdf"
print(f"Inspecting tables with settings in {pdf_path}...")

settings = [
    {}, # Default
    {"vertical_strategy": "text", "horizontal_strategy": "text"},
    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
]

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    for k, s in enumerate(settings):
        tables = page.find_tables(table_settings=s)
        print(f"Setting {k} found {len(tables)} tables")
        for table in tables:
            print(f"Table bbox: {table.bbox}")
            # print(table.extract()[:5])
