import os
import re
import csv
import pandas as pd
from datetime import datetime
from collections import Counter

# 配置
TICKER = "MSFT"
EMAIL = "admin@vera-analytics.local"
COMPANY = "VERA-AI-Bot"
YEARS = 10
OUTPUT_CSV = "outputs/msft_financials_10yr.csv"

def get_filing_paths():
    base_path = f"sec-edgar-filings/{TICKER}/10-K"
    if not os.path.exists(base_path):
        return []
    paths = []
    for folder in os.listdir(base_path):
        f_path = os.path.join(base_path, folder, "full-submission.txt")
        if os.path.exists(f_path):
            paths.append(f_path)
    return paths

def discover_tags(file_paths):
    """扫描所有文件，找出出现频率最高的 us-gaap 标签"""
    print("第一步：扫描所有财报以自动发现财务指标标签...")
    all_tags = Counter()
    
    # 匹配模式：us-gaap:TagName 或者 ix:nonFraction ... name="us-gaap:TagName"
    # 我们只想要数值型的标签，通常伴随着 contextRef
    pattern = re.compile(r'<(?:us-gaap:)([a-zA-Z0-9\-]+)\s+[^>]*contextRef="([^"]+)"')
    ix_pattern = re.compile(r'ix:[^>]*name="us-gaap:([a-zA-Z0-9\-]+)"[^>]*contextRef="([^"]+)"')

    for path in file_paths:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            matches = pattern.findall(content) + ix_pattern.findall(content)
            for tag, ctx in matches:
                # 过滤掉非合并报表的维度数据
                if not any(x in ctx for x in ['Member', 'Axis', 'Segment', 'Standalone']):
                    all_tags[tag] += 1
    
    # 筛选：在至少 5 个报表中出现过的标签（确保具有一定的通用性）
    popular_tags = [tag for tag, count in all_tags.items() if count >= 3]
    print(f"成功发现 {len(popular_tags)} 个常用财务指标标签。")
    return sorted(popular_tags)

def extract_all_data(file_paths, target_tags):
    """提取选定标签的数据"""
    print("第二步：提取选定指标的具体数值并去重...")
    results = []
    
    for path in file_paths:
        acc_num = os.path.basename(os.path.dirname(path))
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            # 提取财报年份
            year_match = re.search(r'<(?:dei:)?DocumentFiscalYearFocus[^>]*>(\d{4})</', content)
            year = year_match.group(1) if year_match else "Unknown"
            
            data = {"Accession Number": acc_num, "Year": year}
            
            for tag in target_tags:
                # 兼容普通 XBRL 和 Inline XBRL
                tag_pattern = rf'<(?:us-gaap:)?{tag}\s+[^>]*contextRef="([^"]+)"[^>]*>([\d\.,\(\)\s\-]+)</'
                ix_pattern = rf'<ix:[^>]*name="(?:us-gaap:)?{tag}"[^>]*contextRef="([^"]+)"[^>]*>([\d\.,\(\)\s\-]+)</ix:'
                
                matches = re.findall(tag_pattern, content) + re.findall(ix_pattern, content)
                
                if matches:
                    candidates = []
                    for ctx, val_str in matches:
                        if not any(x in ctx for x in ['Member', 'Axis', 'Segment', 'Standalone']):
                            val_str = val_str.strip().replace(',', '')
                            if val_str.startswith('(') and val_str.endswith(')'):
                                val_str = '-' + val_str[1:-1]
                            try:
                                candidates.append(float(val_str))
                            except:
                                continue
                    if candidates:
                        # 启发式：取绝对值最大或简单的逻辑，这里选最大值
                        data[tag] = max(candidates)
            
            results.append(data)
    
    # 转换为 DataFrame 并智能去重（按年份保留最新披露的数据）
    df = pd.DataFrame(results)
    if 'Year' in df.columns:
        df = df[df['Year'].str.isdigit()]
        df = df.sort_values(by=["Year", "Accession Number"], ascending=[False, False])
        df = df.drop_duplicates(subset=["Year"], keep="first")
    
    return df

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    paths = get_filing_paths()
    if not paths:
        print("未发现下载的 10-K 文件。")
    else:
        tags = discover_tags(paths)
        if tags:
            # 如果标签太多（比如几百个），我们可以进一步筛选或者只保留最常用的
            # 但用户想要“好几十个”，我们就全给
            final_df = extract_all_data(paths, tags)
            final_df.to_csv(OUTPUT_CSV, index=False)
            print(f"\n成功！生成的 CSV 包含 {len(final_df)} 行年份数据和 {len(final_df.columns)} 个字段。")
            print(f"文件位置: {OUTPUT_CSV}")
            
            # 打印前 20 个字段展示一下
            print("\n前 20 个字段预览:")
            print(final_df.columns[:20].tolist())
