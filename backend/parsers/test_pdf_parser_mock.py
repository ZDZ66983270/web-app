
import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.parsers.pdf_parser import PDFFinancialParser

class TestPDFFinancialParser(unittest.TestCase):
    
    def test_mock_ICBC_report(self):
        """
        Simulate a snippet from ICBC 2023 Annual Report (Mock Text)
        """
        mock_text = """
        中国工商银行股份有限公司
        2023 年度报告
        
        主要会计数据和财务指标
        (除特别注明外，以人民币百万元列示)
        
        截至 2023 年 12 月 31 日  |  2022 年
        ----------------------------------
        营业收入   843,070   |  841,441
        利息净收入 655,013   |  693,687
        手续费及佣金净收入 119,390 | 129,265
        
        归属于母公司股东的净利润 363,993 | 360,483
        
        基本每股收益 (元)    0.98   |   0.97
        
        资产总计  44,697,079 | 39,609,51
        负债合计  40,920,526 | 36,095,83
        
        发放贷款和垫款总额 26,086,170
        不良贷款余额      353,502
        不良贷款率        1.36%
        拨备覆盖率        213.97%
        
        核心一级资本充足率 13.72%
        
        普通股股本     356,407 (百万股)
        """
        
        # Instantiate parser with mock text
        parser = PDFFinancialParser(text_content=mock_text, asset_id="CN:STOCK:600036")
        data = parser.parse_financials()
        
        print("\n--- Parsed Data ---")
        for k, v in data.items():
            if k != "raw_text" and k != "debug_logs":
                print(f"{k}: {v}")
        
        # Validations
        self.assertEqual(data['report_date'], "2023-12-31")
        self.assertEqual(data['report_type'], "annual")
        self.assertEqual(data['global_unit'], 1_000_000) # Detected '百万元'
        
        # Financials (Should be normalized to base unit: 1.0)
        # Input 843,070 (Million) -> 843,070,000,000
        self.assertAlmostEqual(data['revenue'], 843_070_000_000, delta=1_000_000)
        self.assertAlmostEqual(data['net_profit'], 363_993_000_000, delta=1_000_000)
        self.assertAlmostEqual(data['total_assets'], 44_697_079_000_000, delta=1_000_000_000)
        
        # Ratios (No unit scaling)
        self.assertEqual(data['eps'], 0.98)
        self.assertEqual(data['npl_ratio'], 1.36)
        self.assertEqual(data['provision_coverage'], 213.97)

if __name__ == '__main__':
    unittest.main()
