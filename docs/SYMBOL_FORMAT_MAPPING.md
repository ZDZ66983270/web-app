# Symbol格式映射关系总结

## 📋 基于项目实际代码的Symbol格式规范

### 来源文件
- `backend/symbols_config.py` - 指数映射配置
- `backend/symbol_utils.py` - Symbol转换工具函数

---

## 一、指数Symbol映射 (来自 symbols_config.py)

### 美股指数

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `^DJI` | `^DJI` | `.DJI` | 道琼斯工业平均指数 |
| `^NDX` | `^NDX` | `.NDX` | 纳斯达克100指数 |
| `^SPX` | `^GSPC` | `.INX` | 标普500指数 |

**关键发现**:
- AkShare 美股指数使用 `.` 前缀 (如 `.DJI`, `.NDX`, `.INX`)
- yfinance 使用 `^` 前缀

### 港股指数

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `HSI` | `^HSI` | `800000` | 恒生指数 |
| `HSTECH` | `HSTECH.HK` | `800700` | 恒生科技指数 |

**关键发现**:
- AkShare 港股指数使用特殊代码 (`800000`, `800700`)
- yfinance 恒生指数用 `^HSI`,恒生科技用 `HSTECH.HK`

### A股指数

| 内部Symbol | yfinance格式 | AkShare格式 | 说明 |
|-----------|-------------|------------|------|
| `000001.SS` | `000001.SS` | `sh000001` | 上证综合指数 |
| `000300` | `000300.SS` | `sh000300` | 沪深300指数 |
| `000016` | `000016.SS` | `sh000016` | 上证50指数 |
| `000905` | `000905.SS` | `sh000905` | 中证500指数 |

**关键发现**:
- AkShare A股指数使用 `sh` 前缀 + 6位代码
- **重要**: A股指数即使以 `0` 开头，在 yfinance 中也应使用 `.SS` (上海) 而非 `.SZ` (深圳)。
- **严重歧义**: `000001` 在 A 股是平安银行（个股），必须明确区分。

---

## 二、个股Symbol转换规则 (来自 symbol_utils.py)

### yfinance 格式转换 (`get_yahoo_symbol`)

#### 港股
```python
# 输入: '00700', market='HK'
# 输出: '0700.HK'

# 规则:
# 1. 去掉前导0,保留至少4位
# 2. 添加 .HK 后缀
```

**示例**:
- `00700` → `0700.HK` (腾讯)
- `09988` → `9988.HK` (阿里)
- `00005` → `0005.HK` (汇丰)

#### A股
```python
# 规则:
# 1. 6开头 → .SS (上海)
# 2. 0或3开头 (非指数) → .SZ (深圳)
# 3. 0开头且为指数 → .SS (上海) -- 特殊规则
# 4. 8或4开头 → .BJ (北京)
```

**示例**:
- `600519` → `600519.SS` (贵州茅台)
- `000858` → `000858.SZ` (五粮液)
- `300750` → `300750.SZ` (宁德时代)

#### 美股
```python
# 直接使用原symbol,无需转换
```

**示例**:
- `AAPL` → `AAPL`
- `MSFT` → `MSFT`

### Canonical ID 格式 (`get_canonical_id`)

**⚠️ 重要**: Canonical ID 是**内部存储格式**,用于数据库主键,**不是**发给数据源API的格式!

```python
# 格式: MARKET:TYPE:SYMBOL
# 用途: 数据库内部唯一标识,防止重复数据

# 港股: 标准化为5位数字
'00700', 'HK', 'STOCK' → 'HK:STOCK:00700'  # 内部存储
'700', 'HK', 'STOCK' → 'HK:STOCK:00700'    # 自动补0到5位

# A股: 标准化为6位数字  
'600519', 'CN', 'STOCK' → 'CN:STOCK:600519'  # 内部存储

# 美股: 保持原样
'AAPL', 'US', 'STOCK' → 'US:STOCK:AAPL'  # 内部存储
```

**使用流程**:
1. 从Canonical ID提取纯symbol: `HK:STOCK:00700` → `00700`
2. 根据数据源转换格式: `00700` → `0700.HK` (yfinance) 或 `hk00700` (AkShare估值)
3. 调用API获取数据

