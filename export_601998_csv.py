"""
中信银行财报数据导出脚本 (已优化)
Export CITIC Bank financial data to CSV using unified helper
"""
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from utils.export_helper import export_symbol_to_csv

def main():
    symbol = "CN:STOCK:601998"
    filename = "中信银行_近10年财报数据.csv"
    export_symbol_to_csv(symbol, filename)

if __name__ == "__main__":
    main()
