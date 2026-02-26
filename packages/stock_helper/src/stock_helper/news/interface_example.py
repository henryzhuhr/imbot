"""
NewsFetcher 使用示例：演示如何实现订阅分发。

功能：给开发者提供可直接复用的 Fetcher 子类实现模板。
实现：展示 __init__ 状态初始化、生命周期方法覆写、NewsItem 映射与订阅分发链路。
"""

import threading
import time
from datetime import datetime
from typing import Optional, override

from .interface import NewsConsumer, NewsFetcher, NewsItem, NewsSourceType


class DemoNewsFetcher(NewsFetcher):
    """
    功能：提供一个最小可运行的抓取器示例。
    实现：用后台线程模拟抓取、用 Event 控制退出、用 _paused 控制暂停与恢复。
    """

    def __init__(self, *, interval: float = 1.0, max_items: int = 5) -> None:
        super().__init__()
        # 功能：配置推送频率。实现：按 interval 间隔发送一条模拟消息。
        self.interval = interval
        # 功能：限制示例输出数量。实现：在 _run_loop 中按 max_items 截断。
        self.max_items = max_items
        # 功能：通知线程退出。实现：_destroy 中 set，_run_loop 中检查。
        self._stop_event = threading.Event()
        # 功能：持有线程句柄。实现：_start 创建并启动，_destroy join 回收。
        self._thread: Optional[threading.Thread] = None

    @override
    def _start(self) -> None:
        """
        启动抓取流程。启动相关的后台线程或异步任务来执行抓取逻辑，例如 wssocket 连接或定时器。
        """
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    @override
    def _destroy(self) -> None:
        """
        停止抓取并释放线程资源。确保后台线程能优雅退出，避免资源泄露。
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @override
    def _pause(self) -> None:
        """
        暂停消息分发。如果有其他暂停机制（如暂停抓取），也可以在这里实现。
        """
        pass

    @override
    def _resume(self) -> None:
        """
        恢复消息分发。如果有其他暂停机制（如暂停抓取），也可以在这里实现。
        """
        pass

    def _run_loop(self) -> None:
        """
        功能：持续产出并发送新闻。
        实现：循环检查 stop/pause，构造 NewsItem 后调用 _notify_subscribers。
        """
        sent = 0
        while not self._stop_event.is_set() and sent < self.max_items:
            # 功能：标准化新闻数据。实现：将原始消息字段映射到 NewsItem。
            item = NewsItem(
                news_id=f"demo-{sent + 1}",
                content=f"这是一条示例快讯 #{sent + 1}",
                news_time=datetime.now(),
                source_type=NewsSourceType.JIN10,
                metadata={"demo": True},
            )
            self._notify_subscribers(item)
            sent += 1

            if self._stop_event.wait(self.interval):
                break


class NewsAgent(NewsConsumer):
    """功能：消费订阅消息。实现：在 consume 中按简略或详细模式输出。"""

    def __init__(self, name: str, *, verbose: bool = False) -> None:
        self.name = name
        self.verbose = verbose

    def consume(self, item: NewsItem) -> None:
        if self.verbose:
            print(
                "[{name}] source={source}, time={time}, metadata={metadata}".format(
                    name=self.name,
                    source=item.source_type,
                    time=item.news_time.isoformat(timespec="seconds"),
                    metadata=item.metadata,
                )
            )
            return
        print(f"[{self.name}] {item.news_id}: {item.content}")


def main() -> None:
    """功能：演示最小接线流程。实现：创建 fetcher/consumer、订阅、启动、销毁。"""
    fetcher = DemoNewsFetcher(interval=0.5, max_items=4)
    brief_agent = NewsAgent("brief")
    detail_agent = NewsAgent("detail", verbose=True)

    # 同一条消息会分发给所有订阅者回调。
    fetcher.subscribe(brief_agent.consume)
    fetcher.subscribe(detail_agent.consume)

    fetcher.start()
    time.sleep(3)
    fetcher.destroy()


if __name__ == "__main__":
    main()
