# 系统设计与重构指南

**版本**: 1.0  
**日期**: 2025-12-20  
**状态**: 用于重构的DRAFT草稿

## 1. 系统概述

本应用是一个基于 React/Electron 前端和 FastAPI (Python) 后端的**市场风控与价值评估系统**。

### 1.1 前端架构 (`src/`)
*   **核心视图**:
    *   `MarketView`: 市场行情总览，支持多市场切换与排序。
    *   `StockDetailView`: 个股详情，含 K线图、基本面数据及 AI 分析结果。
    *   `FundDetailView`: 基金详情，含净值走势与持仓分析。
*   **组件体系**:
    *   `AppLayout`: 响应式布局容器。
    *   `ChartSeriesViewer`: 基于 ECharts 的多维数据可视化组件。
*   **状态管理**: 基于 React Context + Hooks 的轻量级状态管理。

### 1.2 后端架构 (`backend/`)

*   **前端**: React + Vite + Electron (支持 PWA 及原生 App 打包)
*   **后端**: Python FastAPI (异步架构)
*   **数据库**: SQLite (通过 SQLModel/SQLAlchemy ORM 管理)
*   **数据源 (重构核心策略)**: 
    *   🌟 **主源 (Primary)**: `yfinance` (覆盖 US/HK/CN 全市场，统一接口规范)
    *   🛡️ **备源 (Backup)**: `AkShare` (仅在 Yahoo 服务不可用时作为灾备)

> **架构决策 (2025-12-21)**: 用户已确认可接受 A股/港股 约15分钟的行情延迟。系统将全面转向以 `yfinance` 为核心的单管道架构，极大幅度降低代码复杂度。

---

## 2. 系统基础设施 (System Infrastructure)

本次深度代码审查揭示了支撑应用运行的关键基础设施模块：

### 2.1 日志系统 (`backend/logger_config.py`)
*   **架构**: 集中式日志管理，支持多Handler（文件轮转 + 控制台）。
*   **功能**: 自动捕获所有模块日志，支持按模块/级别过滤读取。
*   **现状**: 每日产生大量日志，需优化轮转策略以防止磁盘占用过大。

### 2.2 速率限制器 (`backend/rate_limiter.py`)
*   **机制**: 双层令牌桶算法（Token Bucket）。
    *   **Symbol级**: 同一标的请求间隔保护（默认 10秒）。
    *   **Source级**: 单一数据源全局频次限制（每分钟请求上限）。
*   **作用**: 防止因高频请求导致 IP 被数据源封禁。

### 2.3 市场日历 (`backend/market_schedule.py`)
*   **逻辑**: 包含 CN/HK/US 三地市场的完整交易时间定义（含时区处理）。
*   **状态机**: 提供 `OPEN` / `CLOSED` / `PRE_MARKET` / `POST_MARKET` 状态判断。
*   **改进点**: 目前硬编码了交易时间，未来应引入 API 获取假期日历。

### 2.4 实时消息推送 (`backend/websocket_manager.py`)
*   **协议**: WebSocket。
*   **功能**: `ConnectionManager` 维护客户端连接，支持广播市场数据更新。
*   **数据流**: 后端数据变更 -> `broadcast_market_update` -> 前端实时渲染。

---

## 3. 当前架构 (Current Architecture)

### 2.1 数据获取 (混合模式)

由于近期的修复工作，系统目前并行运行着两套数据获取机制：

1.  **旧版复杂管道 (`backend/data_fetcher.py` 中的 `DataFetcher`)**:
    *   **逻辑**: 包含智能回退、代理切换和多源路由的复杂异步调用链。
    *   **触发方式**: `/api/force-refresh` 或内部 APScheduler。
    *   **问题**: 复杂度极高，难以调试，`period` 参数经常被内部逻辑覆盖，容易导致不必要的全量历史数据下载。

2.  **新版极简管道 (`daily_incremental_update.py`)**:
    *   **逻辑**: 简单、线性的脚本，为每个市场配置专用的适配器。
    *   **触发方式**: 外部 LaunchAgent (Cron) 或 `/api/trigger-update`。
    *   **特性**: 精确获取最近 5 天数据，保存到 `RawMarketData` -> 触发 ETL。 **(推荐的标准方案)**

