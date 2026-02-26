"""
新闻获取器 - hello world 示例
"""


class NewsItem:
    """单条新闻数据模型"""

    def __init__(self, title: str, source: str, content: str = "") -> None:
        self.title = title
        self.source = source
        self.content = content

    def __repr__(self) -> str:
        return f"NewsItem(title={self.title!r}, source={self.source!r})"


class NewsFetcher:
    """新闻获取器，从不同渠道拉取消息"""

    def fetch(self) -> list[NewsItem]:
        """从所有已注册的渠道拉取新闻（hello world 示例）"""
        print("Hello from newsfetcher!")
        return [
            NewsItem(title="示例新闻标题", source="example", content="这是一条示例新闻。")
        ]
