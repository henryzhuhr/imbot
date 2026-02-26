"""
华尔街见闻（https://wallstreetcn.com/live/global）快讯抓取。
"""

import argparse
import asyncio
import json
import random
import threading
import time
from collections import deque
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union, override

import websockets
from common.log import Logger
from loguru import logger as default_logger
from pydantic import BaseModel, Field
from websockets import ClientConnection
from websockets.exceptions import ConnectionClosed

from .interface import NewsFetcher, NewsItem, NewsSourceType


class WallstreetNewsChannel(StrEnum):
    """
    频道枚举，定义了华尔街见闻快讯的不同频道类型，供订阅和过滤使用。
    """

    GLOBAL = "global-channel"
    """全球频道，包含全球范围内的财经新闻和事件，适合关注国际市场动态的用户。"""

    US_STOCK = "us-stock-channel"
    """美股频道，专注于美国股票市场的新闻和分析，适合关注美股投资机会的用户。"""

    A_STOCK = "a-stock-channel"
    """A股频道，聚焦中国大陆股票市场的资讯和评论，适合关注中国股市的投资者。"""

    HK_STOCK = "hk-stock-channel"
    """港股频道，提供香港股票市场的最新消息和深度分析，适合关注港股投资的用户。"""

    BLOCKCHAIN = "blockchain-channel"
    """区块链频道，涵盖区块链技术、加密货币及相关市场动态，适合关注数字资产和区块链技术的用户。"""

    GoLDC = "goldc-channel"
    """黄金频道，专注于黄金市场的新闻、价格走势和投资分析，适合关注贵金属投资的用户。"""

    OIL = "oil-channel"
    """原油频道，提供原油市场的最新资讯、价格变动和行业分析，适合关注能源市场的投资者。"""

    XGB = "xgb-channel"
    """新股频道，聚焦新股发行、上市动态及相关投资机会，适合关注新股市场的用户。"""


