
import os
import sys

# Add project root to path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path: sys.path.append(base_dir)

from backend.parsers.pdf_parser import PDFFinancialParser

def test_hsbc_parse():
    pdf_path = "data/reports/HK/00005/2025-07-30_汇丰控股_2025年中期业绩.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
        
    print(f"🔍 Parsing {pdf_path}...")
    parser = PDFFinancialParser(pdf_path=pdf_path, asset_id="HK:STOCK:00005")
    data = parser.parse_financials()
    
    print("\n📄 Extracted Text (First 10k):")
    print(parser.text_content[:10000])
    for k, v in data.items():
        if v is not None and k != 'raw_text' and k != 'debug_logs':
            print(f"  - {k}: {v}")
            
    print("\n📝 Debug Logs:")
    for log in parser.logs:
        print(f"  {log}")

if __name__ == "__main__":
    test_hsbc_parse()
