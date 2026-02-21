# 数据处理工作流程

## 概述

本文档描述了股票市场数据从下载到展示的完整处理流程,确保数据的准确性、一致性和可追溯性。

---

## Canonical ID 规范

### 格式定义

所有资产必须使用 **Canonical ID** 格式:

```
{MARKET}:{TYPE}:{TICKER}
```

**示例**:
- `CN:INDEX:000001` - 上证指数
- `HK:STOCK:00700` - 腾讯控股
- `US:STOCK:AAPL` - 苹果公司
- `WORLD:CRYPTO:BTC` - 比特币

### 导入监控列表

使用 `manage_data.py` 从 `imports/symbols.txt` 导入:

```bash
python3 manage_data.py
# 选择: 4 (从 symbols.txt 导入监控列表)
```

**symbols.txt 格式**:
```text
# === A股指数 (CN Indices) ===
000001
000300

# === 美股 (US Stocks) ===
AAPL
MSFT
```

导入工具会自动:
1. 解析注释分组
2. 推断市场和类型
3. 构建完整的Canonical ID

详细说明见: [Watchlist导入规范](WATCHLIST_IMPORT_SPEC.md)

---

## 数据流架构

### ⚠️ 重要原则: 下载与ETL完全分离

```
┌─────────────────┐
│  数据源         │
│  - yfinance     │
│  - AkShare      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1: 数据下载 (Download Only)                      │
│  脚本: download_full_history.py                         │
│  - 只下载,不处理                                        │
│  - 快速完成,不阻塞                                      │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  RawMarketData 表 (原始数据存储)                        │
│  - processed = false                                    │
│  - payload: JSON serialized DataFrame                   │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2: ETL 批量处理 (Batch Processing)               │
│  脚本: process_raw_data.py                              │
│  - 批量处理所有 processed=false 的记录                  │
│  - 可并行优化                                           │
└────────┬────────────────────────────────────────────────┘
         │
         ├─────────────────────────────┐
         ▼                             ▼
┌──────────────────────┐    ┌──────────────────────┐
│  MarketDataDaily     │    │  MarketSnapshot      │
│  - 历史日线数据      │    │  - 最新快照          │
│  - processed = true  │    │                      │
└──────────────────────┘    └──────────────────────┘
```

### 优势

1. **下载快速**: 不被ETL阻塞,70个资产下载完成只需3.5分钟 (vs 原6-12小时)
2. **ETL高效**: 组合优化实现1.8秒/资产 (vs 原2-3分钟/资产)
3. **可重新处理**: RAW数据保留,ETL逻辑变更后可重跑
4. **错误隔离**: 下载失败不影响已下载数据,ETL失败可单独重试
5. **进度清晰**: 下载和处理进度分别显示
6. **总时间**: 5.6分钟完成全部流程 (vs 原2.3-3.5小时) - **25-40倍提速**

---

## 核心流程详解

### 流程 1: 历史数据下载 (只下载)

**脚本**: `download_full_history.py`

```python
# 1. 从数据源获取历史数据
df = yf.Ticker(symbol).history(period="max", auto_adjust=True)

# 2. 保存到 RawMarketData (不触发ETL)
payload = df.to_json(orient='records', date_format='iso')
raw_record = RawMarketData(
    source="yfinance",
    symbol=canonical_id,
    market=market,
    period="1d",
    payload=payload,
    processed=False  # 标记为未处理
)
session.add(raw_record)
session.commit()

# 3. 继续下一个资产 (不等待ETL)
```

**数据流**:
```
yfinance API → DataFrame → JSON → RawMarketData (processed=false)
```

**特点**:
- ✅ 快速: 每个资产1-2秒
- ✅ 轻量: 只做序列化,无计算
- ✅ 可恢复: 中断后可继续

---

### 流程 2: ETL 批量处理

**脚本**: `process_raw_data.py`

