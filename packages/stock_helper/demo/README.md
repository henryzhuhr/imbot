# stock_helper demos

用于演示不同新闻来源（`wallstreet`、`jin10`）的最小可运行示例。

## 运行方式

所有的 demo 程序都支持 **实时模式** 和 **回放模式** 两种运行方式，执行了实时模式后，可以得到一份回放数据用于本地测试，继续执行回放模式可以模拟实时抓取

### 金10数据

实时模式：连接 Jin10 WebSocket，将实时消息写入 `--output-file`（默认 `packages/stock_helper/data/jin10_realtime.jsonl`）用于后续回放或调试

```bash
uv run packages/stock_helper/demo/jin10_demo.py --mode realtime --max-items 20
```

> 默认无限等待，依赖手动 `Ctrl+C` 结束；自动化验证可传 `--timeout-seconds 300`（例如 5 分钟）。

回放模式：读取 `--input-file`（默认 `packages/stock_helper/data/jin10.jsonl`）做本地回放解析

```bash
uv run packages/stock_helper/demo/jin10_demo.py --mode replay --max-items 20
```

### 华尔街新闻

实时模式：连接 Wallstreet WebSocket，将实时消息写入 `--output-file`（默认 `packages/stock_helper/data/wallstreet_realtime.jsonl`）。

```bash
uv run packages/stock_helper/demo/wallstreet_demo.py --mode realtime --max-items 20
```

> 默认无限等待，依赖手动 `Ctrl+C` 结束；自动化验证可传 `--timeout-seconds 300`（例如 5 分钟）。

回放模式：读取 `--input-file`（默认 `packages/stock_helper/data/wallstreet_realtime.jsonl`）回放解析。

```bash
uv run packages/stock_helper/demo/wallstreet_demo.py --mode replay --max-items 20
```
