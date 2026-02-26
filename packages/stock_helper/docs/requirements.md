# stock_helper 模块需求文档（初稿）

## 1. 文档目的

本文档用于沉淀 `stock_helper` 模块的需求基线，作为后续功能补充、重构、测试和对外集成的统一参考。

## 2. 模块目标

`stock_helper` 负责提供股票相关能力，当前包含两大方向：

1. 新闻快讯能力：从多新闻源获取、标准化并分发快讯。
2. 股票搜索能力：通过外部接口查询股票基础信息。

## 3. 范围定义

### 3.1 In Scope

1. 新闻源接入与标准化（Jin10、Wallstreet）。
2. 实时订阅分发机制（发布/订阅 + 队列缓冲）。
3. Mock/离线回放能力（基于 `packages/stock_helper/data/*.jsonl`）。
4. 股票关键词搜索（Tencent）。

### 3.2 Out of Scope（当前版本）

1. 统一持久化存储（数据库落库）。
2. 新闻智能去重策略（跨源语义去重）。
3. 新闻聚类/摘要/情感分析。
4. 完整行情数据服务（`service/stock.py` 目前仅占位）。

## 4. 当前模块结构

1. `src/stock_helper/news`：新闻抽象接口、具体来源实现、mock 工具。
2. `src/stock_helper/search`：股票搜索抽象接口、Tencent 实现。
3. `src/stock_helper/common`：消息队列抽象与内存实现。
4. `src/stock_helper/types`：市场枚举等基础类型。
5. `data`：模块共享样例数据与 mock 回放数据。
6. `demo`：按来源拆分的最小可运行示例。
7. `tests`：news 相关单元测试与行为测试。

## 5. 业务需求

### 5.1 新闻标准化

1. 系统必须将不同来源消息统一为 `NewsItem` 模型。
2. `NewsItem` 核心字段必须包含：`news_id`、`content`、`news_time`、`source_type`。
3. 系统应尽量保留源字段到 `metadata`，避免信息丢失。
4. `news_time` 必须支持字符串/时间戳/`datetime` 输入并标准化为 `datetime`。

### 5.2 新闻实时分发

1. 系统必须支持订阅回调注册（`subscribe`）。
2. 新闻分发应通过内部消息队列异步处理，减少源抓取线程阻塞。
3. 当队列已满时，系统应记录告警并丢弃消息（避免阻塞崩溃）。
4. 订阅者回调异常不应影响其他订阅者处理。

### 5.3 新闻源接入

1. 系统应支持至少以下新闻源：
2. `Jin10FlashService`（WebSocket 协议消息）。
3. `WallstreetLiveFetcher`（WebSocket 实时快讯）。
4. 每个来源必须具备基本生命周期控制：启动、暂停/恢复、销毁。
5. 来源实现应具备基础去重能力（按源内 `id/news_id`）。
6. 来源实现应支持异常重连与错误日志输出。

### 5.4 Mock 与本地数据

1. 系统必须提供离线回放能力用于开发与测试。
2. 模块共享数据文件必须位于 `packages/stock_helper/data`。
3. demo 与 tests 应默认使用 `data` 目录中的样例数据。

### 5.5 股票搜索

1. 系统必须提供统一股票搜索接口 `BaseStockSearcher`。
2. Tencent 搜索实现应支持关键词检索并返回标准 `StockInfo` 列表。
3. 搜索结果必须包含市场、代码、名称、简称等字段。

## 6. 非功能需求

### 6.1 可维护性

1. 对外能力应通过抽象接口定义（`NewsFetcher`、`BaseStockSearcher`）。
2. 新增新闻源时应最小化对现有代码影响。

### 6.2 可靠性

1. 网络异常时应自动重连（带重连间隔配置）。
2. 模块异常不应导致主进程无提示退出，应有日志可追踪。

### 6.3 可测试性

1. 关键解析和分发逻辑必须可通过单元测试覆盖。
2. 关键流程应可通过本地 JSONL 回放复现。

## 7. 数据契约（核心）

### 7.1 NewsItem

1. 必填：`news_id`、`content`、`news_time`、`source_type`。
2. 选填：`title`、`source_name`、`source_url`、`importance`、`channels`、`tags`、`content_html`、`content_extended`。
3. 扩展：`metadata`（源特定字段透传）。

### 7.2 StockInfo

1. 必填：`market`、`code`、`name`。
2. 选填：`abbreviation`。

## 8. 运行与验证需求

### 8.1 本地验证命令

1. `uv run python packages/stock_helper/demo/wallstreet_mock_demo.py`
2. `uv run python packages/stock_helper/demo/jin10_jsonl_demo.py`
3. `uv run python -m pytest packages/stock_helper/tests/news -q`

### 8.2 验收标准（MVP）

1. demo 可在本地基于 `data` 目录稳定输出新闻。
2. news 测试用例通过。
3. 新增/修改路径后，demo 与 tests 不再依赖 `src/stock_helper/news` 内数据文件。

## 9. 已知问题与待补充

1. `search` 子模块存在导入路径风格不统一（如 `from types.market`、`from search.interface`），后续需统一到包内绝对导入规范。
2. `service/stock.py` 目前仅有占位说明，需补齐服务边界与接口。
3. 新闻源配置管理（环境变量、配置文件）尚未统一。
4. 文档尚未包含错误码、监控指标和性能基线。

## 10. 后续补充建议（占位）

1. 补充“需求优先级”（P0/P1/P2）与版本里程碑。
2. 补充“外部接口 SLA”（重连次数、最大延迟、消息丢弃策略）。
3. 补充“数据治理规范”（字段变更兼容策略、schema version）。
4. 补充“发布与回滚流程”。
