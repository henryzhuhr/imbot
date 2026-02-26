# stock_helper 技术实现文档

## 1. 实现目标

`stock_helper` 提供两类核心技术能力：

1. 新闻快讯获取、标准化与分发（重点）。
2. 股票搜索能力（Tencent 实现）。

本文重点说明新闻获取链路，尤其是通过 mock 缩短开发/测试等待时间的实现方式。

## 2. 模块实现结构

1. `src/stock_helper/news/interface.py`
作用：定义统一新闻模型 `NewsItem`、抓取器抽象 `NewsFetcher`、消费者抽象 `NewsConsumer`。
2. `src/stock_helper/news/wallstreet.py`
作用：华尔街见闻实时抓取（`WallstreetLiveFetcher`）与 mock 回放（`WallstreetMockFetcher`）。
3. `src/stock_helper/news/jin10.py`
作用：金十实时抓取（`Jin10FlashService`）与原始消息落盘。
4. `src/stock_helper/common/message_queue.py`
作用：消息队列抽象与默认内存队列实现，支持异步分发。
5. `data/*.jsonl`
作用：离线回放数据源（demo/tests 共用）。

## 3. 新闻获取通用链路

### 3.1 标准化模型

所有来源最终输出统一 `NewsItem`：

1. 必填：`news_id`、`content`、`news_time`、`source_type`。
2. 可选：`title`、`source_url`、`channels`、`importance` 等。
3. `metadata` 保留源侧原始字段，便于追溯与后处理。

### 3.2 分发机制

1. 抓取器收到原始消息后先解析并映射为 `NewsItem`。
2. 通过 `_notify_subscribers` 投递到内部队列。
3. 后台线程 `_notify_subscribers_loop` 从队列消费并广播给订阅者回调。
4. 回调异常被隔离，不影响其他订阅者。

### 3.3 可靠性策略

1. WebSocket 异常重连（来源实现各自配置重连间隔）。
2. 本地去重（按 `news_id/id` 做源内去重）。
3. 队列满时丢弃并告警，避免阻塞主流程。

## 4. 实时抓取实现

### 4.1 Wallstreet（实时）

`WallstreetLiveFetcher` 使用 WSS 连接，处理流程：

1. 建立连接并发送订阅命令。
2. 持续读取消息，解析 JSON。
3. 提取 `content` 字段（可能是单条 dict 或列表）。
4. 过滤频道、去重、映射 `NewsItem`。
5. 进入统一队列并分发给订阅者。

### 4.2 Jin10（实时）

`Jin10FlashService` 处理自定义协议帧：

1. 建立连接，处理心跳与登录流程。
2. 解码消息载荷并抽取业务字段。
3. 通过 `Jin10Message` 转换为 `NewsItem`。
4. 可选把原始消息追加写入 `packages/stock_helper/data/jin10.jsonl`。

## 5. Mock 实现与“避免长期等待”

### 5.1 背景问题

实时源在开发中有几个常见痛点：

1. 等待实时消息时间不可控。
2. 网络波动导致调试中断。
3. 回归测试难复现同一批输入。

### 5.2 方案设计

使用“离线 JSONL 回放”替代实时连接：

1. 读取固定样本文件（`data/wallstreet.jsonl`、`data/jin10.jsonl`）。
2. 按设定速率重放消息，模拟实时推送。
3. 仍走与线上一致的解析/去重/分发链路（尽量保持行为一致）。

### 5.3 Wallstreet Mock 机制

`WallstreetMockFetcher` 继承 `WallstreetLiveFetcher`，核心覆写：

1. 覆写 `_run_loop`：不走网络连接，改为本地文件回放。
2. 覆写 `_handle_raw_message`：只解析并分发，不写回文件。
3. 支持参数：
4. `mock_file`：mock 数据路径（默认 `packages/stock_helper/data/wallstreet.jsonl`）。
5. `replay_interval`：每条消息间隔。
6. `max_items`：最多推送条数。
7. `loop_replay`：是否循环。
8. `shuffle`：是否打乱顺序。

### 5.4 Jin10 Mock/离线解析机制

当前 Jin10 侧主要通过“离线 JSONL 解析示例”快速验证：

1. 使用 `demo/jin10_jsonl_demo.py` 逐行读取 `data/jin10.jsonl`。
2. 调用 `Jin10Message.from_payload(...).to_news_item()` 复用正式映射逻辑。
3. 通过 `max_items` 方式快速截断，避免等待。

### 5.5 推荐调试策略（避免久等）

本地开发优先使用以下模式：

1. `wallstreet`：`replay_interval=0.05~0.2` + `max_items=5~30`。
2. `jin10`：离线解析 + `max_items` 截断。
3. 仅在联调前切换实时模式验证网络链路。

## 6. 开发与测试运行手册

在仓库根目录执行：

```bash
# 快速验证 wallstreet mock（推荐日常开发）
uv run python packages/stock_helper/demo/wallstreet_mock_demo.py

# 快速验证 jin10 离线解析（推荐日常开发）
uv run python packages/stock_helper/demo/jin10_jsonl_demo.py

# 运行 news 相关测试
uv run python -m pytest packages/stock_helper/tests/news -q
```

## 7. 技术权衡

1. Mock 不能覆盖真实网络抖动、协议变更、心跳超时等问题。
2. Mock 能显著提高迭代速度与可复现性，适合作为默认开发路径。
3. 推荐策略：开发与回归用 mock，预发布前补一次实时链路冒烟。

## 8. 后续可演进方向

1. 增加统一的“回放控制器”（倍速、时间窗口、断点续播）。
2. 为 Jin10 增加对等 `MockFetcher` 类，统一两来源使用体验。
3. 将回放样本分级（small/medium/full），缩短 CI 时间。
4. 增加端到端对比工具（实时样本 vs mock 样本字段一致性）。
