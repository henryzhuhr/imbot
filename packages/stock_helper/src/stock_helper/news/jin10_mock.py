import json
import os
import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, overload, override

from common.log import Logger

from .interface import NewsSourceType
from .jin10 import (
    Jin10FlashService,
    Jin10MessageType,
    Jin10NewsService,
    _Jin10BinaryReader,
    _Jin10BinaryWriter,
)


class Jin10FlashGenerateDataService(Jin10FlashService):
    """
    金十快讯服务获取数据的服务
    """

    _data_file: Path
    """保存快讯数据的本地文件路径，默认为 packages/stock_helper/data/jin10.jsonl """

    def __init__(
        self,
        data_file: Path = Path(__file__).resolve().parents[3] / "data/jin10.jsonl",
        logger: Optional[Logger] = None,
        debug: bool = True,
    ):
        super().__init__(logger=logger, debug=debug)
        self._data_file = data_file

    @override
    def _handle_json_payload(self, msg_code: int, payload_text: str):
        """
        重写父类方法，解析 JSON 载荷并将其保存到本地文件，同时分发给订阅者
        """
        try:
            payload = json.loads(payload_text)
            self._debug(f"[jin10] JSON 载荷解析成功: msg_code={msg_code}")
            self._debug(f"[金十数据] {payload}")

            os.makedirs(os.path.dirname(self._data_file), exist_ok=True)
            with open(self._data_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        except json.JSONDecodeError:
            self._debug(f"[jin10] JSON 载荷解析失败: msg_code={msg_code}")
            return


class Jin10FlashMockService(Jin10FlashService):
    """
    模拟金十快讯服务，提供测试用的快讯数据生成和处理功能
    """

    def __init__(self):
        super().__init__()


def main():
    from loguru import logger as default_logger

    print("正在启动金十快讯数据生成服务...")
    generate_service = Jin10FlashGenerateDataService(logger=default_logger)
    generate_service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("收到停止信号，正在关闭金十快讯数据生成服务...")
    finally:
        generate_service.destroy()


if __name__ == "__main__":
    main()
