
import os
import sys
from futu import *

def test_etf_filter_pe_v2():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Try a SimpleFilter for PE_TTM
    s_filter = SimpleFilter()
    s_filter.stock_field = StockField.PE_TTM
    s_filter.filter_min = 0.01
    s_filter.filter_max = 1000.0
    s_filter.is_no_filter = False
    
    print("\n--- Filtering HK Market for PE_TTM > 0 ---")
    
    try:
        ret, data = quote_ctx.get_stock_filter(Market.HK, [s_filter])
        if ret == RET_OK:
            last_page, all_count, ret_list = data
            print(f"Total matched: {all_count}")
            for item in ret_list[:10]:
                print(f"  {item.stock_code} ({item.stock_name}): PE_TTM = {getattr(item, 'pe_ttm', 'N/A')}")
            
            # Check specifically for HK.02800 if we didn't see it
            # But it won't be in the list if its PE is 0.
        else:
            print(f"Error from API: {data}")
    except Exception as e:
        print(f"Caught Exception: {e}")
        import traceback
        traceback.print_exc()
        
    quote_ctx.close()

if __name__ == "__main__":
    test_etf_filter_pe_v2()
