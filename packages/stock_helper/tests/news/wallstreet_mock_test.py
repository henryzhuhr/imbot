"""
华尔街见闻 Mock 模式测试

可以使用 pytest 运行：
    uv run pytest packages/stock_helper/tests/news/wallstreet_mock_test.py -v
"""

import time
from pathlib import Path

import pytest

from stock_helper.news.wallstreet import WallstreetMockFetcher


class TestWallstreetMockFetcher:
    """测试 Mock 模式的各项功能"""

    @pytest.fixture
    def mock_file_path(self):
        """Mock 数据文件路径"""
        return Path(__file__).resolve().parents[2] / "data/wallstreet.jsonl"

    def test_mock_file_exists(self, mock_file_path):
        """测试 Mock 文件是否存在"""
        assert Path(mock_file_path).exists(), f"Mock 文件不存在: {mock_file_path}"

    def test_basic_replay(self, mock_file_path):
        """测试基本的回放功能"""
        received_items = []

        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.1,
            loop_replay=False,
            max_items=10,  # 设置更多条数以应对去重
        )

        fetcher.subscribe(lambda item: received_items.append(item))

        fetcher.start()
        time.sleep(3)  # 等待回放完成
        fetcher.destroy()

        # 验证至少收到了一些消息（考虑去重可能导致实际条数少于设置值）
        assert len(received_items) >= 5, (
            f"预期至少收到 5 条，实际收到 {len(received_items)} 条"
        )
        assert all(item.content for item in received_items)
        assert all(item.metadata for item in received_items)

    def test_channel_filtering(self, mock_file_path):
        """测试频道过滤功能"""
        received_items = []

        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.05,
            loop_replay=False,
            max_items=10,
            channels=["us-stock-channel"],  # 只订阅美股频道
        )

        fetcher.subscribe(lambda item: received_items.append(item))

        fetcher.start()
        time.sleep(2)
        fetcher.destroy()

        # 验证所有消息都包含订阅的频道
        for item in received_items:
            channels = item.channels or []
            assert "us-stock-channel" in channels, f"消息频道不匹配: {channels}"

    def test_deduplication(self, mock_file_path):
        """测试去重功能"""
        received_ids = []

        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.05,
            loop_replay=False,
            max_items=20,
        )

        fetcher.subscribe(lambda item: received_ids.append(item.news_id))

        fetcher.start()
        time.sleep(2)
        fetcher.destroy()

        # 验证没有重复的 ID
        assert len(received_ids) == len(set(received_ids)), "存在重复的新闻 ID"

    def test_max_items_limit(self, mock_file_path):
        """测试最大条数限制"""
        received_items = []

        max_items = 3
        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.1,
            loop_replay=True,  # 即使循环播放
            max_items=max_items,  # 也应该在达到最大值时停止
        )

        fetcher.subscribe(lambda item: received_items.append(item))

        fetcher.start()
        time.sleep(2)
        fetcher.destroy()

        assert len(received_items) == max_items, (
            f"预期最多 {max_items} 条，实际收到 {len(received_items)} 条"
        )

    def test_pause_functionality(self, mock_file_path):
        """测试暂停功能"""
        received_items = []

        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.1,
            loop_replay=False,
            max_items=10,
        )

        fetcher.subscribe(lambda item: received_items.append(item))

        fetcher.start()
        time.sleep(0.3)  # 接收几条

        count_before_pause = len(received_items)
        fetcher.pause()  # 暂停
        time.sleep(0.5)  # 暂停期间应该不接收新消息

        count_during_pause = len(received_items)
        assert count_during_pause == count_before_pause, "暂停期间不应该接收新消息"

        fetcher.pause()  # 恢复
        time.sleep(0.5)  # 恢复后继续接收

        count_after_resume = len(received_items)
        assert count_after_resume > count_during_pause, "恢复后应该继续接收消息"

        fetcher.destroy()

    def test_stop_functionality(self, mock_file_path):
        """测试停止功能"""
        received_items = []

        fetcher = WallstreetMockFetcher(
            mock_file=mock_file_path,
            replay_interval=0.1,
            loop_replay=True,
        )

        fetcher.subscribe(lambda item: received_items.append(item))

        fetcher.start()
        time.sleep(0.5)

        count_before_stop = len(received_items)
        fetcher.destroy()  # 停止
        time.sleep(0.5)

        count_after_stop = len(received_items)
        assert count_after_stop <= count_before_stop + 1, "停止后不应该持续接收新消息"


if __name__ == "__main__":
    # 可以直接运行此文件进行快速测试
    pytest.main([__file__, "-v", "-s"])
