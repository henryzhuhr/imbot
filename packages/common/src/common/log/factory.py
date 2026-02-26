"""
日志工厂
通过 Python 标准库 logging 创建满足 Logger 协议的日志实例。

用法::

    from common.log import get_logger

    logger = get_logger(__name__)
    logger.info("启动中…")
"""

import logging
import sys
from typing import IO

_DEFAULT_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def get_logger(
    name: str,
    level: int = logging.DEBUG,
    fmt: str = _DEFAULT_FMT,
    date_fmt: str = _DEFAULT_DATE_FMT,
    stream: IO[str] | None = None,
) -> logging.Logger:
    """
    获取一个命名日志实例。

    若同名 logger 已配置过 handler，则直接返回，避免重复添加。

    Args:
        name:     日志名称，推荐传入 ``__name__``。
        level:    日志级别，默认 DEBUG。
        fmt:      日志格式字符串。
        date_fmt: 时间格式字符串。
        stream:   输出流，默认 sys.stderr。

    Returns:
        标准库 logging.Logger 实例，满足 ``Logger`` 协议。
    """
    logger = logging.getLogger(name)

    # 已有 handler 则不重复添加
    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))

    logger.addHandler(handler)
    # 不向 root logger 传播，避免重复输出
    logger.propagate = False

    return logger