### 2.2 数据验证与 ETL

*   **原始层 (Raw Layer)**: `RawMarketData` 表存储来自 API 的原始 JSON payload。
*   **ETL 服务**: `backend/etl_service.py` (及 `run_etl.py`) 将原始数据处理为结构化数据。
*   **结构化层 (Structured Layer)**: 
    *   `MarketDataDaily`: 历史日线 OHLCV 数据。
    *   `MarketSnapshot`: 最新市场状态（价格、涨跌幅、市盈率/市净率）。

### 2.3 调度系统

*   **内部调度**: `backend/jobs.py` 中的 `APScheduler` (已弃用/对于重数据任务不可靠)。
*   **外部调度**: macOS LaunchAgent 运行 `daily_incremental_update.py` (健壮可靠)。

---

### 2.5 数据标准化与映射 (Data Standardization)

得益于 **"yfinance First"** 策略，数据标准化工作变得异常简单。系统直接采用 yfinance 的 DataFrame 结构作为内部标准。

#### 统一字段规范 (Unified Schema)

所有市场 (US/CN/HK) 数据均直接由 yfinance 返回，无需复杂的字段名映射。系统只需处理以下少量工作：

1.  **时区转换**: 将 Yahoo 返回的本地时间统一转为 UTC 时间戳存储。
2.  **代码后缀标准化**:
    *   US: 原样 (e.g. `AAPL`)
    *   HK: `.HK` (e.g. `0700.HK`)
    *   CN: `.SS` / `.SZ` (e.g. `600519.SS`)

#### 备用映射 (仅限灾备场景)

仅当启用 AkShare 备用源时，才需要执行字段映射（详见代码配置）。在正常运行模式下，映射逻辑将被**旁路**。

---

## 3. 数据库 Schema 设计

本系统核心由三张主表构成，它们共同构成了数据从"采集"到"应用"的全生命周期。

### 3.1 三大主表结构与关系 (Table Structure & Relationships)

#### 核心关系图
```mermaid
graph TD
    API[外部 API (yfinance/AkShare)] -->|JSON Payload| Raw[RawMarketData (原始数据)]
    Raw -->|ETL 清洗/转换| Daily[MarketDataDaily (日线历史)]
    Daily -->|最新一条记录| Snap[MarketSnapshot (实时快照)]
    Daily -->|聚合计算| Snap
    Snap -->|提供数据| UI[Frontend UI]
```

#### 1. 原始数据表 (`RawMarketData`)
*   **定位**: 数据"缓冲区"与"证据链"。存储 API 返回的原始 JSON，不做任何修改。
*   **关键用途**: 故障排查、ETL 重跑、原始数据归档。
*   **字段详情**:
    *   `id`: 主键
    *   `source`: `yfinance` / `akshare`
    *   `symbol`: 股票代码
    *   `market`: `US`/`CN`/`HK`
    *   `payload`: **Text/JSON** (API返回的完整原始数据)
    *   `processed`: **Boolean** (ETL 是否已处理)

#### 2. 日线历史表 (`MarketDataDaily`)
*   **定位**: 系统的"事实来源" (Source of Truth)。存储清洗后的标准 OHLCV 数据。
*   **关键用途**: K线图展示、历史回测、估值分析 (PE/PB 分位点)。
*   **字段详情**:
    *   `timestamp`: **UTC ISO8601** (如 `2025-12-19T16:00:00`) - **复合主键之一**
    *   `open/high/low/close`: **Float** (前复权价格)
    *   `volume`: **Int** (成交量)
    *   `turnover`: **Float** (成交额，CN/HK专用)

#### 3. 实时快照表 (`MarketSnapshot`)
*   **定位**: 前端"看板"数据。仅存储每个标的**最新**的一条状态。
*   **关键用途**: Watchlist 列表展示、快速计算涨跌幅。
*   **更新逻辑**: 
    *   盘中: 由 WebSocket/轮询实时更新。
    *   盘后: 由 `MarketDataDaily` 最新数据覆盖更新。
*   **字段详情**:
    *   `price`: **Float** (最新价)
    *   `change`: **Float** (涨跌额)
    *   `pct_change`: **Float** (涨跌幅 %)
    *   `pe/pb/market_cap`: **Float** (估值指标)