```python
# 1. 查询所有未处理记录
unprocessed = session.exec(
    select(RawMarketData).where(RawMarketData.processed == False)
).all()

# 2. 批量处理
for raw_record in unprocessed:
    ETLService.process_raw_data(raw_record.id)
    # - 时间戳标准化
    # - 涨跌幅计算
    # - 保存到 Daily/Snapshot
    # - 标记 processed=true
```

**数据流**:
```
RawMarketData → ETL → MarketDataDaily + MarketSnapshot
```

**特点**:
- ✅ 批量: 一次处理所有未处理记录
- ✅ 可重试: 失败的可单独重跑
- ✅ 可优化: 可以并行处理

---

## 完整操作流程

### 方案 A: 全新下载 (推荐)

```bash
# Step 1: 清空数据
python3 manage_data.py
# 选择: 1 2 (清空行情和财务)

# Step 2: 下载到 RAW (快速,3.5分钟)
python3 download_full_history.py

# Step 3: 超级优化 ETL 处理 (2.1分钟)
python3 process_raw_data_optimized.py

# Step 4: 获取估值数据
python3 fetch_valuation_history.py

# 总时间: ~6分钟 (vs 原2.3小时)
```

### 方案 B: 增量更新

```bash
# 下载最近5天数据到 RAW
python3 daily_incremental_update.py

# 处理新增的 RAW 数据
python3 process_raw_data.py
```

### 方案 C: 重新处理 ETL

```bash
# 场景: ETL逻辑修改,需要重新处理

# 1. 标记所有 RAW 为未处理
python3 << 'EOF'
from sqlmodel import Session, create_engine, text
engine = create_engine('sqlite:///backend/database.db')
with Session(engine) as session:
    session.exec(text("UPDATE rawmarketdata SET processed = 0"))
    session.commit()
    print("✅ 已重置所有 RAW 记录")
EOF

# 2. 清空 Daily 和 Snapshot
python3 manage_data.py
# 选择: 1 (只清空行情数据)

# 3. 重新 ETL 处理
python3 process_raw_data_optimized.py  # 使用优化版本
```

---

## ⚡ 性能优化

### 优化策略

#### 1. 架构优化: 下载与ETL分离

**优化前** (边下载边处理):
```python
for asset in watchlist:
    df = download(asset)        # 2秒
    save_to_raw(df)             # 0.1秒
    ETLService.process(...)     # 2-3分钟 ⏰ 阻塞!
    # 总计: 2-3分钟/资产 × 70 = 2.3-3.5小时
```

**优化后** (完全分离):
```python
# Phase 1: 快速下载
for asset in watchlist:
    df = download(asset)        # 2秒
    save_to_raw(df)             # 0.1秒
    # 总计: 2秒/资产 × 70 = 2-3分钟

# Phase 2: 批量ETL (优化版)
for raw in RawMarketData:
    process_optimized(raw.id)   # 1.8秒/资产
    # 总计: 1.8秒/资产 × 70 = 2.1分钟
```

#### 2. ETL性能优化: 组合优化方案

**脚本**: `process_raw_data_optimized.py`

**优化策略**:
1. **预加载已有数据** - 一次查询获取所有历史收盘价,消除N次数据库查询
2. **批量INSERT OR REPLACE** - 使用SQLite原生UPSERT,消除存在性检查
3. **每资产一次提交** - 减少commit次数

**代码对比**:

❌ **优化前** (每条记录):
```python
for row in df.iterrows():
    # 查询前收盘价 (N次SELECT)
    prev_close = session.exec(select(...)).first()
    
    # 检查是否存在 (N次SELECT)
    existing = session.exec(select(...)).first()
    
    # 插入或更新
    if existing:
        session.add(existing)
    else:
        session.add(new_record)
    
    # 每条提交 (N次COMMIT)
    session.commit()
```

✅ **优化后** (批量处理):
```python
# 1. 预加载所有已有数据 (1次SELECT)
existing_data = session.exec(
    select(MarketDataDaily).where(...)
).all()
prev_close_map = {r.timestamp: r.close for r in existing_data}

# 2. 批量准备数据
records = []
for row in df.iterrows():
    prev_close = prev_close_map.get(prev_timestamp)
    records.append({...})

# 3. 批量UPSERT (N次INSERT OR REPLACE,但无SELECT)
for record in records:
    session.exec(text("INSERT OR REPLACE ...").bindparams(**record))

# 4. 一次提交 (1次COMMIT)
session.commit()
```

