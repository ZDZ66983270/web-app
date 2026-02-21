
import os
import sys
from futu import *

def find_etfs_in_filter():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    s_filter = SimpleFilter()
    s_filter.stock_field = StockField.PE_TTM
    s_filter.filter_min = 0.01
    s_filter.filter_max = 10000.0
    s_filter.is_no_filter = False
    
    print("\n--- Searching ALL filtered HK stocks (PE_TTM > 0) for ETFs ---")
    
    all_codes = []
    begin = 0
    while True:
        ret, data = quote_ctx.get_stock_filter(Market.HK, [s_filter], begin=begin, num=200)
        if ret == RET_OK:
            last_page, all_count, ret_list = data
            all_codes.extend([item.stock_code for item in ret_list])
            if last_page or len(all_codes) >= all_count:
                break
            begin += 200
        else:
            print(f"Error at {begin}: {data}")
            break
            
    print(f"Total codes fetched: {len(all_codes)}")
    
    # Batch check basic info
    etfs_found = []
    for i in range(0, len(all_codes), 200):
        batch = all_codes[i:i+200]
        ret_b, data_b = quote_ctx.get_stock_basicinfo(Market.HK, code_list=batch)
        if ret_b == RET_OK:
            etfs_batch = data_b[data_b['stock_type'] == SecurityType.ETF]
            if not etfs_batch.empty:
                etfs_found.append(etfs_batch)
        
    if etfs_found:
        final_etfs = pd.concat(etfs_found)
        print(f"🔥 Found {len(final_etfs)} ETFs with PE!")
        print(final_etfs[['code', 'name']])
    else:
        print("No ETFs found in any filtered results.")
        
    quote_ctx.close()

if __name__ == "__main__":
    find_etfs_in_filter()
