"""
金十快讯服务类
用于从金十网站获取实时快讯信息，包括全球财经新闻和经济数据

l.m && (window.flashServer.vip_news2 = ["wss://test-wss-jin10-vip-flash-1.jin10.com/"],
window.flashServer.news2 = ["wss://test-wss-jin10-flash-1.jin10.com/"],
window.flashServer.classify_news = ["wss://classify-testing.jin10.com/"]);
"""

import argparse
import asyncio
import json
import os
import random
import struct
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import websockets
from common.log import Logger
from pydantic import BaseModel, Field
from websockets import ClientConnection
from websockets.exceptions import ConnectionClosed

from .interface import NewsFetcher, NewsItem, NewsSourceType


class _Jin10BinaryReader:
    """金十二进制协议读取器（对应前端 Ge.r16L/rU16L/rStrL）。"""

    _data: bytes
    _pos: int

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read_i16_le(self) -> int:
        value = struct.unpack_from("<h", self._data, self._pos)[0]
        self._pos += 2
        return value

    def read_i32_le(self) -> int:
        value = struct.unpack_from("<i", self._data, self._pos)[0]
        self._pos += 4
        return value

    def read_u32_le(self) -> int:
        value = struct.unpack_from("<I", self._data, self._pos)[0]
        self._pos += 4
        return value

    def read_u16_le(self) -> int:
        value = struct.unpack_from("<H", self._data, self._pos)[0]
        self._pos += 2
        return value

    def read_str_u16_len(self) -> str:
        size = self.read_u16_le()
        payload = self._data[self._pos : self._pos + size]
        self._pos += size
        return payload.decode("utf-8", errors="replace")


class _Jin10BinaryWriter:
    """金十二进制协议写入器（对应前端 Ge.w16L/w32L/wStrL）。"""

    _buf: bytearray

    def __init__(self):
        self._buf = bytearray()

    def write_i16_le(self, value: int):
        self._buf += struct.pack("<h", int(value))

    def write_i32_le(self, value: int):
        self._buf += struct.pack("<i", int(value))

    def write_u16_le(self, value: int):
        self._buf += struct.pack("<H", int(value))

    def write_str_u16_len(self, value: str):
        payload = value.encode("utf-8")
        self.write_u16_le(len(payload))
        self._buf += payload

    def to_bytes(self) -> bytes:
        return bytes(self._buf)


class Jin10MessageType:
    """金十前端常量（来自 jin10.js）"""

    MSG_NEWS_FLASH = 1000
    MSG_EVENTS_FLASH = 1001
    MSG_VOICE_NEWS = 1002
    MSG_OPINION_NEWS = 1003
    MSG_TOP_LIST = 1005
    MSG_VIP_NEWS_FLASH = 1100
    MSG_LAST_NEWS_LIST = 1200
    """历史消息列表"""
    MSG_HEARTBEAT = 1201
    MSG_USER_LOGIN_NEWS = 4002


class Jin10PayloadData(BaseModel):
    model_config = {"extra": "allow"}

    content: str = Field(default="", description="新闻内容，可能包含 HTML 标签")
    pic: str = Field(default="", description="图片链接")
    title: str = Field(default="", description="新闻标题")
    source: str = Field(default="", description="来源名称")
    source_link: str = Field(default="", description="来源链接")


class Jin10Payload(BaseModel):
    model_config = {"extra": "allow", "populate_by_name": True}

    type: Optional[int] = Field(None, description="消息类型，数值含义不固定")
    id: Optional[str] = Field(default=None, description="消息 ID")
    time: Optional[str] = Field(
        default=None, description="消息时间，YYYY-MM-DD HH:MM:SS"
    )
    data: Optional[Jin10PayloadData] = Field(
        default=None, description="消息数据体，包含内容、图片、标题等"
    )
    important: Optional[int] = Field(default=None, description="重要性，0 或 1")
    tags: Optional[List[Any]] = Field(
        default=None, description="标签列表，元素类型不固定"
    )
    remark: Optional[List[Any]] = Field(
        default=None, description="备注信息，类型不固定"
    )
    extras: Optional[Dict[str, Any]] = Field(
        default=None, description="附加信息，类型不固定"
    )
    channel: Optional[List[Union[str, int]]] = Field(
        default=None, description="频道列表，元素类型不固定"
    )
    channels: Optional[List[Union[str, int]]] = Field(
        default=None, description="频道列表，元素类型不固定"
    )
    action: Optional[int] = Field(default=None, description="动作类型，数值含义不固定")
    m_type: Optional[int] = Field(default=None, description="消息类型，数值含义不固定")
    category: Optional[str] = Field(default=None, description="消息分类")
    content: Optional[str] = Field(default=None, description="消息内容")
    title: Optional[str] = Field(default=None, description="消息标题")
    source: Optional[str] = Field(default=None, description="消息来源")
    source_link: Optional[str] = Field(default=None, description="消息来源链接")
    only_online: Optional[bool] = Field(default=None, description="是否仅在线")
    kinds: Optional[List[Any]] = Field(default=None, description="消息类型列表")
    origin: Optional[Dict[str, Any]] = Field(default=None, alias="_origin")


