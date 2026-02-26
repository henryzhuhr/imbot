# 华尔街见闻快讯抓取器

支持两种模式：**实时模式**（从 WebSocket 获取）和 **Mock 模式**（从 JSONL 文件回放）。

## 功能特点

- ✅ **实时模式**：通过 WebSocket 连接获取华尔街见闻实时快讯
- ✅ **Mock 模式**：从 JSONL 文件回放历史数据，支持测试和开发
- ✅ **多频道订阅**：支持全球、美股、A股、港股、区块链等多个频道
- ✅ **自动去重**：基于新闻 ID 的双结构去重机制
- ✅ **断线重连**：实时模式支持自动重连和续拉
- ✅ **灵活回放**：Mock 模式支持循环、随机、限速等多种配置

## 快速开始

### 1. 实时模式（需要网络连接）

```bash
# 订阅全球频道
uv run python -m src.stock.news.wallstreet

# 订阅多个频道
uv run python -m src.stock.news.wallstreet --channel global-channel --channel us-stock-channel

# 运行 60 秒后自动停止
uv run python -m src.stock.news.wallstreet --duration 60
```

### 2. Mock 模式（从 JSONL 文件回放）

```bash
# 基础用法：播放 10 条后停止
uv run python -m src.stock.news.wallstreet --mock --max-items 10

# 自定义间隔和文件
uv run python -m src.stock.news.wallstreet \
    --mock \
    --mock-file packages/stock_helper/data/wallstreet.jsonl \
    --interval 0.5 \
    --max-items 20

# 循环播放（默认）
uv run python -m src.stock.news.wallstreet --mock

# 不循环播放（播放一遍后停止）
uv run python -m src.stock.news.wallstreet --mock --no-loop

# 随机顺序播放
uv run python -m src.stock.news.wallstreet --mock --shuffle --max-items 50
```

## Python API 使用

### 实时模式

```python
from src.stock.news.wallstreet import WallstreetLiveFetcher

# 创建实时抓取器
fetcher = WallstreetLiveFetcher(
    channels=["global-channel", "us-stock-channel"],
    reconnect_delay=5.0,  # 断线重连间隔
)

# 启动抓取
fetcher.start()

# 运行一段时间...
import time
time.sleep(60)

# 停止抓取
fetcher.destroy()
```

### Mock 模式

```python
from src.stock.news.wallstreet import WallstreetMockFetcher

# 创建 Mock 抓取器
fetcher = WallstreetMockFetcher(
    mock_file="packages/stock_helper/data/wallstreet.jsonl",  # 数据文件路径
    replay_interval=0.5,                           # 每条消息间隔 0.5 秒
    loop_replay=True,                              # 循环播放
    shuffle=False,                                 # 不打乱顺序
    max_items=100,                                 # 最多播放 100 条
    channels=["global-channel"],                   # 过滤频道
)

# 启动回放
fetcher.start()

# 等待播放完成...
time.sleep(60)

# 停止回放
fetcher.destroy()
```

### 自定义输出处理

```python
from src.stock.news.wallstreet import WallstreetMockFetcher

def on_news(item):
    """通过 subscribe 回调自定义输出处理"""
    # 保存到数据库
    # db.save_news(item.content, item.metadata)
    
    # 推送到消息队列
    # mq.publish(item.content)
    
    # 或者简单打印
    print(f"[{item.news_id}] {item.content}")

fetcher = WallstreetMockFetcher(
    mock_file="packages/stock_helper/data/wallstreet.jsonl",
    replay_interval=1.0,
)
fetcher.subscribe(on_news)
fetcher.start()
```

## 命令行参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mock` | 启用 Mock 模式 | False（实时模式） |
| `--mock-file` | Mock 数据文件路径 | `packages/stock_helper/data/wallstreet.jsonl` |
| `--interval` | Mock 模式消息间隔（秒） | 1.0 |
| `--no-loop` | Mock 模式不循环播放 | False（循环播放） |
| `--shuffle` | Mock 模式随机打乱顺序 | False |
| `--max-items` | Mock 模式最多播放条数 | None（不限制） |
| `--channel` | 订阅的频道名（可多次指定） | `global-channel` |
| `--duration` | 运行时长（秒），0 表示持续运行 | 0 |

## 频道列表

| 频道名 | 说明 |
|--------|------|
| `global-channel` | 全球财经新闻 |
| `us-stock-channel` | 美股资讯 |
| `a-stock-channel` | A股资讯 |
| `hk-stock-channel` | 港股资讯 |
| `blockchain-channel` | 区块链/加密货币 |
| `goldc-channel` | 黄金市场 |
| `oil-channel` | 原油市场 |
| `xgb-channel` | 新股发行 |
| `forex-channel` | 外汇市场 |

## Mock 数据文件格式

Mock 模式使用的 JSONL 文件格式（每行一个 JSON 对象）：

```jsonl
{"content": {"channels": ["global-channel"], "content": "新闻内容", "id": 123, "op_name": "create", ...}, "command": "create"}
{"content": {"channels": ["us-stock-channel"], "content": "另一条新闻", "id": 124, "op_name": "create", ...}, "command": "create"}
```

实时模式会自动将接收到的消息追加到 `packages/stock_helper/data/wallstreet.jsonl` 文件中，因此可以：

1. 先运行实时模式收集一些数据
2. 然后使用 Mock 模式回放这些数据进行测试

## 使用场景

### Mock 模式适用场景

- 🧪 **单元测试**：在测试中使用稳定的 Mock 数据
- 🚀 **开发调试**：不依赖网络连接进行功能开发
- 📊 **性能测试**：控制推送速度测试系统承载能力
- 🔄 **数据回放**：重现历史数据进行分析
- 📚 **演示展示**：在没有网络的环境下展示功能

### 实时模式适用场景

- 🔴 **生产环境**：获取最新的实时财经快讯
- 📦 **数据收集**：持续采集新闻数据到 JSONL 文件
- ⚡ **实时推送**：将新闻实时推送到下游系统

## 示例代码

运行演示脚本：

```bash
# 运行 Mock 演示（播放 10 条）
uv run python demo/wallstreet_mock_demo.py 1

# 运行 Mock 循环演示（随机播放 20 条）
uv run python demo/wallstreet_mock_demo.py 2

# 运行实时模式演示（需要网络）
uv run python demo/wallstreet_mock_demo.py 3
```

## 技术细节

### 去重机制

使用双结构去重：

- `deque`：FIFO 队列，自动淘汰最旧的 ID
- `set`：O(1) 查重性能

默认缓存最近 2000 条新闻 ID。

### 线程模型

- 实时模式：独立线程 + 独立事件循环处理 WebSocket
- Mock 模式：独立线程 + 同步回放
- 主线程：负责启动/停止控制

### 暂停/恢复

```python
# 暂停（保持连接但不处理消息）
fetcher.pause()

# 恢复
fetcher.pause()  # 再次调用切换状态
```

## 故障排查

### Mock 模式没有输出

1. 检查文件路径是否正确
2. 检查 JSONL 文件是否为空
3. 检查频道过滤是否过于严格

### 实时模式连接失败

1. 检查网络连接
2. 查看日志中的错误信息
3. 尝试增加 `reconnect_delay` 参数

## License

MIT License
