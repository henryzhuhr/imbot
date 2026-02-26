# newsfetcher

新闻消息获取模块，负责从不同渠道拉取消息。

## 安装

```bash
uv add newsfetcher
```

## 使用

```python
from newsfetcher import NewsFetcher

fetcher = NewsFetcher()
news = fetcher.fetch()
print(news)
```

## 独立发布

```bash
cd packages/newsfetcher
uv build
uv publish
```
