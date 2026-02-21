import sys
import os
import logging
from backend.parsers.pdf_parser import PDFFinancialParser

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def debug_pdf_extraction(pdf_path, symbol="CN:STOCK:600536"):
    print(f"\n{'='*50}")
    print(f"🔍 DEBUGGING PDF: {os.path.basename(pdf_path)}")
    print(f"{'='*50}\n")
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    try:
        # Initialize parser
        parser = PDFFinancialParser(pdf_path=pdf_path, asset_id=symbol)
        
        # 1. Test Raw Text Extraction First
        print("--- [Step 1: Content Extraction] ---")
        parser.extract_content(max_pages=20) # Only first 20 pages for debug
        print(f"✅ Extracted {len(parser.text_content)} chars.")
        print(f"Snapshot (First 500 chars):\n{parser.text_content[:500]}...\n")
        
        # 2. Test Table Parse
        print("\n--- [Step 2: Table Extraction] ---")
        table_data = parser._parse_tables()
        print(f"📊 Table Extraction Results ({len(table_data)} items):")
        for k, v in table_data.items():
            print(f"   - {k}: {v}")
            
        # 3. Test Full Parse Logic
        print("\n--- [Step 3: Full Logic Execution] ---")
        data = parser.parse_financials()
        
        print("\n--- [Step 4: Final Parsed Data] ---")
        fields_of_interest = [
             "revenue_ttm", "net_income_ttm", "dividend_amount", 
             "dividend_per_share", "shares_outstanding_common_end"
        ]
        
        for k in fields_of_interest:
            print(f"   👉 {k}: {data.get(k)}")
            
        # 4. Dump internal logs
        print("\n--- [Step 5: Internal Logs] ---")
        for log in parser.logs:
            if "DEBUG" in log or "⚠️" in log or "Match" in log:
                 print(f"   [LOG] {log}")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Target specific report: 2024 Half Year Report
    target_pdf = "data/reports/CN/600536/2024-08-29_中国软件2024年半年度报告全文.pdf"
    debug_pdf_extraction(target_pdf)
