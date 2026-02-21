import sys
import os
import pdfplumber
import logging
from backend.parsers.pdf_parser import PDFFinancialParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def debug_pdf_tables_deep(pdf_path):
    print(f"\n{'='*50}")
    print(f"🔬 DEEP TABLE DEBUG: {os.path.basename(pdf_path)}")
    print(f"{'='*50}\n")
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Focus on pages that likely contain key tables (usually page 2-15 for summary)
            # Scan specifically for the page with "主要会计数据"
            target_page_idx = -1
            
            for i, page in enumerate(pdf.pages[:20]):
                text = page.extract_text()
                if text and "主要会计数据" in text:
                    print(f"🎯 Found '主要会计数据' on Page {i+1}")
                    target_page_idx = i
                    break
            
            if target_page_idx == -1:
                print("⚠️ Could not find '主要会计数据' page. Defaulting to Page 11")
                target_page_idx = 10 

            page = pdf.pages[target_page_idx]
            
            print(f"\n--- Strategy A: Default extract_tables() ---")
            tables = page.extract_tables()
            for i, t in enumerate(tables):
                print(f"  Table {i}: {len(t)} rows. Top row: {t[0] if t else 'Empty'}")
                if len(t) > 3:
                     print(f"    Row 2: {t[1]}")
                     print(f"    Row 3: {t[2]}")
            
            print(f"\n--- Strategy B: Text Strategy (snap_tolerance=3) ---")
            tables_txt = page.extract_tables({
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
            })
            for i, t in enumerate(tables_txt):
                print(f"  Table {i}: {len(t)} rows. Top row: {t[0] if t else 'Empty'}")
                if len(t) > 3:
                     # Check if it looks clean
                     val_row = t[2]
                     clean_vals = [str(c).replace('\n', '') for c in val_row]
                     print(f"    Row 3 (Clean): {clean_vals}")

            print(f"\n--- Strategy C: Lines Strategy (explicit) ---")
            tables_lines = page.extract_tables({
                "vertical_strategy": "lines", 
                "horizontal_strategy": "lines"
            })
            for i, t in enumerate(tables_lines):
                 print(f"  Table {i}: {len(t)} rows.")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    target_pdf = "data/reports/CN/600536/2024-08-29_中国软件2024年半年度报告全文.pdf"
    debug_pdf_tables_deep(target_pdf)