### 性能对比

| 阶段 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **下载70个资产** | 6-12小时 | **3.5分钟** | 100倍+ |
| **ETL处理** | 2-3分钟/资产 | **1.8秒/资产** | 50-100倍 |
| **总时间** | 2.3-3.5小时 | **5.6分钟** | **25-40倍** |

### 实际测试结果

**测试环境**: 70个资产, 358,984条历史记录

**下载阶段**:
- 时间: 3.5分钟
- 速度: 3秒/资产
- 结果: 70/70成功, 0失败

**ETL阶段**:
- 时间: 2.1分钟
- 速度: 1.8秒/资产
- 结果: 70/70成功, 0失败

**数据分布**:
- CN市场: 57,032条
- HK市场: 59,124条
- US市场: 238,695条
- WORLD: 4,133条

---

## 推荐操作流程 (优化版)

### 全新下载 (总时间: ~6分钟)

```bash
# Step 1: 清空数据
python3 manage_data.py
# 选择: 1 2 (清空行情和财务)

# Step 2: 下载到 RAW (3.5分钟)
python3 download_full_history.py

# Step 3: 超级优化 ETL (2.1分钟)
python3 process_raw_data_optimized.py

# Step 4: 获取估值数据
python3 fetch_valuation_history.py
```

### 增量更新

```bash
# 下载最近数据
python3 daily_incremental_update.py

# 处理新增RAW (如有需要)
python3 process_raw_data_optimized.py
```

---

### 1. RawMarketData (原始数据表)

**作用**: 存储未处理的原始数据,支持数据追溯和重新处理

```python
class RawMarketData(SQLModel, table=True):
    id: int                    # 主键
    source: str                # 数据源: "yfinance", "akshare"
    symbol: str                # Canonical ID: "CN:STOCK:600030"
    market: str                # 市场: "CN", "HK", "US", "WORLD"
    period: str                # 周期: "1d", "1m"
    fetch_time: datetime       # 获取时间
    payload: str               # JSON序列化的DataFrame
    processed: bool            # 是否已处理
    error_log: Optional[str]   # 错误日志
```

**数据示例**:
```json
{
  "id": 1,
  "source": "yfinance",
  "symbol": "US:STOCK:AAPL",
  "market": "US",
  "period": "1d",
  "payload": "[{\"Date\":\"2024-01-01\",\"Open\":185.5,...}]",
  "processed": true
}
```

### 2. MarketDataDaily (历史日线表)

**作用**: 存储每日收盘数据,用于历史分析和回测

```python
class MarketDataDaily(SQLModel, table=True):
    symbol: str                # Canonical ID
    market: str                # 市场
    timestamp: str             # 时间戳 (收盘时间)
    open: float                # 开盘价
    high: float                # 最高价
    low: float                 # 最低价
    close: float               # 收盘价
    volume: int                # 成交量
    turnover: Optional[float]  # 成交额
    change: float              # 涨跌额
    pct_change: float          # 涨跌幅 (%)
    prev_close: float          # 前收盘价
    pe: Optional[float]        # 市盈率
    pb: Optional[float]        # 市净率
    dividend_yield: Optional[float]  # 股息率
```

### 3. MarketSnapshot (最新快照表)

**作用**: 存储每个资产的最新行情,用于前端展示

```python
class MarketSnapshot(SQLModel, table=True):
    symbol: str                # Canonical ID
    market: str                # 市场
    price: float               # 最新价
    open: float                # 今开
    high: float                # 最高
    low: float                 # 最低
    volume: int                # 成交量
    change: float              # 涨跌额
    pct_change: float          # 涨跌幅
    prev_close: float          # 昨收
    timestamp: str             # 时间戳
    data_source: str           # 数据来源: "etl", "intraday"
```

