import struct
from datetime import datetime

from stock_helper.news.interface import NewsSourceType
from stock_helper.news.jin10 import (
    Jin10FlashService,
    Jin10Message,
    Jin10MessageType,
    Jin10NewsService,
    _Jin10BinaryReader,
    _Jin10BinaryWriter,
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


class TestJin10BinaryReader:
    def test_read_basic_types(self) -> None:
        payload = struct.pack("<hIHI", 7, 9, 3, 11)
        reader = _Jin10BinaryReader(payload)
        assert reader.read_i16_le() == 7
        assert reader.read_u32_le() == 9
        assert reader.read_u16_le() == 3
        assert reader.read_u32_le() == 11


class TestJin10BinaryWriter:
    def test_write_and_read_back(self) -> None:
        writer = _Jin10BinaryWriter()
        writer.write_i16_le(1000)
        writer.write_str_u16_len("abc")
        reader = _Jin10BinaryReader(writer.to_bytes())
        assert reader.read_i16_le() == 1000
        assert reader.read_str_u16_len() == "abc"


class TestJin10MessageType:
    def test_constants(self) -> None:
        assert Jin10MessageType.MSG_HEARTBEAT == 1201
        assert Jin10MessageType.MSG_USER_LOGIN_NEWS == 4002


class TestJin10Message:
    def test_from_payload_last_list_to_news_item(self) -> None:
        payload = {
            "type": 0,
            "id": "20260213234208900800",
            "time": "2026-02-13 23:42:08",
            "data": {
                "content": "在等待关税案裁决期间，美国最高法院宣布2月20日将公布意见。",
                "pic": "",
                "title": "",
                "source": "",
                "source_link": "",
            },
            "important": 1,
            "tags": [],
            "remark": [],
            "extras": {"ad": False},
            "channel": [1, 2, 3],
            "action": 1,
        }
        message = Jin10Message.from_payload(payload, "last_list")
        assert message is not None
        news = message.to_news_item()
        assert news.source_type == NewsSourceType.JIN10
        assert news.news_id == "20260213234208900800"
        assert news.channels == [1, 2, 3]
        assert news.importance == 1
        assert isinstance(news.news_time, datetime)

    def test_from_payload_category_flash(self) -> None:
        payload = {
            "title": "特朗普称将访问委内瑞拉",
            "content": "金十数据2月14日讯，内容",
            "category": "flash",
            "extras": {"img": "", "url": "", "flash_id": "20260214021300671800"},
            "important": False,
            "only_online": False,
            "action": 4,
        }
        message = Jin10Message.from_payload(payload, "flash")
        assert message is not None
        news = message.to_news_item()
        assert news.news_id == "20260214021300671800"
        assert news.title == "特朗普称将访问委内瑞拉"
        assert news.importance == 0

    def test_from_payload_delete_action_returns_none(self) -> None:
        payload = {"id": "20260206063011320800", "action": 3}
        assert Jin10Message.from_payload(payload, "flash") is None


class TestJin10FlashService:
    def test_xor_round_trip(self) -> None:
        service = Jin10FlashService(servers=["wss://test"], logger=_FakeLogger())
        original = b"hello"
        encoded = service._xor_crypt(original, "key")
        decoded = service._xor_crypt(encoded, "key")
        assert decoded == original

    def test_handle_news_item_dispatch_and_dedup(self) -> None:
        service = Jin10FlashService(servers=["wss://test"], logger=_FakeLogger())
        received = []
        service.subscribe(lambda item: received.append(item))
        item = {
            "id": 20260215010203000123,
            "action": 1,
            "data": {
                "content": "jin10 content",
                "time": "2026-02-15 01:02:03",
                "title": "t",
            },
        }
        service._handle_news_item(item, "flash")
        service._handle_news_item(item, "flash")
        assert len(received) == 1
        assert received[0].source_type == NewsSourceType.JIN10
        assert isinstance(received[0].news_time, datetime)

    def test_extract_helpers(self) -> None:
        service = Jin10FlashService(servers=["wss://test"], logger=_FakeLogger())
        item = {"id": "20260215010203000123", "data": {"content": "c"}}
        assert service._extract_flash_id(item) == 20260215010203000123
        assert service._extract_text(item) == "c"
        assert service._extract_time(item).startswith("2026-02-15")


class TestJin10FlushService:
    def test_compat_subclass(self) -> None:
        service = Jin10NewsService(servers=["wss://test"], logger=_FakeLogger())
        assert isinstance(service, Jin10FlashService)
