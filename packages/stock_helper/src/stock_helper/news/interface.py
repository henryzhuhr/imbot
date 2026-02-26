"""
快讯服务类的接口，用于获取实时快讯信息
"""

import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Dict, List, Optional, Union

from common.log import Logger
from pydantic import BaseModel, ConfigDict, Field, field_validator
from stock_helper.common.message_queue import (
    InMemoryQueueAdapter,
    MessageQueue,
    QueueEmptyError,
    QueueFullError,
)


class NewsSourceType(StrEnum):
    """新闻源类型标识，表示从哪个网站获取的快讯"""

    JIN10 = "jin10"
    WALLSTREET = "wallstreet"


class NewsItem(BaseModel):
    """
    统一的新闻快讯数据模型，支持多种新闻源（Jin10、华尔街见闻等）。

    设计原则：
    - 核心字段必填，扩展字段可选
    - 灵活的类型支持跨源兼容性
    - 保留完整元数据，避免信息丢失
    - 使用 Field 约束确保数据质量
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "20260213234208900800",
                    "content": "美国最高法院宣布2月20日将公布意见",
                    "timestamp": "2026-02-13 23:42:08",
                    "source_type": "jin10",
                    "title": None,
                    "importance": 1,
                    "channels": [1, 2, 3],
                    "tags": [],
                    "metadata": {"action": 1, "type": 0},
                },
                {
                    "id": 3055296,
                    "content": "欧洲STOXX 600指数初步收跌0.08%，报618.01点",
                    "timestamp": 1771000258,
                    "source_type": "wallstreet",
                    "title": "欧股收盘",
                    "source_url": "https://wallstreetcn.com/livenews/3055296",
                    "importance": 1,
                    "channels": ["global-channel", "forex-channel"],
                    "content_html": "<p>欧洲STOXX 600指数...</p>",
                    "metadata": {"op_name": "create", "op_id": 11806974, "score": 1},
                },
            ]
        }
    )

    # ==================== 核心字段（必填） ====================

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="内部唯一标识符（UUID），自动生成，用于数据库主键和去重",
        frozen=True,  # 创建后不可修改
    )

    news_id: Union[str, int] = Field(description="新闻源的原始 ID，保留原始格式")

    content: str = Field(description="新闻内容")

    news_time: datetime = Field(description="显示时间（已标准化为 datetime 对象）")

    source_type: NewsSourceType = Field(description="新闻源类型标识")

    # ==================== 可选字段（常用） ====================

    title: Optional[str] = Field(default=None, description="新闻标题")

    source_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="原始来源名称（如媒体机构）",
        examples=["新华社", "Bloomberg", "Reuters", None],
    )

    source_url: Optional[str] = Field(default=None, description="新闻原文链接（URL）")

    # ==================== 重要性与分类 ====================

    importance: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="重要性评分（0-10），Jin10: 0/1，Wallstreet: 1/2",
    )

    channels: Optional[List[Union[str, int]]] = Field(
        default=None,
        max_length=50,
        description="频道/分类列表，Jin10 使用数字，Wallstreet 使用字符串",
        examples=[[1, 2, 3], ["global-channel", "us-stock-channel"], None],
    )

    tags: Optional[List[str]] = Field(
        default=None,
        max_length=100,
        description="内容标签列表，用于过滤和搜索",
        examples=[["股市", "美股"], ["CPI", "通胀"], None],
    )

    # ==================== 扩展内容 ====================

    content_html: Optional[str] = Field(
        default=None,
        max_length=100000,
        description="HTML 格式的内容（Wallstreet 提供）",
        examples=["<p>德国DAX 30指数初步收涨0.27%...</p>", None],
    )

    content_extended: Optional[str] = Field(
        default=None,
        max_length=100000,
        description="扩展内容/全文（Wallstreet 的 content_more 字段）",
        examples=["此次接入标志着百度App打通「百度生态+本地个人助理」全链路...", None],
    )

    # ==================== 灵活扩展 ====================

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="源特定的元数据字段（可扩展），Jin10: action/type/remark，Wallstreet: op_name/op_id/article",
        examples=[
            {"action": 1, "type": 0, "remark": []},
            {"op_name": "create", "op_id": 11806974, "score": 1},
        ],
    )

    # ==================== 字段验证器 ====================

    @field_validator("news_time", mode="before")
    @classmethod
    def validate_news_time(cls, v: Union[datetime, int, str]) -> datetime:
        """
        验证并转换显示时间字段为 datetime 对象

        支持格式：
        - datetime 对象：直接返回
        - 整数（Unix 时间戳）：转换为 datetime
        - 字符串（ISO 8601 格式）：直接解析
        - 字符串（Jin10 格式："2026-02-13 23:42:08"）：转换为 datetime

        :param v: 输入的显示时间字段值
        :return: 标准化后的 datetime 对象
        :raises ValueError: 如果输入值无法解析为有效时间戳
        """
        if isinstance(v, datetime):
            return v
        elif isinstance(v, int):
            return datetime.fromtimestamp(v)
        elif isinstance(v, str):
            # 尝试多种格式
            try:
                # ISO 格式: "2026-02-13T23:42:08"
                return datetime.fromisoformat(v)
            except ValueError:
                try:
                    # Jin10 格式: "2026-02-13 23:42:08"
                    return datetime.fromisoformat(v.replace(" ", "T"))
                except ValueError:
                    raise ValueError(f"failed to parse displaytime from string: {v}")
        else:
            raise ValueError(f"unsupported type for displaytime: {type(v)}")


class NewsFetcher(ABC):
    """
    快讯服务抽象接口，支持主动拉取和推送监听两种模式。

    实现建议：
    - start/destroy/pause 方法是必须的生命周期方法
    - fetch_latest 适用于支持主动拉取的源（可选实现）
    - subscribe 适用于实时推送的源（可选实现）
    """

    logger: Logger
    """注入的日志接口实例，用于输出日志信息，需实现 Logger 接口"""

    _subscribers: List[Callable[[NewsItem], None]]
    """内部维护的订阅者列表，存储回调函数，当有新快讯时调用这些函数进行分发"""

    _message_queue: MessageQueue["NewsItem"]
    """内部消息队列，默认使用 InMemoryQueueAdapter 进行异步处理新闻分发"""

    _worker_thread: threading.Thread
    """后台线程对象，负责从队列中消费新闻并分发给订阅者"""

    _running: bool
    """运行标志，用于控制后台线程的生命周期"""

    def __init__(
        self,
        logger: Optional[Logger] = None,
        message_queue: Optional[MessageQueue["NewsItem"]] = None,
    ) -> None:
        if logger:
            self.logger = logger
        else:
            import logging

            self.logger = logging.getLogger(__name__)
        self._subscribers: List[Callable[[NewsItem], None]] = []
        self._message_queue = message_queue or InMemoryQueueAdapter(maxsize=100)
        self._worker_thread = threading.Thread(
            target=self._notify_subscribers_loop, daemon=True
        )
        self._running = False

    # ==================== 生命周期管理（必须实现） ====================

    def start(self) -> None:
        """
        调用子类实现的 `_start` 方法启动连接，设置运行标志，并启动后台线程。
        """
        self._start()
        self._running = True
        self._worker_thread.start()

    @abstractmethod
    def _start(self) -> None:
        """
        启动底层连接（WebSocket、长轮询等）

        此方法应该：
        - 设置运行标志 self._running = True
        - 建立网络连接
        - 启动后台线程/任务
        - 初始化必要的资源
        """
        raise NotImplementedError("_start method must be implemented by subclass")

    def destroy(self) -> None:
        """
        设置运行标志，等待后台线程退出，并调用子类自定义的 `_destroy` 进行资源清理。
        """
        self._running = False
        self._worker_thread.join(timeout=2)
        self._destroy()

    @abstractmethod
    def _destroy(self) -> None:
        """
        彻底关闭连接并释放资源

        此方法应该：
        - 关闭所有网络连接
        - 停止后台线程/任务
        - 清理临时资源
        """
        raise NotImplementedError("_destroy method must be implemented by subclass")

    def pause(self) -> None:
        """
        设置暂停标志，调用子类实现的 `_pause` 方法切换暂停状态
        """
        self._running = False
        self._pause()

    @abstractmethod
    def _pause(self) -> None:
        """
        暂停/恢复接收新消息（保持连接）
        """
        raise NotImplementedError("_pause method must be implemented by subclass")

    def resume(self) -> None:
        """
        设置暂停标志，调用子类实现的 `_resume` 方法切换暂停状态
        """
        self._resume()
        self._running = True

    @abstractmethod
    def _resume(self) -> None:
        """
        恢复接收新消息（保持连接）
        """
        raise NotImplementedError("_resume method must be implemented by subclass")

    # ==================== 主动拉取模式（可选实现） ====================

    def fetch_latest(self, limit: int = 10) -> List[NewsItem]:
        """
        主动拉取最新快讯（适用于支持 HTTP API 的源）

        Args:
            limit: 返回的最大新闻条数

        Returns:
            List[NewsItem]: 新闻列表（如不支持则返回空列表）

        Note:
            如果数据源不支持主动拉取（如纯 WebSocket 推送），
            默认实现返回空列表，子类无需覆写。
        """
        return []

    # ==================== 推送/监听模式（可选实现） ====================

    def subscribe(self, callback: Callable[[NewsItem], None]) -> None:
        """
        订阅实时快讯推送（适用于 WebSocket/SSE 等推送源）

        Args:
            callback: 当有新快讯时被调用，参数为单条 NewsItem 对象
        """
        self._subscribers.append(callback)

    def _notify_subscribers(self, item: NewsItem) -> None:
        """将消息投递到内部队列，由后台线程统一分发。"""
        try:
            self._message_queue.put_nowait(item)
        except QueueFullError:
            self.logger.warning("news queue is full, dropping item")

    def _notify_subscribers_loop(self) -> None:
        """向所有订阅者分发标准化新闻对象的后台线程函数"""
        while self._running or self._message_queue.qsize() > 0:
            try:
                item = self._message_queue.get(timeout=1)
                for callback in self._subscribers:
                    try:
                        callback(item)
                    except Exception as e:
                        self.logger.error(
                            f"failed to run callback {callback}: {e}", exc_info=True
                        )
                self._message_queue.task_done()
            except QueueEmptyError:
                continue


class NewsConsumer(ABC):
    """
    快讯消费者抽象接口，定义处理快讯的统一方法。

    实现建议：
    - consume 方法是必须实现的核心方法
    - 可以根据需要添加其他辅助方法（如过滤、分类等）
    """

    @abstractmethod
    def consume(self, item: NewsItem) -> None:
        """
        处理接收到的快讯消息

        Args:
            item: 标准化的 NewsItem 对象

        Note:
            具体实现可以是打印、存储、触发其他事件等。
        """
        raise NotImplementedError("consume method must be implemented by subclass")