---

## 核心流程详解

### 流程 1: 历史数据下载

**脚本**: `download_full_history.py`

```python
# 1. 从数据源获取历史数据
df = yf.Ticker(symbol).history(period="max", auto_adjust=True)

# 2. 保存到 RawMarketData
payload = df.to_json(orient='records', date_format='iso')
raw_record = RawMarketData(
    source="yfinance",
    symbol=canonical_id,
    market=market,
    period="1d",
    payload=payload,
    processed=False
)
session.add(raw_record)
session.commit()

# 3. 触发 ETL 处理
ETLService.process_raw_data(raw_record.id)
```

**数据流**:
```
yfinance API → DataFrame → RawMarketData → ETL → MarketDataDaily
```

### 流程 2: 增量更新

**脚本**: `daily_incremental_update.py`

```python
# 1. 获取最近5天数据
df = ticker.history(period="5d", interval="1d", auto_adjust=True)

# 2. 保存到 RawMarketData
# (同上)

# 3. ETL 处理
# - 去重: 已存在的日期会被更新
# - 盘中过滤: 市场开盘时不保存当天数据
```

**数据流**:
```
yfinance API → RawMarketData → ETL → MarketDataDaily (更新) + MarketSnapshot
```

### 流程 3: ETL 处理

**服务**: `ETLService.process_raw_data()`

#### 3.1 数据提取 (Extract)
```python
# 从 RawMarketData 读取
raw_record = session.get(RawMarketData, raw_id)
payload_data = json.loads(raw_record.payload)
df = pd.DataFrame(payload_data)
```

#### 3.2 数据转换 (Transform)

**时间戳标准化**:
```python
# 规则: 00:00:00 → 市场收盘时间
if orig_time.hour == 0 and orig_time.minute == 0:
    if market == "CN":
        target_time = orig_time.replace(hour=15, minute=0)  # 15:00
    elif market == "HK":
        target_time = orig_time.replace(hour=16, minute=0)  # 16:00
    elif market == "US":
        target_time = orig_time.replace(hour=16, minute=0)  # 16:00 EST
```

**涨跌幅计算**:
```python
# 从数据库获取前一日收盘价
prev_record = session.exec(
    select(MarketDataDaily)
    .where(MarketDataDaily.symbol == symbol)
    .where(MarketDataDaily.timestamp < current_date)
    .order_by(MarketDataDaily.timestamp.desc())
).first()

prev_close = prev_record.close if prev_record else None
change = close - prev_close
pct_change = (change / prev_close) * 100
```

**盘中数据过滤**:
```python
# 只在市场开盘时过滤当天数据
market_today = get_market_time(market).date()
market_open = is_market_open(market)

if data_date == market_today and market_open:
    # 跳过当天数据 (盘中未定型)
    continue
```

#### 3.3 数据加载 (Load)

**保存到 MarketDataDaily**:
```python
# Upsert 逻辑
existing = session.exec(
    select(MarketDataDaily).where(
        MarketDataDaily.symbol == symbol,
        MarketDataDaily.timestamp == timestamp
    )
).first()

if existing:
    # 更新
    existing.close = close
    existing.change = change
    existing.pct_change = pct_change
else:
    # 插入
    new_record = MarketDataDaily(...)
    session.add(new_record)
```

**更新 MarketSnapshot**:
```python
# 从 MarketDataDaily 读取最新记录
latest_daily = session.exec(
    select(MarketDataDaily)
    .where(MarketDataDaily.symbol == symbol)
    .order_by(MarketDataDaily.timestamp.desc())
).first()

# 更新快照
snapshot = MarketSnapshot(
    symbol=symbol,
    price=latest_daily.close,
    change=latest_daily.change,
    pct_change=latest_daily.pct_change,
    ...
)
```

---

## 数据复权说明

### 复权方式

| 市场 | 数据源 | 复权方式 | 参数 |
|------|--------|---------|------|
| **US** | yfinance | 自动复权 | `auto_adjust=True` |
| **CN** | AkShare | 前复权 (QFQ) | `adjust="qfq"` |
| **HK** | AkShare | 前复权 (QFQ) | `adjust="qfq"` |