class Jin10Message(BaseModel):
    """金十消息解析模型。"""

    source_type: str = Field(description="消息来源类型")
    payload: Jin10Payload = Field(description="原始消息体")

    @classmethod
    def from_payload(
        cls, payload: Dict[str, Any], source_type: str
    ) -> Optional["Jin10Message"]:
        if not isinstance(payload, dict):
            return None

        normalized = (
            payload.get("_origin")
            if isinstance(payload.get("_origin"), dict)
            else payload
        )
        if not isinstance(normalized, dict):
            return None

        parsed = Jin10Payload.model_validate(normalized)
        if parsed.action == 3:
            return None

        return cls(source_type=source_type, payload=parsed)

    def to_news_item(self) -> NewsItem:
        payload_dict = self.payload.model_dump(mode="python", by_alias=True)
        data_dict = (
            payload_dict.get("data")
            if isinstance(payload_dict.get("data"), dict)
            else {}
        )
        extras_dict = (
            payload_dict.get("extras")
            if isinstance(payload_dict.get("extras"), dict)
            else {}
        )

        news_id = self._extract_news_id(payload_dict, extras_dict)
        news_time = self._extract_news_time(payload_dict, news_id)
        title = self._extract_title(payload_dict, data_dict)
        content = self._extract_content(payload_dict, data_dict, title)
        importance = self._extract_importance(payload_dict, data_dict)
        channels = self._extract_channels(payload_dict, data_dict)

        return NewsItem(
            news_id=news_id,
            content=content,
            news_time=news_time,
            source_type=NewsSourceType.JIN10,
            title=title,
            source_name=self._extract_source_name(payload_dict, data_dict),
            source_url=self._extract_source_url(payload_dict, data_dict, extras_dict),
            importance=importance,
            channels=channels,
            metadata={
                "type": "jin10",
                "source_type": self.source_type,
                "raw": payload_dict,
            },
        )

    @staticmethod
    def _extract_news_id(payload: Dict[str, Any], extras: Dict[str, Any]) -> str:
        raw = payload.get("id") or extras.get("flash_id")
        if raw is None:
            return f"jin10-{int(time.time() * 1000)}"
        return str(raw)

    @staticmethod
    def _extract_news_time(
        payload: Dict[str, Any], news_id: str
    ) -> datetime | str | int:
        raw_time = payload.get("time")
        if isinstance(raw_time, str) and raw_time.strip():
            return raw_time
        if isinstance(raw_time, (int, float)):
            return int(raw_time)

        digits = "".join(ch for ch in news_id if ch.isdigit())
        if len(digits) >= 14:
            try:
                return datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _extract_title(payload: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
        for value in (payload.get("title"), data.get("title")):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_content(
        payload: Dict[str, Any], data: Dict[str, Any], title: Optional[str]
    ) -> str:
        for value in (
            data.get("content"),
            payload.get("content"),
            data.get("content_text"),
            payload.get("content_text"),
            title,
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _extract_importance(
        payload: Dict[str, Any], data: Dict[str, Any]
    ) -> Optional[int]:
        value = payload.get("important")
        if value is None:
            value = data.get("important")
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _extract_channels(
        payload: Dict[str, Any], data: Dict[str, Any]
    ) -> Optional[List[Union[str, int]]]:
        for key in ("channel", "channels"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            value = data.get(key)
            if isinstance(value, list):
                return value
        return None

    @staticmethod
    def _extract_source_name(
        payload: Dict[str, Any], data: Dict[str, Any]
    ) -> Optional[str]:
        for value in (data.get("source"), payload.get("source")):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_source_url(
        payload: Dict[str, Any], data: Dict[str, Any], extras: Dict[str, Any]
    ) -> Optional[str]:
        for value in (
            data.get("source_link"),
            payload.get("source_link"),
            extras.get("url"),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


# class Jin10Message(BaseModel):
#     """金十消息模型，包含了从原始数据中解析出的核心字段和元数据"""

#     source_type: str = Field(
#         ...,
#         description="消息来源类型，如 'flash', 'vip_flash', 'event', 'top_list', 'login' 等",
#     )
#     payload: Jin10Payload = Field(
#         default_factory=Jin10Payload, description="原始消息体"
#     )
#     # flash_id: Optional[int] = Field(default=None, description="金十原始快讯 ID")
#     # action: Optional[int] = Field(default=None, description="动作类型，3 表示删除")
#     # content: str = Field(default="", description="标准化后的文本内容")
#     # news_time: Union[str, int] = Field(default="unknown", description="标准化时间字段")
#     # title: Optional[str] = Field(default=None, description="消息标题")
#     # source_name: Optional[str] = Field(default=None, description="来源名称")
#     # source_url: Optional[str] = Field(default=None, description="来源链接")
#     # importance: Optional[int] = Field(default=None, description="重要性")
#     # channels: Optional[List[Union[str, int]]] = Field(default=None, description="频道")
#     # tags: Optional[List[str]] = Field(default=None, description="标签")
#     # content_html: Optional[str] = Field(default=None, description="HTML 内容")
#     # content_extended: Optional[str] = Field(default=None, description="扩展内容")
#     # metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

#     @classmethod
#     def from_payload(
#         cls, payload: Dict[str, Any], source_type: str
#     ) -> Optional["Jin10Message"]:
#         if not isinstance(payload, dict):
#             return None

#         normalized = (
#             payload.get("_origin")
#             if isinstance(payload.get("_origin"), dict)
#             else payload
#         )
#         if not isinstance(normalized, dict):
#             return None

#         payload_model = cls.Jin10Payload.model_validate(normalized)
#         payload_dict = payload_model.model_dump(mode="python", by_alias=True)
#         data_dict = payload_model.data.model_dump(mode="python", by_alias=True)
#         extras_dict = payload_model.extras or {}

#         action = payload_model.action
#         if action == 3:
#             return None

#         flash_id = cls._extract_flash_id(payload_dict, data_dict, extras_dict)
#         content = cls._extract_content(payload_dict, data_dict)
#         if not content:
#             return None

#         news_time = cls._extract_time(payload_dict, data_dict, flash_id)
#         channels = cls._extract_channels(payload_dict, data_dict)
#         tags = cls._extract_tags(payload_dict, data_dict)
#         source_url = cls._extract_source_url(payload_dict, data_dict, extras_dict)
#         source_name = cls._extract_source_name(payload_dict, data_dict)
#         importance = cls._extract_importance(payload_dict, data_dict)
#         title = cls._extract_title(payload_dict, data_dict)

#         return cls(
#             source_type=source_type,
#             payload=payload_model,
#             flash_id=flash_id,
#             action=action if isinstance(action, int) else None,
#             content=content,
#             news_time=news_time,
#             title=title,
#             source_name=source_name,
#             source_url=source_url,
#             importance=importance,
#             channels=channels,
#             tags=tags,
#             content_html=data_dict.get("content_html")
#             if isinstance(data_dict.get("content_html"), str)
#             else None,
#             content_extended=data_dict.get("content_more")
#             if isinstance(data_dict.get("content_more"), str)
#             else None,
#             metadata={
#                 "type": "jin10",
#                 "source_type": source_type,
#                 "id": flash_id,
#                 "action": action,
#                 "raw": payload_dict,
#                 "m_type": payload_model.m_type,
#                 "category": payload_model.category,
#                 "remark": payload_model.remark,
#                 "extras": extras_dict if extras_dict else None,
#             },
#         )

#     def to_news_item(self) -> NewsItem:
#         raw_news_id: Union[str, int]
#         if self.payload.id is not None:
#             raw_news_id = self.payload.id
#         elif self.flash_id is not None:
#             raw_news_id = str(self.flash_id)
#         else:
#             raw_news_id = f"jin10-{int(time.time() * 1000)}"

#         return NewsItem(
#             news_id=raw_news_id,
#             content=self.content,
#             news_time=self.news_time,
#             source_type=NewsSourceType.JIN10,
#             title=self.title,
#             source_name=self.source_name,
#             source_url=self.source_url,
#             importance=self.importance,
#             channels=self.channels,
#             tags=self.tags,
#             content_html=self.content_html,
#             content_extended=self.content_extended,
#             metadata=self.metadata,
#         )

#     @staticmethod
#     def _extract_flash_id(
#         payload: Dict[str, Any], data: Dict[str, Any], extras: Dict[str, Any]
#     ) -> Optional[int]:
#         candidates = [payload.get("id"), data.get("id"), extras.get("flash_id")]
#         for candidate in candidates:
#             if isinstance(candidate, int):
#                 return candidate
#             if isinstance(candidate, str) and candidate.isdigit():
#                 return int(candidate)
#         return None

#     @staticmethod
#     def _extract_content(payload: Dict[str, Any], data: Dict[str, Any]) -> str:
#         parts = [
#             data.get("content"),
#             data.get("content_text"),
#             data.get("title"),
#             payload.get("content"),
#             payload.get("content_text"),
#             payload.get("title"),
#             payload.get("remark"),
#         ]
#         for value in parts:
#             if isinstance(value, str):
#                 text = value.strip()
#                 if text:
#                     return text
#         return ""

#     @staticmethod
#     def _extract_time(
#         payload: Dict[str, Any], data: Dict[str, Any], flash_id: Optional[int]
#     ) -> Union[str, int]:
#         for key in (
#             "time",
#             "display_time",
#             "created_at",
#             "createdAt",
#             "publish_time",
#             "pub_time",
#             "timestamp",
#             "ts",
#         ):
#             value = data.get(key)
#             if value is None:
#                 value = payload.get(key)
#             if value is None:
#                 continue
#             if isinstance(value, (int, float)):
#                 return int(value)
#             if isinstance(value, str):
#                 text = value.strip()
#                 if text:
#                     return text
#         if flash_id is not None:
#             digits = str(flash_id)
#             if len(digits) >= 14 and digits[:14].isdigit():
#                 try:
#                     return datetime.strptime(digits[:14], "%Y%m%d%H%M%S").strftime(
#                         "%Y-%m-%d %H:%M:%S"
#                     )
#                 except ValueError:
#                     pass
#         return int(time.time())

#     @staticmethod
#     def _extract_channels(
#         payload: Dict[str, Any], data: Dict[str, Any]
#     ) -> Optional[List[Union[str, int]]]:
#         for key in ("channel", "channels"):
#             value = payload.get(key)
#             if isinstance(value, list):
#                 return value
#             value = data.get(key)
#             if isinstance(value, list):
#                 return value
#         return None

#     @staticmethod
#     def _extract_tags(
#         payload: Dict[str, Any], data: Dict[str, Any]
#     ) -> Optional[List[str]]:
#         raw = payload.get("tags")
#         if not isinstance(raw, list):
#             raw = data.get("tags")
#         if not isinstance(raw, list):
#             return None
#         tags = [str(tag) for tag in raw if isinstance(tag, (str, int, float))]
#         return tags or None

#     @staticmethod
#     def _extract_source_url(
#         payload: Dict[str, Any], data: Dict[str, Any], extras: Dict[str, Any]
#     ) -> Optional[str]:
#         candidates = [
#             data.get("source_url"),
#             data.get("source_link"),
#             payload.get("source_url"),
#             payload.get("source_link"),
#             extras.get("url"),
#         ]
#         for value in candidates:
#             if isinstance(value, str) and value.strip():
#                 return value.strip()
#         return None

#     @staticmethod
#     def _extract_source_name(
#         payload: Dict[str, Any], data: Dict[str, Any]
#     ) -> Optional[str]:
#         for value in (data.get("source"), payload.get("source")):
#             if isinstance(value, str) and value.strip():
#                 return value.strip()
#         return None

#     @staticmethod
#     def _extract_importance(
#         payload: Dict[str, Any], data: Dict[str, Any]
#     ) -> Optional[int]:
#         value = payload.get("important")
#         if value is None:
#             value = data.get("important")
#         if isinstance(value, bool):
#             return int(value)
#         if isinstance(value, int):
#             return value
#         return None

#     @staticmethod
#     def _extract_title(payload: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
#         for value in (data.get("title"), payload.get("title")):
#             if isinstance(value, str):
#                 title = value.strip()
#                 if title:
#                     return title
#         return None


class Jin10FlashService(NewsFetcher):
    """基于前端同协议 WSS 的金十快讯抓取器。"""

    DEFAULT_NEWS_SERVERS = [
        "wss://wss-flash-2.jin10.com/",
    ]
    """默认金十快讯服务器列表"""

    DEFAULT_VIP_NEWS_SERVERS = [
        "wss://wss-flash-vip-2.jin10.com/",
    ]

    reconnect_delay: float
    """断线重连间隔（秒）"""

    keepalive_timeout: float
    """收到心跳(1201)后，下一次心跳最长期待时间（秒）"""

    _paused: bool
    _stop_event: threading.Event
    _thread: Optional[threading.Thread]
    _loop: Optional[asyncio.AbstractEventLoop]
    _last_heartbeat_at: float
    _heartbeat_started: bool

    _seen_ids: set[int]
    _seen_order: List[int]
    _dedup_size: int

    _use_vip_socket: bool
    _servers: List[str]
    _debug_enabled: bool
    _crypto_key: str

    def __init__(
        self,
        *,
        reconnect_delay: float = 5.0,
        keepalive_timeout: float = 15.0,
        dedup_size: int = 2000,
        servers: Optional[Iterable[str]] = None,
        logger: Optional[Logger] = None,
        debug: bool = False,
    ):
        super().__init__(logger)
        self._servers = list(servers or [])
        if not self._servers:
            self._servers = self.DEFAULT_NEWS_SERVERS

        self.reconnect_delay = reconnect_delay
        self.keepalive_timeout = keepalive_timeout
        self._dedup_size = dedup_size

        self._paused = False
        self._stop_event = threading.Event()
        self._thread = None
        self._loop = None
        self._last_heartbeat_at = 0.0
        self._heartbeat_started = False

        self._seen_ids = set()
        self._seen_order = []

        self._debug_enabled = debug
        self._crypto_key = ""

    def _debug(self, message: str):
        if self._debug_enabled:
            self.logger.debug(message)

    def start(self):
        """启动后台线程并建立实时连接。"""
        self._start()

    def _start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def destroy(self):
        """停止抓取器并回收线程资源。"""
        self._destroy()

    def _destroy(self) -> None:
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def pause(self):
        """切换暂停状态：暂停后保持连接但忽略消息处理。"""
        self._pause()

    def _pause(self) -> None:
        self._paused = True

    def _resume(self) -> None:
        self._paused = False

    def _notify_subscribers(self, item: NewsItem) -> None:
        for callback in self._subscribers:
            try:
                callback(item)
            except Exception as err:
                self.logger.error(
                    f"failed to run callback {callback}: {err}", exc_info=True
                )

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_forever())
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_forever(self):
        while not self._stop_event.is_set():
            ws_url = random.choice(self._servers)
            try:
                async with websockets.connect(
                    ws_url,
                    # Jin10 服务端对标准 websocket ping/pong 支持不稳定，
                    # 否则会周期性触发 keepalive ping timeout。
                    # 这里禁用库内建 ping，改用协议内 1201 心跳保活。
                    ping_interval=None,
                    open_timeout=15,
                    close_timeout=10,
                    max_size=None,
                ) as ws:
                    self._last_heartbeat_at = time.time()
                    self._heartbeat_started = False
                    self._crypto_key = ""
                    self.logger.info(f"[jin10] 已连接: {ws_url}")
                    await self._consume_messages(ws)  # 消费消息
            except (
                ConnectionClosed,
                OSError,
                TimeoutError,
                websockets.WebSocketException,
            ) as err:
                if self._stop_event.is_set():
                    break
                self.logger.info(
                    f"[jin10] 连接断开，{self.reconnect_delay:.0f}s 后重连: {err}"
                )
                await asyncio.sleep(self.reconnect_delay)
            except Exception as err:
                if self._stop_event.is_set():
                    break
                self.logger.error(
                    f"[jin10] 未知错误，{self.reconnect_delay:.0f}s 后重连: {err}"
                )
                await asyncio.sleep(self.reconnect_delay)

    async def _send_login(self, ws: ClientConnection):
        """发送前端同款 4002 登录包，降低服务端主动断链概率。"""
        writer = _Jin10BinaryWriter()
        writer.write_i16_le(Jin10MessageType.MSG_USER_LOGIN_NEWS)
        writer.write_i32_le(0)
        writer.write_str_u16_len("")
        writer.write_str_u16_len("python")
        writer.write_i32_le(0)
        writer.write_str_u16_len("web")
        payload = writer.to_bytes()
        if self._crypto_key:
            payload = self._xor_crypt(payload, self._crypto_key)
        await ws.send(payload)
        self._debug(f"[jin10] 已发送登录包 4002，bytes={len(payload)}")

    def _xor_crypt(self, data: bytes, key: str) -> bytes:
        """前端 We.Eab 的 Python 等价实现（异或，对称加解密）。"""
        if not data or not key:
            return data
        key_len = len(key)
        offset = ord(key[0])
        source = bytearray(data)
        for index in range(len(source)):
            source[index] ^= ord(key[(index + offset) % key_len])
        return bytes(source)

    async def _try_init_crypto_key(self, raw: bytes, ws: ClientConnection) -> bool:
        """解析连接后首包中的会话 key，并发送登录包。"""
        if self._crypto_key:
            return False
        if len(raw) < 12:
            return False
        try:
            reader = _Jin10BinaryReader(raw)
            _ = reader.read_u32_le()
            second = reader.read_u32_le()
            third = reader.read_u32_le()
        except struct.error:
            return False

        self._crypto_key = f"{third}.{second}"
        self._debug(f"[jin10] 已建立会话 key，长度={len(self._crypto_key)}")
        await self._send_login(ws)
        return True

    async def _consume_messages(self, ws: ClientConnection):
        """
        持续消费服务器消息，直到连接断开或服务停止
        """
        async for raw in ws:
            if self._stop_event.is_set():
                break
            if self._paused:
                continue

            # 与前端行为对齐：只有收到过 1201 心跳后，才启用心跳超时检测。
            now = time.time()
            if (
                self._heartbeat_started
                and now - self._last_heartbeat_at > self.keepalive_timeout
            ):
                self.logger.info("[jin10] 心跳超时，主动断开等待重连")
                await ws.close()
                break

            if isinstance(raw, str):
                self._handle_text_message(raw)
            elif isinstance(raw, (bytes, bytearray)):
                await self._handle_binary_message(bytes(raw), ws)

    async def _handle_binary_message(self, raw: bytes, ws: ClientConnection):
        if len(raw) < 2:
            return

        # 与前端逻辑一致：加密模式下首包用于协商 key。
        if not self._crypto_key and await self._try_init_crypto_key(raw, ws):
            return

        if self._crypto_key:
            raw = self._xor_crypt(raw, self._crypto_key)

        reader = _Jin10BinaryReader(raw)
        msg_code = reader.read_i16_le()
        self._debug(f"[jin10] 二进制帧: msg_code={msg_code}, bytes={len(raw)}")

        # 按照消息 code，分别处理不同的消息类型
        if msg_code == Jin10MessageType.MSG_HEARTBEAT:
            self._heartbeat_started = True
            self._last_heartbeat_at = time.time()
            self._debug("[jin10] 收到心跳 1201，回发空消息")
            await ws.send("")
        elif msg_code == Jin10MessageType.MSG_LAST_NEWS_LIST:
            """
            读取历史消息
            与前端一致：1200 是历史列表，会包含多个 rStrL JSON。
            """
            self._handle_last_news_list(reader)
        elif msg_code in {
            Jin10MessageType.MSG_NEWS_FLASH,
            Jin10MessageType.MSG_VIP_NEWS_FLASH,
            Jin10MessageType.MSG_EVENTS_FLASH,
            Jin10MessageType.MSG_TOP_LIST,
            Jin10MessageType.MSG_USER_LOGIN_NEWS,
        }:
            payload_text = reader.read_str_u16_len()
            self._handle_json_payload(msg_code, payload_text)
        else:
            self._debug(f"[jin10] 未知二进制消息类型: msg_code={msg_code}")

    def _handle_text_message(self, raw: str):
        self._debug(f"[jin10] 文本帧长度: {len(raw)}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            self._debug("[jin10] 文本帧 JSON 解析失败")
            return
        self._dispatch_payload(parsed, source_type="text")

    def _handle_json_payload(self, msg_code: int, payload_text: str):
        try:
            payload = json.loads(payload_text)
            self._debug(f"[jin10] JSON 载荷解析成功: msg_code={msg_code}")
        except json.JSONDecodeError:
            self._debug(f"[jin10] JSON 载荷解析失败: msg_code={msg_code}")
            return

        source_type = {
            Jin10MessageType.MSG_NEWS_FLASH: "flash",
            Jin10MessageType.MSG_VIP_NEWS_FLASH: "vip_flash",
            Jin10MessageType.MSG_EVENTS_FLASH: "event",
            Jin10MessageType.MSG_TOP_LIST: "top_list",
            Jin10MessageType.MSG_USER_LOGIN_NEWS: "login",
        }.get(msg_code, "unknown")
        self._dispatch_payload(payload, source_type=source_type)

    def _handle_last_news_list(self, reader: _Jin10BinaryReader):
        """
        处理历史列表帧，包含多条 JSON 结构的快讯数据
        在第一次连接到 websocket 的时候会线读取历史消息
        """
        # 前端代码写的是 JSON.parse(n.r32L())，语义上等价为读取历史条数。
        try:
            count = reader.read_i32_le()
        except struct.error:
            self._debug("[jin10] 读取历史列表数量失败")
            return
        self._debug(f"[jin10] 历史列表条数: {count}")

        items: List[Dict[str, Any]] = []
        for _ in range(max(0, count)):
            try:
                text = reader.read_str_u16_len()
                one = json.loads(text)
                if isinstance(one, dict):
                    items.append(one)
            except (struct.error, json.JSONDecodeError):
                self._debug("[jin10] 历史列表解析中断")
                break

        # 前端使用 unshift 逆序，这里保持时间从旧到新输出。
        for item in reversed(items):
            self._dispatch_payload(item, source_type="last_list")

    def _dispatch_payload(self, payload: Any, *, source_type: str):
        self._append_raw(payload, source_type)
        self._debug(
            f"[jin10] 分发 payload: source_type={source_type}, payload_type={type(payload).__name__}"
        )

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    self._handle_news_item(item, source_type)
            return

        if isinstance(payload, dict):
            # 部分帧形如 {action: 1, data: {...}}，也有直接是新闻结构。
            if isinstance(payload.get("datas"), list):
                for item in payload["datas"]:
                    if isinstance(item, dict):
                        self._handle_news_item(item, source_type)
                return
            if isinstance(payload.get("data"), dict):
                self._handle_news_item(payload, source_type)
                return
            self._handle_news_item(payload, source_type)

    def _handle_news_item(self, item: Dict[str, Any], source_type: str):
        action = item.get("action")
        if action == 3:
            self._debug("[jin10] 忽略删除动作 action=3")
            return

        flash_id = self._extract_flash_id(item)
        if flash_id is not None and self._is_seen(flash_id):
            self._debug(f"[jin10] 去重命中 id={flash_id}")
            return

        text = self._extract_text(item)
        if not text:
            self._debug("[jin10] 快讯无文本内容，忽略")
            return

        when = self._extract_time(item)
        content = f"[{when}][金十快讯] {text}"

        data = item.get("data") if isinstance(item.get("data"), dict) else item
        raw_news_id = item.get("id")
        if raw_news_id is None and isinstance(data, dict):
            raw_news_id = data.get("id")
        if raw_news_id is None:
            raw_news_id = (
                str(flash_id)
                if flash_id is not None
                else f"jin10-{int(time.time() * 1000)}"
            )

        importance = item.get("important")
        if not isinstance(importance, int):
            importance = data.get("important") if isinstance(data, dict) else None
        if isinstance(importance, bool):
            importance = int(importance)
        if not isinstance(importance, int):
            importance = None

        channels = item.get("channel")
        if not isinstance(channels, list):
            channels = item.get("channels")
        if not isinstance(channels, list):
            channels = data.get("channel") if isinstance(data, dict) else None
        if not isinstance(channels, list):
            channels = data.get("channels") if isinstance(data, dict) else None

        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = data.get("tags") if isinstance(data, dict) else None

        source_url = None
        if isinstance(data, dict):
            for value in (data.get("source_url"), data.get("source_link")):
                if isinstance(value, str) and value.strip():
                    source_url = value.strip()
                    break

        metadata = {
            "type": "jin10",
            "source_type": source_type,
            "id": flash_id,
            "action": action,
            "raw": item,
        }

        news_item = NewsItem(
            news_id=raw_news_id,
            content=text,
            news_time=when if when != "unknown" else int(time.time()),
            source_type=NewsSourceType.JIN10,
            title=(data.get("title") if isinstance(data.get("title"), str) else None),
            source_name=(
                data.get("source") if isinstance(data.get("source"), str) else None
            ),
            source_url=source_url,
            importance=importance,
            channels=channels,
            tags=tags if isinstance(tags, list) else None,
            content_html=(
                data.get("content_html")
                if isinstance(data.get("content_html"), str)
                else None
            ),
            content_extended=(
                data.get("content_more")
                if isinstance(data.get("content_more"), str)
                else None
            ),
            metadata=metadata,
        )

        self._notify_subscribers(news_item)
        self.logger.info(content, extra=metadata)
        self._debug(
            f"[jin10] 已输出快讯: source_type={source_type}, id={flash_id}, action={action}"
        )

        if flash_id is not None:
            self._mark_seen(flash_id)

    def _extract_flash_id(self, item: Dict[str, Any]) -> Optional[int]:
        candidates = [item.get("id")]
        data = item.get("data")
        if isinstance(data, dict):
            candidates.append(data.get("id"))

        for candidate in candidates:
            if isinstance(candidate, int):
                return candidate
            if isinstance(candidate, str) and candidate.isdigit():
                return int(candidate)
        return None

    def _extract_text(self, item: Dict[str, Any]) -> str:
        data = item.get("data")
        if not isinstance(data, dict):
            data = item

        parts = [
            data.get("content"),
            data.get("content_text"),
            data.get("title"),
            data.get("remark"),
            item.get("content"),
            item.get("content_text"),
            item.get("title"),
        ]

        for value in parts:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
        return ""

    def _extract_time(self, item: Dict[str, Any]) -> str:
        raw_data = item.get("data")
        data: Dict[str, Any] = raw_data if isinstance(raw_data, dict) else item

        for key in (
            "time",
            "display_time",
            "created_at",
            "createdAt",
            "publish_time",
            "pub_time",
            "timestamp",
            "ts",
        ):
            value = data.get(key)
            if value is None:
                continue

            parsed = self._format_unix_time(value)
            if parsed:
                return parsed

            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text

        # 金十常见 id 形如 20260214005844618800，前 14 位是 YYYYMMDDHHMMSS。
        flash_id = self._extract_flash_id(item)
        if flash_id is not None:
            parsed_by_id = self._format_time_from_flash_id(flash_id)
            if parsed_by_id:
                return parsed_by_id

        return "unknown"

    def _format_unix_time(self, value: Any) -> Optional[str]:
        if not isinstance(value, (int, float, str)):
            return None

        if isinstance(value, str):
            raw = value.strip()
            if not raw or not raw.isdigit():
                return None
            numeric = float(raw)
        else:
            numeric = float(value)

        try:
            if numeric > 1e12:
                numeric /= 1000
            return datetime.fromtimestamp(numeric).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError):
            return None

    def _format_time_from_flash_id(self, flash_id: int) -> Optional[str]:
        digits = str(flash_id)
        if len(digits) < 14 or not digits[:14].isdigit():
            return None
        try:
            dt = datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
        except ValueError:
            return None
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _is_seen(self, item_id: int) -> bool:
        return item_id in self._seen_ids

    def _mark_seen(self, item_id: int):
        if item_id in self._seen_ids:
            return
        self._seen_ids.add(item_id)
        self._seen_order.append(item_id)
        if len(self._seen_order) > self._dedup_size:
            oldest = self._seen_order.pop(0)
            self._seen_ids.discard(oldest)

    def _append_raw(self, payload: Any, source_type: str):
        out_file = Path(__file__).resolve().parents[3] / "data/jin10.jsonl"
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        line = {"source_type": source_type, "payload": payload}
        try:
            with open(out_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            pass


class Jin10NewsService(Jin10FlashService):
    """兼容旧命名，保持对外 API 不变。"""


def main():
    """命令行入口：用于本地快速验证实时抓取效果。"""
    parser = argparse.ArgumentParser(description="金十实时快讯抓取")
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="运行秒数，0 表示持续运行直到 Ctrl+C",
    )
    args = parser.parse_args()

    debug_mode = False

    fetcher = Jin10FlashService(debug=debug_mode)
    fetcher.start()
    fetcher.logger.info("Jin10 实时快讯已启动，按 Ctrl+C 退出。")

    try:
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        fetcher.logger.info("\n正在停止 Jin10 实时快讯...")
    finally:
        fetcher.destroy()
        fetcher.logger.info("Jin10 实时快讯已停止")


if __name__ == "__main__":
    main()
