# Database Schema Documentation

本文档说明了系统使用的 SQLite 数据库中的主要表及其用途。

## 0. 数据标准 (Data Standards)

> 💡 **提示**: 
> *   关于详细的数据处理流程 (ETL)、下载策略及复权逻辑，请参阅 [数据处理工作流程](../docs/DATA_PROCESS_WORKFLOW.md)。
> *   关于 **数据源接口规范** (AkShare/yfinance 参数说明及返回字段)，请参阅 [数据源接口文档](docs/data_source_api_reference.md)。

### 典范 ID (Canonical ID)
系统中所有表的 `symbol` 字段必须严格遵守 **典范 ID** 格式。这是跨表关联和数据一致性的基石。

*   **格式**: `MARKET:TYPE:CODE`
*   **示例**:
    *   美股: `US:STOCK:AAPL`
    *   港股: `HK:STOCK:00700`
    *   A股: `CN:STOCK:600519`
    *   指数: `HK:INDEX:HSI`, `US:INDEX:SPX`
    *   ETF: `US:ETF:SPY`, `HK:ETF:02800`
    *   信托: `US:UTRUST:0P00014FO3`
    *   加密货币: `WORLD:CRYPTO:BTC-USD`

> **注意**: 任何脚本在写入 `symbol` 字段时，都必须先调用 `backend.symbol_utils.get_canonical_id` 生成标准 ID。

## 核心数据表 (Core Data Tables)

### 1. `MarketDataDaily` (日线历史表)
*   **用途**: 严格存储股票和指数的**已收盘日线 (EOD)** 历史数据。
*   **关键规则**:
    *   **不存盘中数据**: 盘中实时价格不应写入此表，应只写入 `MarketSnapshot`。
    *   **时间戳**: 必须是实际收盘日期，不允许将未来的收盘时间（如尚未收盘的今日16:00）强行标记写入。
*   **关键字段**:
    *   `symbol`: 典范ID (如 `US:STOCK:AAPL`)。
    *   `date`: 交易日期/时间。
    *   `open`, `high`, `low`, `close`: OHLC 价格数据。
    *   `volume`: 成交量。
    *   `pct_change`: 涨跌幅 (百分比)。
    *   `change`: 涨跌额。
    *   `pe`: 静态市盈率 (Static PE)。
    *   `pe_ttm`: 滚动市盈率 (TTM PE)。
    *   `dividend_yield`: 股息率。
    *   `market_cap`: 市值。
*   **场景**: 用于绘制历史 K 线图、计算历史技术指标。每日收盘后通过 ETL 任务写入。

### 2. `MarketSnapshot` (行情快照表)
*   **用途**: 存储每个资产的**最新行情状态**。这是前端 API 查询实时数据的唯一来源。
*   **特性**:
    *   **唯一性**: 每个 `(symbol, market)` 组合只有一条记录。
    *   **实时性**: 盘中实时更新 (如每分钟)，盘后由 ETL 用收盘数据校准。
    *   **字段**: 包含即时价格 `price`, 涨跌幅 `change/pct_change`, 以及估值指标 `pe/pe_ttm/dividend_yield` (通常来自日线)。
*   **场景**: App 首页列表、自选股刷新、详情页头部数据。

### 3. `RawMarketData` (原始数据表)
*   **用途**: 数据抓取的**缓冲区**。所有从外部 API (Yahoo/AkShare) 下载的 JSON 原始数据首先存入此表。
*   **关键字段**:
    *   `payload`: 原始 JSON 字符串。
    *   `period`: 数据周期 (如 `1d`, `1m`)。
    *   `processed`: ETL 处理状态标记。
*   **场景**: 故障排查、数据回溯、ETL 异步处理源头。

### 4. `Watchlist` (自选股表)
*   **用途**: 存储用户添加的自选资产列表。
*   **关键字段**:
    *   `symbol`: 典范ID (如 `US:STOCK:AAPL`, `WORLD:CRYPTO:BTC-USD`)。
    *   `name`: 资产名称 (如 "特斯拉", "Bitcoin")。
    *   `market`: 市场标识 (`US`, `CN`, `HK`, `WORLD`)。
*   **场景**: 用户界面的「自选股」列表数据源。

### 5. `StockInfo` (资产基础信息表)
*   **用途**: 存储资产的静态基础信息，用于搜索和补全。
*   **关键字段**:
    *   `symbol`: 典范ID (如 `US:ETF:SPY`)。
    *   `name`: 资产名称 (中文/英文)。
    *   `market`: 市场。
*   **场景**: 搜索框的自动完成建议，以及不在自选股中的资产信息查询。

## 辅助/历史表 (Auxiliary Tables)

### 5. `AssetAnalysisHistory` (资产分析历史表)
*   **用途**: 存储 AI 对资产进行的分析结果历史记录。
*   **关键字段**:
    *   `symbol`: 资产代码。
    *   `date`: 分析生成的日期。
    *   `summary`: AI 分析摘要。
    *   `score`: 评分。
    *   `recommendation`: 投资建议 (Buy/Sell/Hold)。