---

## 三、AkShare 个股接口格式 (基于测试验证)

### A股个股

**K线接口** (`stock_zh_a_hist`):
```python
symbol = "600519"  # 6位纯数字,无前缀后缀
```

**估值接口** (`stock_value_em`):
```python
symbol = "600519"  # 6位纯数字
```

### 港股个股

**K线接口** (`stock_hk_hist`):
```python
symbol = "00700"  # 5位数字,前补0
```

**估值接口** (`stock_hk_indicator_eniu`):
```python
symbol = "hk00700"  # 小写hk + 5位数字
```

**百度估值** (`stock_hk_valuation_baidu`):
```python
symbol = "00700"  # 5位数字,无hk前缀
```

### 美股个股

**K线接口** (`stock_us_hist`):
```python
symbol = "105.AAPL"  # 交易所代码.股票代码
# 105 = 纳斯达克/纽交所
# 106 = 其他交易所
```

---

## 四、完整对照表

### 内部存储 vs API格式对照

| 用途 | A股示例 | 港股示例 | 美股示例 |
|------|---------|---------|---------|
| **内部存储(纯symbol)** | `600519` | `00700` | `AAPL` |
| **Canonical ID(数据库主键)** | `CN:STOCK:600519` | `HK:STOCK:00700` | `US:STOCK:AAPL` |

### 数据源API格式对照

| 数据源 | A股 | 港股 | 美股 |
|--------|-----|------|------|
| **yfinance** | `600519.SS` | `0700.HK` ⚠️去前导0 | `AAPL` |
| **AkShare K线** | `600519` | `00700` | `105.AAPL` ⚠️需交易所前缀 |
| **AkShare 估值** | `600519` | `hk00700` ⚠️需hk前缀 | - |
| **Futu API** | `SH.600519` | `HK.00700` | `US.AAPL` |

### 数据流转示例

**港股数据获取流程**:
```
1. 数据库存储: HK:STOCK:00700
2. 提取symbol: 00700
3. 转换为API格式:
   - yfinance: 00700 → 0700.HK
   - AkShare K线: 00700 (不变)
   - AkShare 估值: 00700 → hk00700
   - Futu API: 00700 → HK.00700
4. 调用API获取数据
5. 存回数据库时关联: HK:STOCK:00700
```

---

## 五、关键注意事项

### 1. 港股代码位数
- **内部存储**: 5位 (`00700`)
- **yfinance**: 去前导0,至少4位 (`0700.HK`)
- **AkShare K线**: 5位 (`00700`)
- **AkShare 估值**: `hk` + 5位 (`hk00700`)
- **Futu**: `HK.` + 5位 (`HK.00700`)

### 2. A股代码位数
- 统一使用6位数字
- 根据首位数字判断交易所

### 3. 大小写敏感
- `hk00700` ≠ `HK00700` ≠ `Hk00700`
- 必须严格按照接口要求

### 4. 指数特殊映射
- 港股指数在AkShare中使用特殊代码 (`800000`, `800700`)
- 需要通过 `symbols_config.py` 进行映射

---

## 六、ETF 参数规范

### Canonical ID 格式

```python
# ETF 使用 ETF 作为 asset_type
'TLT', 'US', 'ETF' → 'US:ETF:TLT'
'159662', 'CN', 'ETF' → 'CN:ETF:159662'
'02800', 'HK', 'ETF' → 'HK:ETF:02800'
```

### 美股ETF

**内部存储**: `TLT`, `SPY`, `QQQ`, `DIA`, `IWM`等

**Canonical ID**: `US:ETF:TLT`, `US:ETF:SPY`

**数据源格式**:
| 数据源 | 格式 | 示例 |
|--------|------|------|
| yfinance | 直接使用 | `TLT`, `SPY`, `QQQ` |
| AkShare | 交易所前缀 | `105.TLT`, `105.SPY` |

**常见美股ETF**:
```python
# 指数ETF
'SPY'   # 标普500指数ETF
'QQQ'   # 纳指100ETF
'DIA'   # 道琼斯指数ETF
'IWM'   # 罗素2000指数ETF

# 债券ETF
'TLT'   # 20年期以上国债ETF
'SGOV'  # 0-3月美国国债ETF

# 行业ETF
'XLK'   # 科技行业ETF
'XLF'   # 金融行业ETF
'XLE'   # 能源指数ETF
'XLV'   # 医疗保健行业ETF
```

