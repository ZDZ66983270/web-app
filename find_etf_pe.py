
import os
import sys
from futu import *

def find_etfs_with_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Filter for PE_TTM > 0
    s_filter = SimpleFilter()
    s_filter.stock_field = StockField.PE_TTM
    s_filter.filter_min = 0.01
    s_filter.filter_max = 10000.0
    s_filter.is_no_filter = False
    
    print("\n--- Searching for ETFs with PE_TTM > 0 ---")
    ret, data = quote_ctx.get_stock_filter(Market.HK, [s_filter], num=200)
    if ret == RET_OK:
        lp, ac, ret_list = data
        codes = [item.stock_code for item in ret_list]
        
        # Get basic info to check types
        ret_b, data_b = quote_ctx.get_stock_basicinfo(Market.HK, code_list=codes)
        if ret_b == RET_OK:
            etfs = data_b[data_b['stock_type'] == SecurityType.ETF]
            if not etfs.empty:
                print(f"🔥 Found {len(etfs)} ETFs with PE!")
                # Join back to get PE
                for _, row in etfs.iterrows():
                    # Find item in ret_list
                    item = next(it for it in ret_list if it.stock_code == row['code'])
                    print(f"  {row['code']} ({row['name']}): PE = {item.pe_ttm}")
            else:
                print("No ETFs found among 200 stocks with PE.")
    else:
         print(f"Error: {data}")
         
    quote_ctx.close()

if __name__ == "__main__":
    find_etfs_with_pe()
