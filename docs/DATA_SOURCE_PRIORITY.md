# 三大市场数据源优先级对应关系表

## 📊 数据源优先级矩阵

| 市场 | 资产类型 | 首选数据源 | 备选数据源 | 说明 |
|:---|:---|:---|:---|:---|
| **CN（中国A股）** | 指数 (INDEX) | ✅ **AkShare** | ⚠️ yfinance | 部分指数（000016/000905）在 yfinance 无历史数据 |
| | 个股 (STOCK) | ✅ **AkShare** | yfinance | AkShare 数据更准确，包含复权信息 |
| | ETF | ✅ **AkShare** | yfinance | 使用 `fund_etf_hist_em` 接口 |
| **HK（香港）** | 指数 (INDEX) | ✅ **yfinance** | AkShare | yfinance 数据更完整，更新更及时 |
| | 个股 (STOCK) | ✅ **yfinance** | AkShare | yfinance 数据完整性较好 |
| | ETF | ✅ **yfinance** | AkShare | 港股 ETF 在 yfinance 上数据较全 |
| **US（美国）** | 指数 (INDEX) | ✅ **yfinance** | - | yfinance 是美股指数的标准数据源 |
| | 个股 (STOCK) | ✅ **yfinance** | - | yfinance 覆盖全面，数据质量高 |
| | ETF | ✅ **yfinance** | - | yfinance 是美股 ETF 的最佳数据源 |

---

## 🔍 详细说明

### CN 市场（中国A股）

#### 指数 (INDEX)
- **首选：AkShare**
  - 接口：`ak.stock_zh_index_daily(symbol="sh000001")`
  - 符号格式：`sh000001`, `sh000300`, `sh000016`, `sh000905`
  - 优势：完整的历史数据，数据质量高
  - **关键**：000016（上证50）和 000905（中证500）**仅在 AkShare 可用**

- **备选：yfinance**
  - 符号格式：`000001.SS`, `000300.SS`
  - 限制：部分指数不支持 `period='max'`，仅能获取近期数据

#### 个股 (STOCK)
- **首选：AkShare**
  - 接口：`ak.stock_zh_a_hist(symbol="600030", adjust="hfq")`
  - 符号格式：`600030`, `601998`（6位数字）
  - 优势：提供后复权数据，适合长期分析

- **备选：yfinance**
  - 符号格式：`600030.SS`, `601998.SH`
  - 可用性：基本可用，但复权处理可能不同

#### ETF
- **首选：AkShare**
  - 接口：`ak.fund_etf_hist_em(symbol="512800", adjust="hfq")`
  - 符号格式：`512800`, `159662`（6位数字）
  - 优势：专门的 ETF 接口，数据准确

---

### HK 市场（香港）

#### 指数 (INDEX)
- **首选：yfinance**
  - 符号格式：`^HSI`, `^HSCE`, `^HSCC`, `HSTECH.HK`
  - 注意：需要 `^` 前缀（除 HSTECH 外）
  - 优势：数据更完整，更新更及时，历史深度足够

- **备选：AkShare**
  - 接口：`ak.stock_hk_index_daily_sina(symbol="HSI")`
  - 符号格式：`HSI`, `HSTECH`, `0HSCC`, `0HSCE`
  - 可用性：作为 yfinance 的补充数据源

#### 个股 (STOCK)
- **首选：yfinance**
  - 符号格式：`00700.HK`, `09988.HK`（5位数字 + .HK）
  - 优势：数据完整，包含分红、拆股信息

- **备选：AkShare**
  - 可用性：有限，主要用于指数

#### ETF
- **首选：yfinance**
  - 符号格式：`02800.HK`, `03033.HK`
  - 优势：数据质量好，历史深度足够

---

### US 市场（美国）

#### 指数 (INDEX)
- **首选：yfinance**
  - 符号格式：`^DJI`, `^NDX`, `^GSPC`（标普500）
  - 注意：需要 `^` 前缀
  - 优势：Yahoo Finance 是美股指数的权威数据源

#### 个股 (STOCK)
- **首选：yfinance**
  - 符号格式：`AAPL`, `TSLA`, `MSFT`
  - 优势：覆盖全面，包含完整的财务数据和公司行动

#### ETF
- **首选：yfinance**
  - 符号格式：`SPY`, `QQQ`, `TLT`, `DIA`
  - 优势：数据最全面，包括成交量、期权等信息

---

## 🛠️ 实施建议

### 当前 `download_full_history.py` 的处理顺序

1. **CN ETF**：优先 AkShare ✅
2. **HK INDEX**：优先 yfinance，AkShare 作为 fallback ✅
3. **CN INDEX**：❌ **缺失**，需要添加优先 AkShare 逻辑
4. **其他资产**：默认 yfinance

### 需要修复的部分

```python
# 需要在 download_full_history.py 中添加：
if market == 'CN' and ':INDEX:' in canonical_id:
    # 优先使用 AkShare
    try:
        df = ak.stock_zh_index_daily(symbol=akshare_symbol)
        # ... 处理逻辑
    except:
        # fallback to yfinance
        pass
```

---

## 📌 关键要点

1. **CN 指数必须用 AkShare**：000016 和 000905 在 yfinance 上无历史数据
2. **HK 指数优先 yfinance**：数据更完整，更新更及时，AkShare 作为备选
3. **US 市场全部用 yfinance**：这是最可靠的美股数据源
4. **符号格式要注意**：
   - HK/US 指数需要 `^` 前缀（如 `^HSI`, `^DJI`）
   - CN 指数在 yfinance 需要 `.SS` 后缀（如 `000001.SS`）
   - HK 个股/ETF 需要 `.HK` 后缀（如 `00700.HK`）

---

> [!NOTE]
> 此表格应作为 `download_full_history.py` 逻辑设计的参考依据。
