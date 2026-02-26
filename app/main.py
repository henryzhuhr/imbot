"""
app/main.py - 应用入口

同时使用 newsfetcher 和 imbot 两个模块。
"""

from imbot import IMBot
from newsfetcher import NewsFetcher


def main() -> None:
    # 1. 拉取新闻
    fetcher = NewsFetcher()
    news_list = fetcher.fetch()

    # 2. 通过机器人发送消息
    bot = IMBot(platform="feishu")
    for news in news_list:
        bot.send(news)


if __name__ == "__main__":
    main()
