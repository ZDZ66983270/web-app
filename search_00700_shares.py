
import sys
import os
import pdfplumber
sys.path.append(os.getcwd())

pdf_path = "data/reports/HK/00700/2016-08-31_腾讯控股_中期报告2016.pdf"
print(f"Searching for shares in {pdf_path}...")

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text and ("股份" in text or "Shares" in text or "股本" in text):
            print(f"\n--- Page {i+1} ---")
            for line in text.split('\n'):
                if "股份" in line or "Shares" in line or "股本" in line:
                    print(line)
