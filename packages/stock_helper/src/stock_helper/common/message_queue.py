"""
通用消息队列接口及内存实现

提供泛型消息队列抽象，屏蔽底层队列实现差异（内存/Redis/Kafka 等），
默认实现基于 Python 内置 queue.Queue。
"""

import queue
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class QueueFullError(Exception):
    """队列已满时抛出"""


class QueueEmptyError(Exception):
    """队列为空且超时时抛出"""


class MessageQueue(ABC, Generic[T]):
    """
    抽象消息队列接口。

    子类需实现 put_nowait、get、qsize、task_done 四个方法，
    以适配不同的底层队列实现。
    """

    @abstractmethod
    def put_nowait(self, item: T) -> None:
        """
        非阻塞投递消息。

        :raises QueueFullError: 队列已满时抛出
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, timeout: float = 1.0) -> T:
        """
        阻塞获取消息，超时后抛出 QueueEmptyError。

        :param timeout: 等待超时秒数
        :raises QueueEmptyError: 超时未获取到消息时抛出
        """
        raise NotImplementedError

    @abstractmethod
    def qsize(self) -> int:
        """返回队列当前元素数量"""
        raise NotImplementedError

    @abstractmethod
    def task_done(self) -> None:
        """标记一个已获取的任务处理完成（用于 join 同步）"""
        raise NotImplementedError


class InMemoryQueueAdapter(MessageQueue[T]):
    """
    基于 queue.Queue 的内存消息队列实现。

    :param maxsize: 队列最大容量，0 表示无限制
    """

    def __init__(self, maxsize: int = 0) -> None:
        self._q: queue.Queue[T] = queue.Queue(maxsize=maxsize)

    def put_nowait(self, item: T) -> None:
        try:
            self._q.put_nowait(item)
        except queue.Full as e:
            raise QueueFullError(str(e)) from e

    def get(self, timeout: float = 1.0) -> T:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty as e:
            raise QueueEmptyError(str(e)) from e

    def qsize(self) -> int:
        return self._q.qsize()

    def task_done(self) -> None:
        self._q.task_done()
