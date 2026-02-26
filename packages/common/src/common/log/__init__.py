"""
common.log - 日志子模块

导出 Logger 协议与 get_logger 工厂函数，方便其他模块直接使用。

示例::

    from common.log import Logger, get_logger

    logger: Logger = get_logger(__name__)
    logger.info("hello")
"""

from common.log.factory import get_logger
from common.log.interface import Logger

__all__ = ["Logger", "get_logger"]