### A股ETF

**内部存储**: `159662`, `159751`, `159851`, `512800`等 (6位数字)

**Canonical ID**: `CN:ETF:159662`, `CN:ETF:512800`

**数据源格式**:
| 数据源 | 格式规则 | 示例 |
|--------|---------|------|
| yfinance | 根据首位数字添加后缀 | `159662.SZ`, `512800.SS` |
| AkShare | 6位数字 | `159662`, `512800` |

**A股ETF交易所映射规则** (yfinance):
| 代码前缀 | 交易所 | 后缀 | 示例 |
|---------|--------|------|------|
| **1xxxxx** | 深圳 | `.SZ` | `159662.SZ`, `159751.SZ` |
| **5xxxxx** | 上海 | `.SS` | `512800.SS`, `512880.SS` |

**常见A股ETF示例**:
```python
# 深圳ETF (1开头)
'159662'  # 航运ETF → 159662.SZ
'159751'  # 港股通科技ETF → 159751.SZ
'159851'  # 科创板50ETF → 159851.SZ
'159852'  # 科创板100ETF → 159852.SZ

# 上海ETF (5开头)
'510300'  # 沪深300ETF → 510300.SS
'512800'  # 银行ETF → 512800.SS
'512880'  # 证券ETF → 512880.SS
'513190'  # 纳指ETF → 513190.SS
'516020'  # 菜油ETF → 516020.SS
```

### 港股ETF

**内部存储**: `02800`, `03033`等 (5位数字)

**Canonical ID**: `HK:ETF:02800`

**数据源格式**:
| 数据源 | 格式 | 示例 |
|--------|------|------|
| yfinance | 去前导0 + .HK | `2800.HK`, `3033.HK` |
| AkShare | 5位数字 | `02800`, `03033` |

**港股ETF代码规律**:
- 28XX, 30XX, 31XX等

**示例**:
```python
'02800'  # 盈富基金(追踪恒生指数)
'03033'  # 南方A50ETF
'03110'  # 恒生科技ETF
```

> [!NOTE]
> **HSTECH 特殊说明**: 
> 恒生科技指数在 yfinance 中的符号 `HSTECH.HK` 不支持长周期历史数据 (`period='max'`)。
> 因此在全量下载时，必须使用 AkShare 的 `stock_hk_index_daily_sina(symbol='HSTECH')` 作为备份源。

---

## 七、指数 (Index) 参数规范

### Canonical ID 格式

```python
# 指数使用 INDEX 作为 asset_type
'^DJI', 'US', 'INDEX' → 'US:INDEX:^DJI'
'HSI', 'HK', 'INDEX' → 'HK:INDEX:HSI'
'000001.SS', 'CN', 'INDEX' → 'CN:INDEX:000001.SS'
```

### 美股指数

**内部存储**: `^DJI`, `^NDX`, `^SPX`

**Canonical ID**: `US:INDEX:^DJI`, `US:INDEX:^NDX`, `US:INDEX:^SPX`

**数据源映射** (来自 `symbols_config.py`):

| 内部Symbol | yfinance | AkShare | 说明 |
|-----------|----------|---------|------|
| `^DJI` | `^DJI` | `.DJI` | 道琼斯工业指数 |
| `^NDX` | `^NDX` | `.NDX` | 纳斯达克100指数 |
| `^SPX` | `^GSPC` | `.INX` | 标普500指数 |

**⚠️ 注意**:
- yfinance 使用 `^` 前缀
- AkShare 使用 `.` 前缀
- `^SPX` 在 yfinance 中是 `^GSPC`

### 港股指数

**内部存储**: `HSI`, `HSTECH`

**Canonical ID**: `HK:INDEX:HSI`, `HK:INDEX:HSTECH`

**数据源映射**:

| 内部Symbol | yfinance | AkShare | 说明 |
|-----------|----------|---------|------|
| `HSI` | `^HSI` | `800000` | 恒生指数 |
| `HSTECH` | `HSTECH.HK` | `800700` | 恒生科技指数 |

