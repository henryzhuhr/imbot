import time
from datetime import datetime

from stock_helper.news.interface import NewsItem, NewsSourceType
from stock_helper.news.interface_example import DemoNewsFetcher, NewsAgent


class TestDemoNewsFetcher:
    def test_start_and_emit(self) -> None:
        fetcher = DemoNewsFetcher(interval=0.01, max_items=3)
        received = []
        fetcher.subscribe(lambda item: received.append(item))
        fetcher.start()
        time.sleep(0.1)
        fetcher.destroy()
        assert len(received) == 3


class TestNewsAgent:
    def test_consume_brief(self, capsys) -> None:
        agent = NewsAgent("agent")
        agent.consume(
            NewsItem(
                news_id="n1",
                content="content",
                news_time=datetime.now(),
                source_type=NewsSourceType.JIN10,
            )
        )
        assert "[agent] n1: content" in capsys.readouterr().out

    def test_consume_verbose(self, capsys) -> None:
        agent = NewsAgent("agent", verbose=True)
        agent.consume(
            NewsItem(
                news_id="n1",
                content="content",
                news_time=datetime.now(),
                source_type=NewsSourceType.WALLSTREET,
                metadata={"k": "v"},
            )
        )
        assert "source=wallstreet" in capsys.readouterr().out
