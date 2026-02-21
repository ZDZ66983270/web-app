"""
简化的基于表格的财报解析器
直接提取PDF表格，按行匹配关键词
"""

import pdfplumber
import re
from typing import Dict, Any, Optional, List

class TableBasedParser:
    """基于表格的财报解析器"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.data = {}
    
    def parse(self) -> Dict[str, Any]:
        """解析财报"""
        with pdfplumber.open(self.pdf_path) as pdf:
            # 扫描前30页查找财报表格
            for page in pdf.pages[:30]:
                tables = page.extract_tables()
                if not tables:
                    continue
                
                for table in tables:
                    self._parse_table(table)
        
        return self.data
    
    def _parse_table(self, table: List[List[str]]):
        """解析单个表格"""
        for row in table:
            if not row or not row[0]:
                continue
            
            label = str(row[0]).strip()
            
            # 提取第一个数值列（通常是当期数据）
            value = self._extract_number(row[1] if len(row) > 1 else None)
            
            if not value:
                continue
            
            # 营业收入
            if '营业收入' in label and '营业总收入' not in label:
                if '营业收入' == label:  # 精确匹配
                    self.data['revenue'] = value
            
            # 营业成本
            elif '营业成本' in label and '营业总成本' not in label:
                if '营业成本' == label:
                    self.data['cost_of_revenue'] = value
            
            # 研发费用
            elif '研发费用' in label:
                self.data['rd_expense'] = value
            
            # 销售费用
            elif '销售费用' in label:
                self.data['selling_expense'] = value
            
            # 管理费用
            elif '管理费用' in label:
                self.data['admin_expense'] = value
            
            # 财务费用
            elif '财务费用' in label:
                self.data['finance_expense'] = value
            
            # 净利润（归母）
            elif '归属于母公司' in label and '净利润' in label:
                self.data['net_profit'] = value
            elif '归属于上市公司股东的净利润' in label:
                self.data['net_profit'] = value
            
            # 经营现金流
            elif '经营活动产生的现金流量净额' in label:
                self.data['operating_cashflow'] = value
            
            # 投资现金流
            elif '投资活动产生的现金流量净额' in label:
                self.data['investing_cashflow'] = value
            
            # 筹资现金流
            elif '筹资活动产生的现金流量净额' in label:
                self.data['financing_cashflow'] = value
            
            # 总资产
            elif label == '资产总计' or label == '总资产':
                self.data['total_assets'] = value
            
            # 总负债
            elif label == '负债合计' or label == '总负债':
                self.data['total_liabilities'] = value
    
    def _extract_number(self, cell: Optional[str]) -> Optional[float]:
        """从单元格提取数值"""
        if not cell:
            return None
        
        # 移除逗号和空格
        cell = str(cell).replace(',', '').replace(' ', '').replace('，', '')
        
        # 提取数字（包括负数和小数）
        match = re.search(r'-?\d+\.?\d*', cell)
        if match:
            try:
                return float(match.group())
            except:
                return None
        
        return None


# 测试
if __name__ == '__main__':
    parser = TableBasedParser('data/reports/CN/600309/2024-03-19_万华化学2023年年度报告.pdf')
    data = parser.parse()
    
    print('=== 提取结果 ===')
    for key, value in sorted(data.items()):
        if value:
            print(f'{key}: {value:,.0f} ({value/1e8:.2f}亿)')