### 复权影响

**前复权 (QFQ)**:
- 保持最新价格不变
- 向前调整历史价格
- 适合技术分析

**注意**: 由于使用复权价,**不能直接用派息金额/当前价格计算股息率**,应使用数据源提供的股息率。

---

## 估值数据获取

### US 股票
```python
# yfinance ticker.info
ticker = yf.Ticker(symbol)
pe = ticker.info.get('trailingPE')
pb = ticker.info.get('priceToBook')
dividend_yield = ticker.info.get('dividendYield')  # 0.4 = 0.4%
```

### CN 股票
```python
# AkShare - 同花顺分红情况
df = ak.stock_fhps_detail_ths(symbol="600009")
dividend_yield = df['税前分红率'].iloc[-1]  # 最新一期
```

### HK 股票
```python
# AkShare - 财务分析指标
df = ak.stock_financial_hk_analysis_indicator_em(symbol="00700")
# 注: 当前接口无股息TTM字段,需进一步确认
```

---

## 运维操作

### 清空数据重新下载
```bash
# 1. 清空行情表
python3 clear_market_data.py

# 2. 重新下载
python3 download_full_history.py

# 3. 验证数据
python3 -c "
from sqlmodel import Session, create_engine, text
engine = create_engine('sqlite:///backend/database.db')
with Session(engine) as session:
    result = session.exec(text('SELECT COUNT(*) FROM marketdatadaily'))
    print(f'历史数据: {result.first()[0]:,} 条')
    result = session.exec(text('SELECT COUNT(*) FROM marketsnapshot'))
    print(f'快照数据: {result.first()[0]:,} 条')
"
```

### 重新处理 ETL
```bash
# 重新处理所有未处理的原始数据
python3 process_unprocessed_etl.py

# 或重新处理所有数据 (包括已处理)
python3 reprocess_etl.py
```

### 数据质量检查
```bash
# 检查成交量
python3 -c "
from sqlmodel import Session, create_engine, select
from backend.models import MarketSnapshot
engine = create_engine('sqlite:///backend/database.db')
with Session(engine) as session:
    snapshots = session.exec(select(MarketSnapshot)).all()
    zero_vol = sum(1 for s in snapshots if not s.volume or s.volume == 0)
    print(f'总资产: {len(snapshots)}')
    print(f'零成交量: {zero_vol}')
    print(f'成功率: {(len(snapshots)-zero_vol)/len(snapshots)*100:.1f}%')
"
```

---

## 常见问题

### Q1: 为什么要有 RawMarketData 表?
**A**: 
- 数据可追溯: 保留原始下载数据
- 支持重新处理: ETL 逻辑变更后可重新处理
- 错误隔离: ETL 失败不影响原始数据

### Q2: 盘中数据如何处理?
**A**: 
- 盘中: 更新 `MarketSnapshot`,不写入 `MarketDataDaily`
- 盘后: 同时更新 `MarketSnapshot` 和 `MarketDataDaily`

### Q3: 如何确保数据不重复?
**A**: 
- `MarketDataDaily` 使用 `(symbol, market, timestamp)` 唯一约束
- ETL 使用 Upsert 逻辑 (存在则更新,不存在则插入)

### Q4: 为什么指数没有成交量?
**A**: 
- 指数本身不可交易,无成交量
- 只有指数ETF有成交量
- 例: HSI (指数) 无成交量, 02800 (盈富基金) 有成交量

---

## 相关文档

- [Watchlist导入规范](WATCHLIST_IMPORT_SPEC.md) - **新增**
- [数据源分析](DATA_SOURCE_ANALYSIS.md)
- [资产管理工作流](ASSET_MANAGEMENT_WORKFLOW.md)
- [US股票PE/PB说明](US_STOCK_PE_PB_EXPLANATION.md)
- [AkShare股息率分析](AKSHARE_DIVIDEND_YIELD_ANALYSIS.md)