class WallstreetNewsCommand(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    """update说明有新的内容更新了，可能是之前的新闻有了新的发展，或者是对原有内容的补充和修正。用相同的id"""


class WallstreetNewsItemContent(BaseModel):
    """
    华尔街见闻快讯的新闻数据模型，包含了从 WSS 消息中提取的核心字段和元数据
    """

    channels: List[str] = Field(default_factory=list)
    """新闻所属频道列表，示例：['global-channel']"""

    content: str
    """新闻内容文本，通常包含标题和正文摘要"""

    content_text: Optional[str]
    """新闻正文摘要，部分消息可能没有该字段"""

    display_time: Optional[Union[int, str]]
    """新闻展示时间，可能是时间戳或字符串"""

    id: int
    """新闻唯一 ID，整数类型"""

    op_id: Optional[int]
    """操作 ID，通常与 op_name 配合使用，部分消息可能没有该字段"""

    op_name: str
    """操作类型，示例：'create'（新增）、'update'（更新)、'reorder'（排序调整）"""

    score: Optional[float]
    """新闻热度分数，数值越大表示越热，部分消息可能没有该字段"""

    uri: Optional[str]
    """新闻来源 URI，部分消息可能没有该字段"""


class WallstreetNewsItem(BaseModel):
    content: WallstreetNewsItemContent
    command: str


class WallstreetLiveFetcher(NewsFetcher):
    """基于前端同协议 WSS 的华尔街见闻快讯抓取器。"""

    WSS_URL = "wss://streamer-prod-wscn.awtmt.com/wsv1/realtime"
    """华尔街见闻快讯的 WSS 地址，前端同协议"""

    logger: Logger
    """注入的日志接口实例，用于输出日志信息，需实现 Logger 接口"""

    cursor: str
    """服务端游标，用于断线后续拉"""

    channels: set[str]
    """需要接收的频道集合，默认 global-channel"""

    reconnect_delay: float
    """断线后的重连间隔（秒）"""

    _seen_ids: deque[int]
    """本地去重缓存（按新闻 id）"""

    _seen_set: set[int]
    """本地去重集合（按新闻 id）"""

    _stop_event: threading.Event
    """线程停止事件，用于优雅关闭连接和线程"""

    _thread: Optional[threading.Thread]
    """后台线程对象，负责运行事件循环"""

    _loop: Optional[asyncio.AbstractEventLoop]
    """事件循环对象，在线程内创建用于处理异步连接"""
    _paused: bool
    """是否暂停处理消息（用于 mock 回放和实时模式）"""

    def __init__(
        self,
        *,
        cursor: str = "",
        channels: Optional[Iterable[str]] = None,
        reconnect_delay: float = 5.0,
        dedup_size: int = 2000,
        loggger: Optional[Logger] = None,
    ):
        super().__init__()
        self.cursor = cursor
        self.channels = set(channels or ["global-channel"])
        self.reconnect_delay = reconnect_delay
        # 双结构去重：deque 用于 FIFO 淘汰，set 用于 O(1) 查重。
        self._seen_ids: deque[int] = deque(maxlen=dedup_size)
        self._seen_set: set[int] = set()

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._paused = False

        self.logger = loggger if loggger else default_logger

    @override
    def _start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    @override
    def _destroy(self) -> None:
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            # 唤醒事件循环，避免 join 阶段阻塞过久。
            self._loop.call_soon_threadsafe(lambda: None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @override
    def _pause(self) -> None:
        self._paused = not self._paused
        self._running = not self._paused

    @override
    def _resume(self) -> None:
        self._paused = False
        self._running = True

    # def _notify_subscribers(self, item: NewsItem) -> None:
    #     for callback in self._subscribers:
    #         try:
    #             callback(item)
    #         except Exception as err:
    #             self.logger.error(
    #                 f"failed to run callback {callback}: {err}", exc_info=True
    #             )

    def _run_loop(self):
        """在线程内创建独立事件循环，专门处理 websocket 协程"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_forever())
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_forever(self):
        """主连接循环：断线自动重连，直到 stop_event 被设置。"""
        while not self._stop_event.is_set():
            try:
                # 使用库内置 ping 保活，降低长连接被网关回收概率。
                async with websockets.connect(
                    self.WSS_URL, ping_interval=20, ping_timeout=20
                ) as ws:
                    await self._send_enter_channel(ws)
                    await self._consume_messages(ws)
            except (
                ConnectionClosed,
                OSError,
                TimeoutError,
                websockets.WebSocketException,
            ) as err:
                if self._stop_event.is_set():
                    break
                self.logger.warning(
                    f"[wallstreet] 连接断开，{self.reconnect_delay:.0f}s 后重连: {err}"
                )
                await asyncio.sleep(self.reconnect_delay)
            except Exception as err:
                if self._stop_event.is_set():
                    break
                self.logger.error(
                    f"[wallstreet] 未知错误，{self.reconnect_delay:.0f}s 后重连: {err}"
                )
                await asyncio.sleep(self.reconnect_delay)

    async def _send_enter_channel(self, ws: ClientConnection):
        """发送订阅命令，协议与前端页面保持一致。"""
        payload = {
            "command": "ENTER_CHANNEL",
            "data": {"chann_name": "live", "cursor": self.cursor},
        }
        await ws.send(json.dumps(payload, ensure_ascii=False))

    async def _consume_messages(self, ws: ClientConnection):
        """消费 websocket 消息流并分发到解析逻辑。"""
        async for raw in ws:
            if self._stop_event.is_set():
                break
            if not self._running:
                continue

            if not isinstance(raw, str):
                continue
            self._handle_raw_message(raw)

    def _handle_raw_message(self, raw: str):
        """解析原始 JSON 消息并提取新闻列表"""
        try:
            message = json.loads(raw)
            self.logger.debug(
                f"[华尔街见闻]: {json.dumps(message, ensure_ascii=False)}"
            )
            # news_file = "packages/stock_helper/data/wallstreet.jsonl"
            # os.makedirs(os.path.dirname(news_file), exist_ok=True)
            # with open(news_file, "a", encoding="utf-8") as f:
            #     f.write(json.dumps(message, ensure_ascii=False) + "\n")
        except json.JSONDecodeError:
            return

        if not isinstance(message, dict):
            return

        next_cursor = message.get("next_cursor")
        if isinstance(next_cursor, str) and next_cursor:
            # 持续更新 cursor，供断线重连后续拉。
            self.cursor = next_cursor

        msg_type: str = message.get("type", "")
        content: Union[Dict[str, Any], List[Dict[str, Any]]] = message.get(
            "content", {}
        )
        if msg_type == "STREAM" and isinstance(content, dict):
            items = [content]
        elif isinstance(content, list):
            items = [item for item in content if isinstance(item, dict)]
        else:
            items = []

        for item in items:
            self._handle_news_item(item)

    def _handle_news_item(self, item: Dict[str, Any]):
        """对单条新闻做过滤、格式化和输出。"""
        item_id = item.get("id")
        if not isinstance(item_id, int):
            return
        # 先做去重，防止重放消息导致重复输出。
        if self._is_seen(item_id):
            return

        item_channels = item.get("channels") or []
        if self.channels and isinstance(item_channels, list):
            if not any(ch in self.channels for ch in item_channels):
                return

        op_name = item.get("op_name", "create")
        # 删除类型通常用于前端列表同步，抓取场景可忽略。
        if op_name not in {"create", "update", "reorder"}:
            return

        text = self._format_item(item)
        metadata = {
            "type": "wallstreet",
            "id": item_id,
            "op_name": op_name,
            "channels": item_channels,
            "raw": item,
        }
        display_time = item.get("display_time") or item.get("created_at")
        normalized_displaytime = self._normalize_displaytime(display_time)
        source_url = f"https://wallstreetcn.com/livenews/{item_id}"
        score = item.get("score")
        importance = int(score) if isinstance(score, (int, float)) else None

        news_item = NewsItem(
            news_id=item_id,
            content=(item.get("content_text") or item.get("content") or "").strip()
            or text,
            news_time=normalized_displaytime,
            source_type=NewsSourceType.WALLSTREET,
            title=(item.get("title") or None),
            source_name=(item.get("uri") or None),
            source_url=source_url,
            importance=importance,
            channels=item_channels if isinstance(item_channels, list) else None,
            content_html=(
                item.get("content") if isinstance(item.get("content"), str) else None
            ),
            content_extended=(
                item.get("content_more")
                if isinstance(item.get("content_more"), str)
                else None
            ),
            metadata=metadata,
        )

        self._notify_subscribers(news_item)
        self.logger.debug(text, metadata)
        self._mark_seen(item_id)

    def _format_item(self, item: Dict[str, Any]) -> str:
        """把新闻结构化字段格式化成可读文本。"""
        title = (item.get("title") or "").strip()
        content_text = (item.get("content_text") or item.get("content") or "").strip()
        if isinstance(content_text, dict):
            # 避免字段异常时崩溃，降级为 JSON 字符串展示。
            content_text = json.dumps(content_text, ensure_ascii=False)

        timestamp = item.get("display_time") or item.get("created_at") or ""
        human_time = self._format_time(timestamp)
        news_id = item.get("id")
        source_url = (
            f"https://wallstreetcn.com/live/global#{news_id}" if news_id else ""
        )

        body = content_text if content_text else title
        if title and content_text and title != content_text:
            body = f"【{title}】\n{content_text}"

        suffix = f"\n[华尔街见闻 - {human_time}]"
        if source_url:
            suffix = f"（{source_url}）{suffix}"
        return f"{body}{suffix}"

    def _format_time(self, value: Any) -> str:
        """时间字段容错处理：支持时间戳/字符串/未知值。"""
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, OSError):
                return str(value)
        if isinstance(value, str):
            return value
        return "unknown"

    def _normalize_displaytime(self, value: Any) -> datetime:
        """把 Wallstreet 时间字段统一转换为 datetime。"""
        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value))
            except (ValueError, OSError):
                return datetime.now()

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return datetime.now()
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                try:
                    return datetime.fromisoformat(text.replace(" ", "T"))
                except ValueError:
                    return datetime.now()

        return datetime.now()

    def _is_seen(self, item_id: int) -> bool:
        """判断新闻 id 是否已处理过。"""
        return item_id in self._seen_set

    def _mark_seen(self, item_id: int):
        """记录已处理新闻 id，并按上限淘汰最旧记录。"""
        if item_id in self._seen_set:
            return
        if len(self._seen_ids) == self._seen_ids.maxlen:
            oldest = self._seen_ids[0]
            self._seen_set.discard(oldest)
        self._seen_ids.append(item_id)
        self._seen_set.add(item_id)


class WallstreetMockFetcher(WallstreetLiveFetcher):
    """
    基于 JSONL 文件的模拟数据回放器。

    可用于测试和开发，从 wallstreet.jsonl 文件中读取历史数据并模拟实时推送。
    支持循环播放、随机顺序、控制推送速度等功能。
    """

    mock_file: str
    """Mock 数据文件路径"""

    replay_interval: float
    """每条消息之间的间隔时间（秒），默认 1.0 秒"""

    loop_replay: bool
    """是否循环播放数据，默认 True"""

    shuffle: bool
    """是否随机打乱播放顺序，默认 False"""

    max_items: Optional[int]
    """最多播放的消息数量，None 表示不限制"""

    def __init__(
        self,
        *,
        mock_file: str = str(
            Path(__file__).resolve().parents[3] / "data/wallstreet.jsonl"
        ),
        replay_interval: float = 1.0,
        loop_replay: bool = True,
        shuffle: bool = False,
        max_items: Optional[int] = None,
        channels: Optional[Iterable[str]] = None,
        dedup_size: int = 2000,
        loggger: Optional[Logger] = None,
    ):
        super().__init__(
            cursor="",
            channels=channels,
            reconnect_delay=0,
            dedup_size=dedup_size,
            loggger=loggger,
        )
        self.mock_file = mock_file
        self.replay_interval = replay_interval
        self.loop_replay = loop_replay
        self.shuffle = shuffle
        self.max_items = max_items

    def _run_loop(self):
        """覆写父类方法，使用同步方式播放 mock 数据"""
        self._replay_from_file()

    def _replay_from_file(self):
        """从 JSONL 文件读取并回放数据"""
        file_path = Path(self.mock_file)

        if not file_path.exists():
            self.logger.error(f"[wallstreet-mock] Mock 文件不存在: {self.mock_file}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                messages = [line.strip() for line in f if line.strip()]

            if not messages:
                self.logger.warning(
                    f"[wallstreet-mock] Mock 文件为空: {self.mock_file}"
                )
                return

            self.logger.info(
                f"[wallstreet-mock] 加载 {len(messages)} 条消息，"
                f"间隔 {self.replay_interval}s，循环播放: {self.loop_replay}"
            )

            items_sent = 0

            while not self._stop_event.is_set():
                # 准备本轮要播放的消息
                current_messages = messages.copy()
                if self.shuffle:
                    random.shuffle(current_messages)

                for raw_message in current_messages:
                    if self._stop_event.is_set():
                        break

                    if self._paused:
                        time.sleep(0.1)
                        continue

                    # 检查是否达到最大条数
                    if self.max_items is not None and items_sent >= self.max_items:
                        self.logger.info(
                            f"[wallstreet-mock] 已达到最大推送条数 {self.max_items}，停止播放"
                        )
                        self._stop_event.set()
                        break

                    # 处理消息
                    self._handle_raw_message(raw_message)
                    items_sent += 1

                    # 等待下一条
                    if not self._stop_event.wait(self.replay_interval):
                        continue
                    else:
                        break

                # 如果不循环播放，退出
                if not self.loop_replay:
                    self.logger.info(
                        f"[wallstreet-mock] 播放完成，共 {items_sent} 条消息"
                    )
                    break

        except Exception as e:
            self.logger.error(f"[wallstreet-mock] 回放失败: {e}")

    def _handle_raw_message(self, raw: str):
        """
        覆写父类方法，处理 mock 数据时不再写入文件。
        Mock 模式下只解析和输出，不记录到 JSONL。
        """
        try:
            message = json.loads(raw)
            self.logger.debug(
                f"[wallstreet-mock] 播放消息: {json.dumps(message, ensure_ascii=False)[:100]}..."
            )
        except json.JSONDecodeError:
            return

        if not isinstance(message, dict):
            return

        # 提取新闻内容
        content = message.get("content", {})
        if isinstance(content, dict):
            items = [content]
        elif isinstance(content, list):
            items = [item for item in content if isinstance(item, dict)]
        else:
            items = []

        for item in items:
            self._handle_news_item(item)


def main():
    """命令行入口：用于本地快速验证实时抓取效果。"""
    parser = argparse.ArgumentParser(description="华尔街见闻实时快讯抓取")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用 mock 模式从 JSONL 文件回放数据",
    )
    parser.add_argument(
        "--mock-file",
        type=str,
        default=str(Path(__file__).resolve().parents[3] / "data/wallstreet.jsonl"),
        help="Mock 数据文件路径",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Mock 模式下每条消息的间隔时间（秒）",
    )
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="Mock 模式下不循环播放",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Mock 模式下随机打乱播放顺序",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Mock 模式下最多播放的消息数量",
    )
    parser.add_argument(
        "--channel",
        action="append",
        default=["global-channel"],
        help="频道名，可重复传参（示例：--channel a-stock-channel）",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="运行秒数，0 表示持续运行直到 Ctrl+C",
    )
    args = parser.parse_args()

    if args.mock:
        # Mock 模式
        fetcher = WallstreetMockFetcher(
            mock_file=args.mock_file,
            replay_interval=args.interval,
            loop_replay=not args.no_loop,
            shuffle=args.shuffle,
            max_items=args.max_items,
            channels=args.channel,
        )
        print(f"Wallstreet Mock 模式已启动（文件: {args.mock_file}），按 Ctrl+C 退出。")
    else:
        # 实时模式
        fetcher = WallstreetLiveFetcher(channels=args.channel)
        print("Wallstreet 实时快讯已启动，按 Ctrl+C 退出。")

    fetcher.start()

    try:
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止 Wallstreet 快讯...")
    finally:
        fetcher.destroy()
        print("Wallstreet 快讯已停止")


if __name__ == "__main__":
    main()
