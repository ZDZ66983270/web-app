
import os
import sys
from futu import *

def test_stock_filter_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # Try to filter specifically for HK.02800 and get its financial data
    # Note: Stock filter might not support filtering a specific list of codes easily if it's large,
    # but let's try to set a filter that only matches HK.02800
    
    simple_filter = SimpleFilter()
    simple_filter.filter_id = SortField.PE_TTM
    simple_filter.begin = 0
    simple_filter.end = 1000
    
    ret, data = quote_ctx.get_stock_filter(Market.HK, [simple_filter])
    if ret == RET_OK:
        print(f"Total stocks matched: {len(data)}")
        # Check if HK.02800 or HK.03110 is in the list
        matches = data[data['code'].isin(['HK.02800', 'HK.03110', 'HK.00700'])]
        print("Matches in filter:")
        print(matches)
    else:
        print(f"Error: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    test_stock_filter_pe()
