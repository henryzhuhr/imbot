import time
from datetime import datetime

from stock_helper.news.interface import NewsSourceType
from stock_helper.news.wallstreet import (
    WallstreetLiveFetcher,
    WallstreetNewsChannel,
    WallstreetNewsItem,
)


class _FakeLogger:
    def debug(self, *_args, **_kwargs) -> None:
        return None

    def info(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None

    def error(self, *_args, **_kwargs) -> None:
        return None


class TestWallstreetLiveNewsChannel:
    def test_enum_values(self) -> None:
        assert WallstreetNewsChannel.GLOBAL.value == "global-channel"
        assert WallstreetNewsChannel.US_STOCK.value == "us-stock-channel"


class TestWallstreetLiveNews:
    def test_model_parse(self) -> None:
        news = WallstreetNewsItem(
            content={
                "channels": ["global-channel"],
                "content": "content",
                "content_text": "summary",
                "display_time": "2026-02-15 00:00:00",
                "id": 1,
                "op_id": 2,
                "op_name": "create",
                "score": 1.0,
                "uri": "source",
            },
            command="create",
        )
        assert news.content.id == 1
        assert news.content.op_name == "create"


class TestWallstreetLiveFetcher:
    def test_handle_news_item_dispatch_and_dedup(self) -> None:
        fetcher = WallstreetLiveFetcher(
            channels=["global-channel"],
            reconnect_delay=0,
            dedup_size=2,
            loggger=_FakeLogger(),
        )
        received = []
        fetcher.subscribe(lambda item: received.append(item))
        fetcher._running = True
        fetcher._worker_thread.start()

        item = {
            "id": 100,
            "channels": ["global-channel"],
            "op_name": "create",
            "title": "t",
            "content_text": "c",
            "display_time": 1700000000,
            "score": 1,
        }
        fetcher._handle_news_item(item)
        fetcher._handle_news_item(item)
        time.sleep(0.05)
        fetcher.destroy()

        assert len(received) == 1
        assert received[0].source_type == NewsSourceType.WALLSTREET

    def test_mark_seen_fifo(self) -> None:
        fetcher = WallstreetLiveFetcher(
            channels=["global-channel"],
            reconnect_delay=0,
            dedup_size=2,
            loggger=_FakeLogger(),
        )
        fetcher._mark_seen(1)
        fetcher._mark_seen(2)
        fetcher._mark_seen(3)
        assert fetcher._is_seen(1) is False
        assert fetcher._is_seen(2) is True
        assert fetcher._is_seen(3) is True

    def test_normalize_displaytime(self) -> None:
        fetcher = WallstreetLiveFetcher(
            channels=["global-channel"],
            reconnect_delay=0,
            dedup_size=2,
            loggger=_FakeLogger(),
        )
        parsed = fetcher._normalize_displaytime("2026-02-15 01:02:03")
        assert isinstance(parsed, datetime)
