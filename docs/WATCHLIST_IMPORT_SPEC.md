# Watchlist 导入规范

## 概述

本文档说明如何正确导入监控列表资产,确保每个资产都有正确的 Canonical ID 格式。

---

## Canonical ID 格式

### 标准格式

```
{MARKET}:{TYPE}:{TICKER}
```

**组成部分**:
- `MARKET`: 市场代码 (CN, HK, US, WORLD)
- `TYPE`: 资产类型 (INDEX, STOCK, ETF, CRYPTO)
- `TICKER`: 原始ticker符号

### 示例

| 资产 | Canonical ID | 说明 |
|------|-------------|------|
| 上证指数 | `CN:INDEX:000001` | A股指数 |
| 中国平安 | `CN:STOCK:601318` | A股股票 |
| 恒生指数 | `HK:INDEX:HSI` | 港股指数 |
| 腾讯控股 | `HK:STOCK:00700` | 港股股票 |
| 标普500 | `US:INDEX:SPX` | 美股指数 |
| 苹果公司 | `US:STOCK:AAPL` | 美股股票 |
| 比特币 | `WORLD:CRYPTO:BTC` | 加密货币 |

---

## symbols.txt 文件格式

### 文件结构

使用**注释分组**来标识资产的市场和类型:

```text
# === A股指数 (CN Indices) ===
000001
000300

# === 港股指数 (HK Indices) ===
HSI
HSTECH

# === 美股指数 (US Indices) ===
DJI
SPX

# === A股 (CN Stocks) ===
600030
601318

# === 港股 (HK Stocks) ===
00700
00005

# === 美股 (US Stocks) ===
AAPL
MSFT

# === A股 ETF (CN ETFs) ===
159662
512880

# === 港股 ETF (HK ETFs) ===
02800
03033

# === 美股 ETF (US ETFs) ===
SPY
QQQ

# === 加密货币 (Crypto) ===
BTC
```

### 注释关键词映射

| 注释关键词 | Market | Type |
|-----------|--------|------|
| `CN Indices` 或 `A股指数` | CN | INDEX |
| `HK Indices` 或 `港股指数` | HK | INDEX |
| `US Indices` 或 `美股指数` | US | INDEX |
| `CN Stocks` 或 `A股` (不含ETF) | CN | STOCK |
| `HK Stocks` 或 `港股` (不含ETF) | HK | STOCK |
| `US Stocks` 或 `美股` (不含ETF) | US | STOCK |
| `CN ETF` 或 `A股 ETF` | CN | ETF |
| `HK ETF` 或 `港股 ETF` | HK | ETF |
| `US ETF` 或 `美股 ETF` | US | ETF |
| `Crypto` 或 `加密货币` | WORLD | CRYPTO |

---

## 导入流程

### 使用 manage_data.py

```bash
python3 manage_data.py
# 选择: 4 (从 symbols.txt 导入监控列表)
```

### 导入逻辑

`manage_data.py` 的 `import_symbols()` 函数会:

1. **读取文件**: 逐行读取 `imports/symbols.txt`
2. **解析注释**: 识别注释中的关键词,推断当前分组的市场和类型
3. **构建Canonical ID**: 将 ticker 与市场、类型组合
4. **保存到数据库**: 将完整的Canonical ID保存到 `watchlist` 表

**代码示例**:
```python
# 解析注释
if 'CN Indices' in line or 'A股指数' in line:
    current_market, current_type = 'CN', 'INDEX'

# 构建Canonical ID
canonical_id = f"{current_market}:{current_type}:{ticker}"

# 保存
watchlist_item = Watchlist(
    symbol=canonical_id,      # CN:INDEX:000001
    market=current_market,    # CN
    name=ticker               # 000001
)
```

---

## 验证导入结果

### 检查Canonical ID

```bash
python3 << 'EOF'
from sqlmodel import Session, create_engine, select
from backend.models import Watchlist

engine = create_engine('sqlite:///backend/database.db')

with Session(engine) as session:
    watchlist = session.exec(select(Watchlist)).all()
    
    for item in watchlist[:5]:  # 显示前5个
        print(f"{item.symbol:35s} | Market: {item.market} | Ticker: {item.name}")
EOF
```

**预期输出**:
```
CN:INDEX:000001                     | Market: CN | Ticker: 000001
CN:INDEX:000300                     | Market: CN | Ticker: 000300
HK:INDEX:HSI                        | Market: HK | Ticker: HSI
US:STOCK:AAPL                       | Market: US | Ticker: AAPL
WORLD:CRYPTO:BTC                    | Market: WORLD | Ticker: BTC
```

### 按市场统计

```bash
python3 << 'EOF'
from sqlmodel import Session, create_engine, text

engine = create_engine('sqlite:///backend/database.db')

with Session(engine) as session:
    result = session.exec(text("""
        SELECT market, COUNT(*) as count
        FROM watchlist
        GROUP BY market
        ORDER BY market
    """))
    
    for row in result:
        print(f"{row[0]:6s}: {row[1]:3d} 个资产")
EOF
```

---

## 常见问题

### Q1: 为什么要使用Canonical ID?
**A**: 
- **唯一性**: 避免不同市场的ticker冲突 (如 `000001` 在CN和HK都存在)
- **可追溯**: 明确资产的市场和类型
- **数据源选择**: 根据市场自动选择正确的数据源 (yfinance/AkShare)

### Q2: 如果注释写错了会怎样?
**A**: 
- 该分组下的所有ticker会被归类到错误的市场/类型
- 建议导入后立即验证
- 可以重新编辑 `symbols.txt` 并重新导入

### Q3: 可以手动添加资产吗?
**A**: 
可以,但必须使用完整的Canonical ID:
```python
from backend.models import Watchlist

watchlist_item = Watchlist(
    symbol="CN:STOCK:600519",  # 完整Canonical ID
    market="CN",
    name="600519"
)
```

### Q4: 导入后如何修改?
**A**: 
1. 编辑 `imports/symbols.txt`
2. 运行 `python3 manage_data.py`
3. 选择 `3` (清除监控列表)
4. 选择 `4` (重新导入)

---

## 相关文档

- [数据处理工作流程](DATA_PROCESS_WORKFLOW.md)
- [资产管理工作流](ASSET_MANAGEMENT_WORKFLOW.md)
- [数据源分析](DATA_SOURCE_ANALYSIS.md)
