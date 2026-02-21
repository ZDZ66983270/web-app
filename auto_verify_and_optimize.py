
import os
import sys
import subprocess
import time
import pandas as pd
import re
from datetime import datetime

LOG_FILE = "auto_optimization.log"

def log(msg):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} {msg}\n")

def run_command(cmd, desc):
    log(f"🚀 开始执行: {desc}")
    log(f"   Cmd: {cmd}")
    try:
        # Check running processes first? No, assume user wants to run now.
        start_time = time.time()
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Stream output
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   > {output.strip()}")
        
        rc = process.poll()
        duration = time.time() - start_time
        
        if rc == 0:
            log(f"✅ {desc} 完成 (耗时 {duration:.1f}s)")
            return True
        else:
            _, stderr = process.communicate()
            log(f"❌ {desc} 失败 (Exit Code {rc})")
            if stderr:
                log(f"   Error: {stderr}")
            return False
            
    except Exception as e:
        log(f"❌ 执行异常: {e}")
        return False

def analyze_deviations(csv_file="pe_comparison.csv"):
    if not os.path.exists(csv_file):
        log(f"⚠️ 未找到校验文件: {csv_file}")
        return
        
    log("🔍 分析偏差数据...")
    try:
        # Read CSV (skip header line if formatted text, but verify_pe_with_yahoo usually prints table)
        # Wait, verify_pe_with_yahoo writes a cleaner CSV? Let's assume standard CSV format or parse text.
        # Actually verify_pe_with_yahoo.py writes a file named 'pe_comparison.csv' with columns:
        # Symbol, Market, Date, DB_PE, Yahoo_PE, Diff_Pct
        
        df = pd.read_csv(csv_file)
        
        # Clean percentage strings
        if 'Diff %' in df.columns:
            df['Diff_Abs'] = df['Diff %'].str.rstrip('%').astype(float).abs()
        elif 'Diff_Pct' in df.columns:
            df['Diff_Abs'] = df['Diff_Pct'].str.rstrip('%').astype(float).abs()
        else:
            # Fallback for verifying strict schema
            log("⚠️ CSV 格式无法识别偏差列")
            return

        # High Deviation Threshold
        THRESHOLD = 10.0
        
        high_diffs = df[df['Diff_Abs'] > THRESHOLD]
        
        if not high_diffs.empty:
            log(f"⚠️ 发现 {len(high_diffs)} 个偏差 > {THRESHOLD}% 的资产:")
            for _, row in high_diffs.iterrows():
                u_sym = row.get('Symbol', row.get('symbol', 'Unknown'))
                u_db = row.get('DB PE', row.get('db_pe', 'N/A'))
                u_yahoo = row.get('Yahoo PE', row.get('yahoo_pe', 'N/A'))
                u_diff = row.get('Diff %', row.get('diff_pct', 'N/A'))
                log(f"   ❌ {u_sym}: DB={u_db}, Yahoo={u_yahoo}, Diff={u_diff}")
                
            log("\n💡 建议: ")
            log("   1. 检查数据源 (Yahoo/FMP) 是否混淆了 TTM/Quarterly/Annual")
            log("   2. 检查 ADR 换算比例 (ADR_RATIO_MAP) 是否正确")
            log("   3. 检查财报货币单位 (CNY/USD/HKD) 是否一致")
        else:
            log(f"✅ 所有资产偏差均在 {THRESHOLD}% 以内！目标达成！🎉")
            
    except Exception as e:
        log(f"❌ 分析失败: {e}")

def main():
    log("=" * 60)
    log("🤖 自动估值校验与优化脚本")
    log("=" * 60)
    
    # 1. 计算估值 (Fetch Valuation History)
    # Using --days 365 to ensure full history backfill based on new financials
    # Must specify --market ALL to bypass interactive menu
    if not run_command("python3 fetch_valuation_history.py --market ALL --days 5", "计算历史估值 (5天)"):
        return

    # 2. 导出数据 (Export Daily CSV) - Optional but good for verification
    if not run_command("python3 export_daily_csv.py", "导出日线数据"):
        pass

    # 3. 校验对比 (Verify PE with Yahoo)
    if not run_command("python3 verify_pe_with_yahoo.py", "与 Yahoo Finance 进行 PE 校验"):
        return

    # 4. 分析结果
    analyze_deviations()
    
    log("=" * 60)
    log("🏁 任务结束")
    log("=" * 60)

if __name__ == "__main__":
    main()