**⚠️ 注意**:
- AkShare 港股指数使用特殊代码 (`800000`, `800700`)
- 需要通过 `symbols_config.py` 的 `get_akshare_symbol()` 函数映射

### A股指数

**内部存储**: `000001.SS`

**Canonical ID**: `CN:INDEX:000001.SS`

**数据源映射**:

| 内部Symbol | yfinance | AkShare | 说明 |
|-----------|----------|---------|------|
| `000001.SS` | `000001.SS` | `sh000001` | 上证综合指数 |

**⚠️ 重要**:
- `000001` 是平安银行(股票)
- `sh000001` 才是上证指数
- 必须使用 `sh` 前缀区分

---

## 八、完整 asset_type 对照表

| asset_type | 用途 | Canonical ID示例 | 说明 |
|-----------|------|-----------------|------|
| `STOCK` | 个股 | `US:STOCK:AAPL` | 普通股票 |
| `ETF` | 交易所交易基金 | `US:ETF:SPY` | ETF基金 |
| `INDEX` | 指数 | `US:INDEX:^DJI` | 市场指数 |

### 识别规则

**美股**:
```python
# 指数: 以 ^ 开头
if symbol.startswith('^'):
    asset_type = 'INDEX'
# ETF: 已知ETF列表
elif symbol in ['SPY', 'QQQ', 'TLT', 'DIA', ...]:
    asset_type = 'ETF'
# 其他: 股票
else:
    asset_type = 'STOCK'
```

**A股**:
```python
# 指数: sh/sz 前缀或特定代码
if symbol.startswith('sh') or symbol.startswith('sz'):
    asset_type = 'INDEX'
# ETF: 特定代码段
elif symbol.startswith(('159', '510', '512', '513', '515', '516', '517', '588')):
    asset_type = 'ETF'
# 其他: 股票
else:
    asset_type = 'STOCK'
```

**港股**:
```python
# 指数: 已知指数代码
if symbol in ['HSI', 'HSTECH']:
    asset_type = 'INDEX'
# ETF: 28XX, 30XX, 31XX等
elif symbol.startswith(('28', '30', '31')):
    asset_type = 'ETF'
# 其他: 股票
else:
    asset_type = 'STOCK'
```

---

## 九、数据获取完整示例

### 示例1: 美股ETF (SPY)

```python
# 1. 内部存储
symbol = "SPY"
market = "US"
asset_type = "ETF"

# 2. 生成 Canonical ID
canonical_id = f"{market}:{asset_type}:{symbol}"  # US:ETF:SPY

# 3. 调用 yfinance
import yfinance as yf
ticker = yf.Ticker("SPY")  # 直接使用
df = ticker.history(period="1y")

# 4. 调用 AkShare
import akshare as ak
df = ak.stock_us_hist(symbol="105.SPY")  # 需要交易所前缀
```

### 示例2: 港股指数 (HSI)

```python
# 1. 内部存储
symbol = "HSI"
market = "HK"
asset_type = "INDEX"

# 2. 生成 Canonical ID
canonical_id = "HK:INDEX:HSI"

# 3. 调用 yfinance
from backend.symbols_config import get_yfinance_symbol
yf_symbol = get_yfinance_symbol("HSI")  # 返回 "^HSI"
ticker = yf.Ticker("^HSI")

# 4. 调用 AkShare
from backend.symbols_config import get_akshare_symbol
ak_symbol = get_akshare_symbol("HSI")  # 返回 "800000"
df = ak.stock_hk_hist(symbol="800000")
```

### 示例3: A股ETF (159662)

```python
# 1. 内部存储
symbol = "159662"
market = "CN"
asset_type = "ETF"

# 2. 生成 Canonical ID
canonical_id = "CN:ETF:159662"

# 3. 调用 yfinance
ticker = yf.Ticker("159662.SZ")  # 深圳ETF用.SZ

# 4. 调用 AkShare
df = ak.stock_zh_a_hist(symbol="159662")  # 直接使用6位代码
```

---

**文档版本**: v1.2  
**最后更新**: 2026-01-09  
**更新内容**: 修正A股ETF交易所映射规则（1开头→深圳，5开头→上海）  
**数据来源**: 项目实际代码 + 测试验证
