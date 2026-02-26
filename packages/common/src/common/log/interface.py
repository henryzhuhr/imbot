"""
日志接口
定义通用日志接口协议，兼容 Python 标准 logging.Logger 及 loguru 等主流日志库。
"""

from typing import Any, Protocol, overload, runtime_checkable


@runtime_checkable
class Logger(Protocol):
    """
    通用日志接口协议。

    兼容 Python 内置 logging.Logger 与 loguru.logger，
    只需实现 debug / info / warning / error / exception 五个方法即可通过类型检查。
    """

    @overload
    def debug(__self, __message: str, *args: Any, **kwargs: Any) -> None: ...

    @overload
    def debug(__self, __message: Any) -> None: ...

    @overload
    def info(__self, __message: str, *args: Any, **kwargs: Any) -> None: ...

    @overload
    def info(__self, __message: Any) -> None: ...

    @overload
    def warning(__self, __message: str, *args: Any, **kwargs: Any) -> None: ...

    @overload
    def warning(__self, __message: Any) -> None: ...

    @overload
    def error(__self, __message: str, *args: Any, **kwargs: Any) -> None: ...

    @overload
    def error(__self, __message: Any) -> None: ...
