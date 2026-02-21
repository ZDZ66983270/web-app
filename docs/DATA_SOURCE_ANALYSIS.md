# 行情数据源分析报告

## 📊 查询资产的数据来源

根据代码分析,以下是 **HSTECH** 和 **CN ETF(1开头/5开头)** 的行情数据获取来源:

---

## 1️⃣ HSTECH (恒生科技指数)

### Canonical ID
```
HK:INDEX:HSTECH
```

### 数据源策略

#### 主数据源: **yfinance** (优先)
- **符号转换**: `HSTECH` → `HSTECH.HK`
- **代码位置**: 
  - [`backend/symbol_utils.py:58-59`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/symbol_utils.py#L58-L59)
  - [`backend/data_fetcher.py:155`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/data_fetcher.py#L155)

```python
# symbol_utils.py 第58-59行
if clean_code == 'HSTECH':
    return "HSTECH.HK"
```

#### 备用数据源: **AkShare** (fallback)
- **接口**: `ak.stock_hk_index_daily_sina(symbol="HSTECH")`
- **触发条件**: 当 yfinance 返回空数据或异常时
- **代码位置**: [`download_full_history.py:201-202`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/download_full_history.py#L201-L202)

```python
# download_full_history.py 第201-202行
if market == 'HK' and code == 'HSTECH':
    return fallback_index_akshare(canonical_id, market, "HSTECH", "hk_index_sina")
```

### ⚠️ 已知问题
根据代码注释(第57行),yfinance 的 `HSTECH.HK` **历史数据有限**,可能需要依赖 AkShare 补全历史数据。

---

## 2️⃣ CN ETF - 1开头 (深圳ETF)

### 示例资产
- `CN:ETF:159662` (军工ETF)
- `CN:ETF:159751` (芯片ETF)
- `CN:ETF:159851` (科创50ETF)
- `CN:ETF:159852` (创新药ETF)

### 数据源策略

#### 主数据源: **yfinance** (唯一)
- **符号转换**: `159662` → `159662.SZ`
- **转换规则**: 1开头的代码 → 添加 `.SZ` 后缀(深圳交易所)
- **代码位置**: [`backend/symbol_utils.py:92-94`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/symbol_utils.py#L92-L94)

```python
# symbol_utils.py 第92-94行
elif clean_code.startswith('1'):
    # 1xxxxx: 深圳ETF
    return f"{clean_code}.SZ"
```

#### 数据获取流程
1. **实时数据**: [`backend/data_fetcher.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/data_fetcher.py) → `_convert_to_yfinance_symbol()` → `159662.SZ`
2. **历史数据**: [`download_full_history.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/download_full_history.py) → `convert_to_yfinance_symbol()` → `159662.SZ`

### ⚠️ 注意
- **无 AkShare 备用方案**: 代码中未为 CN ETF 配置 AkShare fallback
- **完全依赖 yfinance**: 如果 yfinance 无数据,则无法获取

---

## 3️⃣ CN ETF - 5开头 (上海ETF)

### 示例资产
- `CN:ETF:512800` (银行ETF)
- `CN:ETF:512880` (证券ETF)
- `CN:ETF:513190` (纳指ETF)
- `CN:ETF:516020` (菁英ETF)

### 数据源策略

#### 主数据源: **yfinance** (唯一)
- **符号转换**: `512800` → `512800.SS`
- **转换规则**: 5开头的代码 → 添加 `.SS` 后缀(上海交易所)
- **代码位置**: [`backend/symbol_utils.py:95-97`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/symbol_utils.py#L95-L97)

```python
# symbol_utils.py 第95-97行
elif clean_code.startswith('5'):
    # 5xxxxx: 上海ETF
    return f"{clean_code}.SS"
```

#### 数据获取流程
与1开头ETF相同,完全依赖 yfinance。

### ⚠️ 注意
- **无 AkShare 备用方案**: 代码中未为 CN ETF 配置 AkShare fallback
- **完全依赖 yfinance**: 如果 yfinance 无数据,则无法获取

---

## 📋 总结对比表

| 资产类型 | Canonical ID 示例 | yfinance 符号 | AkShare 备用 | 代码位置 |
|---------|------------------|--------------|-------------|---------|
| **HSTECH** | `HK:INDEX:HSTECH` | `HSTECH.HK` | ✅ `stock_hk_index_daily_sina` | `symbol_utils.py:58` |
| **1开头 CN ETF** | `CN:ETF:159662` | `159662.SZ` | ❌ 无 | `symbol_utils.py:92` |
| **5开头 CN ETF** | `CN:ETF:512800` | `512800.SS` | ❌ 无 | `symbol_utils.py:95` |

---

## 🔍 核心代码文件

1. **符号转换逻辑**: [`backend/symbol_utils.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/symbol_utils.py)
   - `get_yahoo_symbol()` - 将 Canonical ID 转换为 yfinance 格式

2. **实时数据获取**: [`backend/data_fetcher.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/backend/data_fetcher.py)
   - `DataFetcher._fetch_from_yfinance_unified()` - 统一使用 yfinance

3. **历史数据下载**: [`download_full_history.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/download_full_history.py)
   - `download_full_history()` - 下载全量历史数据
   - `fallback_index_akshare()` - AkShare 补全(仅指数)

---

## 💡 建议

### 如果需要为 CN ETF 添加 AkShare 备用数据源:

1. **修改** [`download_full_history.py`](file:///Users/zhangzy/My%20Docs/Privates/22-AI编程/AI+风控App/web-app/download_full_history.py) 的 fallback 逻辑
2. **添加** AkShare ETF 接口(如 `ak.fund_etf_hist_em()`)
3. **更新** `fallback_index_akshare()` 函数支持 ETF 类型

### 当前风险:
- **CN ETF 完全依赖 yfinance**,如果 yfinance 数据缺失或延迟,无备用方案
- **HSTECH 有双重保障**,数据可靠性更高

---

*分析时间: 2026-01-09*  
*基于代码版本: 当前 main 分支*
