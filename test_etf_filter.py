
import os
import sys
from futu import *

def test_etf_filter_pe():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    
    # FinancialFilter for PE_TTM
    f_filter = FinancialFilter()
    f_filter.filter_id = StockField.PE_TTM
    f_filter.begin = 0.1 # Greater than 0
    f_filter.end = 1000
    f_filter.quarter = FinancialQuarter.ANNUAL
    
    print("\n--- Filtering HK Market for ETFs with PE_TTM > 0 ---")
    # We can't specify ETF in get_stock_filter directly? 
    # Let's check get_stock_filter doc or dir
    
    ret, data = quote_ctx.get_stock_filter(Market.HK, [f_filter])
    if ret == RET_OK:
        print(f"Total matched: {len(data)}")
        # Check if any ETF is in the results
        # We need to get basic info to check types
        if len(data) > 0:
            codes = data['code'].tolist()[:50]
            ret_b, data_b = quote_ctx.get_stock_basicinfo(Market.HK, code_list=codes)
            if ret_b == RET_OK:
                etfs = data_b[data_b['stock_type'] == SecurityType.ETF]
                if not etfs.empty:
                    print("🔥 Found ETFs with PE via filter!")
                    print(etfs)
                else:
                    print("No ETFs found in the filtered list (only stocks).")
    else:
        print(f"Error: {data}")
        
    quote_ctx.close()

if __name__ == "__main__":
    test_etf_filter_pe()