### 3.2 遗留问题与修复建议
1.  **时间戳一致性**: 目前 `MarketDataDaily` 混用了多种时间格式，导致查询困难。-> **Fix**: 统一迁移至 ISO8601。
2.  **Payload 膨胀**: `RawMarketData` 若存储全量历史会过大。-> **Fix**: 仅在增量更新(5d)模式下使用此表。

---

## 4. 重构路线图 (Refactoring Roadmap)

### 第一阶段：标准化 (立即执行)

*   **目标**: 将 `daily_incremental_update.py` 确立为*标准*获取引擎。
*   **行动**:
    1.  重构 `DataFetcher` 以使用与增量脚本相同的简单适配器。
    2.  弃用 `data_fetcher.py` 中复杂的"智能路由"逻辑。
    3.  确保 `RawMarketData` 始终作为数据入口（禁止直接写入 `MarketDataDaily`）。
    4.  在 `models.py` 验证器中标准化时间戳处理。

### 第二阶段：解耦 ETL (中期目标)

*   **目标**:彻底分离数据获取与数据处理。
*   **行动**:
    1.  **Fetcher**: 仅负责 `API -> RawMarketData`。
    2.  **Processor**: 后台 Worker 监听 `RawMarketData`（或通过事件触发）-> 写入 `MarketDataDaily`。
    3.  **验证**: 添加 `DataQuality` 表以记录处理错误/警告（例如：可疑的价格尖峰）。

### 第三阶段：健壮的调度与监控 (长期目标)

*   **目标**: 企业级的可靠性。
*   **行动**:
    1.  将所有定时任务迁移至外部系统（LaunchAgent/Cron，或扩展时使用 Celery/Redis 等专用任务队列）。
    2.  在前端构建"系统状态"仪表盘页面，显示：
        *   每个市场的最后成功获取时间。
        *   ETL 队列状态。
        *   来自数据库的错误日志。

---

## 5. 决策与风控模块 (Decision & Risk Module) - 未来规划

本模块位于数据层之上，是系统的"大脑"，负责消费结构化数据并输出投资决策信号。

### 5.1 架构定位

*   **输入**: `MarketDataDaily` (历史趋势), `MarketSnapshot` (实时状态)
*   **输出**: `AnalysisResult` (估值分析), `RiskSignal` (风险预警)

### 5.2 核心功能规划

1.  **资产评估引擎 (Asset Valuation Engine)**:
    *   **历史分位点分析**: 计算当前 PE/PB 在过去 3/5/10 年中的百分位。
    *   **DCF 模型**: 简化的现金流折现模型（需接入更详细的财务数据）。
    
2.  **风险监控 (Risk Monitor)**:
    *   **波动率监控**: 识别价格异常波动。
    *   **流动性预警**: 针对港股/美股小盘股，监测成交量枯竭风险。
    *   **持仓集中度**: 自动计算单一资产或单一市场的风险暴露度。

3.  **AI 决策辅助**:
    *   利用 LLM 结合定量数据（价格/估值）与定性数据（新闻/财报），生成综合投资建议。

---

## 6. 新功能开发指南

### 添加新的数据源
1.  **不要** 直接修改 `backend/main.py`。
2.  在 `backend/fetchers/` 中创建标准化的适配器函数（如需则创建目录）。
3.  确保它返回标准化的 DataFrame/Dict。
4.  将其接入 `daily_incremental_update.py`。

### 调试数据问题
1.  **检查 Raw**: `select * from rawmarketdata order by id desc limit 1` -> 数据到了吗？
2.  **检查 ETL**: 手动运行 `python3 run_etl.py` -> 处理过程报错了吗？
3.  **检查 DB**: `select * from marketdatadaily ...` -> 时间戳正确吗？

---

## 6. 关键文件

*   `daily_incremental_update.py`: **核心脚本**，用于每日增量更新。
*   `backend/data_fetcher.py`: **旧版核心**，包含有价值的 ETL 逻辑，但用法复杂。
*   `backend/etl_service.py`: 将 Raw 转换为结构化数据的逻辑。
*   `backend/models.py`: 数据库 Schema 定义。
