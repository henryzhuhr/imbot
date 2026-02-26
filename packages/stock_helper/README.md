# stock-helper

Stock module - news fetching, search, and data services.

## 示例程序（demo）

在 `packages/stock_helper/demo` 目录下提供了不同新闻来源的示例程序：

- `wallstreet_mock_demo.py`：华尔街见闻来源（本地 JSONL mock 回放）
- `jin10_jsonl_demo.py`：金十来源（本地 JSONL 解析示例）

在仓库根目录执行：

```bash
uv run python packages/stock_helper/demo/wallstreet_mock_demo.py
uv run python packages/stock_helper/demo/jin10_jsonl_demo.py
```

## 运行测试

在仓库根目录执行：

```bash
# 安装依赖（包含开发依赖，如 pytest）
uv sync

# 运行 stock_helper 全部测试
uv run python -m pytest packages/stock_helper/tests -q

# 只运行 news 相关测试
uv run python -m pytest packages/stock_helper/tests/news -q
```
