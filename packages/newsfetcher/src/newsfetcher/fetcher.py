"""新闻获取器 - Hello World 示例"""


class NewsFetcher:
    """新闻获取器，负责从不同渠道拉取消息"""

    def __init__(self, source: str = "default"):
        self.source = source

    def hello(self) -> str:
        return f"[NewsFetcher] Hello from source: {self.source}"

    def fetch(self) -> list[str]:
        """拉取新闻消息（示例）"""
        return [
            f"[{self.source}] 示例新闻 1",
            f"[{self.source}] 示例新闻 2",
        ]
