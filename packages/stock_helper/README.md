# stock-helper

Stock module - news fetching, search, and data services.

## 示例程序（demo）

在 `packages/stock_helper/demo` 目录下提供了不同新闻来源的示例程序，参考[demo文档](./demo/README.md) 进行使用

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
