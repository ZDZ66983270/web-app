# 完整数据处理命令流程

## 🎯 完整流程 (从零开始)

### Step 1: 清空数据
```bash
python3 manage_data.py
# 交互式选择: 1 2 (清空行情和财务数据)
```

### Step 2: 下载历史数据到 RAW (3.5分钟)
```bash
python3 download_full_history.py
```

**结果**:
- 70个资产全部下载
- 358,984条记录保存到 RawMarketData
- processed = false (未触发ETL)

### Step 3: 批量 ETL 处理 (2.1分钟)
```bash
python3 process_raw_data_optimized.py
```

**结果**:
- 处理70个资产
- 生成358,984条 MarketDataDaily
- 生成70条 MarketSnapshot
- 平均速度: 1.8秒/资产

### Step 4: 获取估值数据
```bash
python3 fetch_valuation_history.py
```

**结果**:
- 更新PE/PB/股息率到 MarketDataDaily

### Step 5: 导出数据
```bash
# 导出行情数据
python3 export_daily_csv.py

# 导出财务数据
python3 export_financials_formatted.py
```

**总时间**: ~8分钟 (vs 原2.3-3.5小时)

---

## 📊 数据验证命令

### 检查数据状态
```bash
python3 << 'EOF'
from sqlmodel import Session, create_engine, text
from datetime import datetime

engine = create_engine('sqlite:///backend/database.db')

print("=" * 80)
print(f"数据状态检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

with Session(engine) as session:
    # RAW数据
    result = session.exec(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) as done
        FROM rawmarketdata
    """))
    row = result.first()
    print(f"\nRawMarketData:")
    print(f"  总计: {row[0]} 条")
    print(f"  已处理: {row[1]} 条")
    
    # Daily数据
    daily_count = session.exec(text("SELECT COUNT(*) FROM marketdatadaily")).first()[0]
    print(f"\nMarketDataDaily: {daily_count:,} 条")
    
    # Snapshot数据
    snapshot_count = session.exec(text("SELECT COUNT(*) FROM marketsnapshot")).first()[0]
    print(f"MarketSnapshot: {snapshot_count} 条")
    
    # 按市场统计
    market_stats = session.exec(text("""
        SELECT market, COUNT(*) as count
        FROM marketdatadaily
        GROUP BY market
    """)).all()
    
    print("\n按市场分布:")
    for market, count in market_stats:
        print(f"  {market}: {count:,} 条")

print("=" * 80)
EOF
```

### 检查成交量质量
```bash
python3 << 'EOF'
from sqlmodel import Session, create_engine, text

engine = create_engine('sqlite:///backend/database.db')

with Session(engine) as session:
    result = session.exec(text("""
        SELECT market,
               COUNT(*) as total,
               SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) as has_volume
        FROM marketdatadaily
        GROUP BY market
    """))
    
    print("成交量数据质量:")
    for row in result:
        market, total, has_vol = row
        pct = (has_vol / total * 100) if total > 0 else 0
        print(f"  {market}: {has_vol:,}/{total:,} ({pct:.1f}%)")
EOF
```

---

## 🔄 日常维护命令

### 增量更新 (每日运行)
```bash
# 下载最近数据
python3 daily_incremental_update.py

# 处理新增RAW (如有需要)
python3 process_raw_data_optimized.py
```

### 重新处理 ETL (ETL逻辑修改后)
```bash
# 1. 重置RAW状态
python3 -c "
from sqlmodel import Session, create_engine, text
engine = create_engine('sqlite:///backend/database.db')
with Session(engine) as session:
    session.exec(text('UPDATE rawmarketdata SET processed = 0'))
    session.commit()
    print('✅ 已重置所有 RAW 记录')
"

# 2. 清空Daily和Snapshot
python3 manage_data.py  # 选择: 1

# 3. 重新ETL
python3 process_raw_data_optimized.py
```

---

## 🛠️ 工具命令

### 数据管理工具 (交互式)
```bash
python3 manage_data.py
```

**选项**:
- 1) 清除行情数据
- 2) 清除财务数据
- 3) 清除监控列表
- 4) 从 symbols.txt 导入监控列表

### 单资产测试
```bash
python3 test_raw_etl_pipeline.py
```

---

## 📈 性能对比

| 命令 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| `download_full_history.py` | 6-12小时 | 3.5分钟 | 100倍+ |
| `process_raw_data_optimized.py` | 2-3分钟/资产 | 1.8秒/资产 | 50-100倍 |
| **总时间** | 2.3-3.5小时 | **5.6分钟** | **25-40倍** |

---

## 📋 完整命令序列 (复制粘贴版)

```bash
# 1. 清空数据
python3 manage_data.py << 'EOF'
1 2
EOF

# 2. 下载历史数据 (3.5分钟)
python3 download_full_history.py

# 3. 批量ETL处理 (2.1分钟)
python3 process_raw_data_optimized.py

# 4. 验证数据
python3 << 'EOF'
from sqlmodel import Session, create_engine, text
engine = create_engine('sqlite:///backend/database.db')
with Session(engine) as session:
    daily = session.exec(text("SELECT COUNT(*) FROM marketdatadaily")).first()[0]
    snapshot = session.exec(text("SELECT COUNT(*) FROM marketsnapshot")).first()[0]
    print(f"✅ MarketDataDaily: {daily:,} 条")
    print(f"✅ MarketSnapshot: {snapshot} 条")
EOF
```

---

## 🎉 实际测试结果

**环境**: 70个资产, 358,984条历史记录

**执行时间**:
- 清空数据: 1秒
- 下载: 3.5分钟
- ETL: 2.1分钟
- **总计**: 5.6分钟

**成功率**: 100% (70/70资产, 0失败)
