# stock_helper demos

用于演示不同新闻来源（`wallstreet`、`jin10`）的最小可运行示例。

## 运行方式

在仓库根目录执行：

```bash
# Wallstreet（基于本地 JSONL mock 回放）
uv run python packages/stock_helper/demo/wallstreet_mock_demo.py

# Jin10（基于本地 JSONL 解析示例）
uv run python packages/stock_helper/demo/jin10_jsonl_demo.py
```
