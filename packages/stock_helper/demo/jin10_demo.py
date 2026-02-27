import argparse
import json
import threading
import time
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Optional

from stock_helper.news.interface import NewsItem
from stock_helper.news.jin10 import Jin10FlashService, Jin10Message


class OperationMode(StrEnum):
    """运行模式"""

    REPLAY = "replay"  # 回放模式
    REALTIME = "realtime"  # 实时模式


def run_replay(jsonl_file: Path, max_items: int):
    """从本地 JSONL 文件回放 Jin10 原始消息，并转换为标准 NewsItem 输出。"""
    emitted = 0
    print(f"start jin10 replay demo, file={jsonl_file}")

    with jsonl_file.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue

            # 每行格式：{"source_type": "...", "payload": {...}}
            row = json.loads(text)
            source_type = row.get("source_type")
            payload = row.get("payload")
            if not isinstance(source_type, str) or not isinstance(payload, dict):
                continue

            message = Jin10Message.from_payload(payload, source_type)
            if message is None:
                continue

            item = message.to_news_item()
            emitted += 1
            print(
                f"[jin10] #{emitted} id={item.news_id} "
                f"time={item.news_time} content={item.content[:80]}"
            )
            if emitted >= max_items:
                break

    print(f"done, emitted={emitted}")


def run_realtime(
    replay_file: Path,
    max_items: int,
    timeout_seconds: Optional[int],
    include_last_list: bool,
):
    """实时连接 Jin10 WebSocket，并把消息写入 JSONL 作为回放素材。"""
    replay_file.parent.mkdir(parents=True, exist_ok=True)
    received = 0
    done = threading.Event()
    # 回调在后台线程触发，写文件与计数需要互斥保护。
    lock = threading.Lock()

    def on_news(item: NewsItem) -> None:
        """处理单条实时消息：过滤、落盘、打印、计数。"""
        nonlocal received
        source_type = item.metadata.get("source_type")
        payload = item.metadata.get("raw")
        # 历史回放帧默认不写入，避免污染实时采样结果。
        if source_type == "last_list" and not include_last_list:
            return
        if not isinstance(source_type, str) or not isinstance(payload, dict):
            return

        row = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_type": source_type,
            "payload": payload,
        }
        with lock:
            with replay_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            received += 1
            index = received

        print(
            f"[jin10-live] #{index} id={item.news_id} "
            f"time={item.news_time} content={item.content[:80]}"
        )
        if index >= max_items:
            done.set()

    fetcher = Jin10FlashService(debug=False)
    fetcher.subscribe(on_news)
    timeout_text = f"{timeout_seconds}s" if timeout_seconds is not None else "infinite"
    print(
        f"start jin10 realtime demo, output={replay_file}, "
        f"max_items={max_items}, timeout={timeout_text}"
    )
    fetcher.start()
    try:
        # 轮询等待直到达到 max_items；如传入 timeout 则额外受超时约束。
        if timeout_seconds is None:
            while not done.is_set():
                time.sleep(0.2)
        else:
            deadline = time.time() + timeout_seconds
            while not done.is_set() and time.time() < deadline:
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("interrupted by user")
    finally:
        fetcher.destroy()

    print(f"done, received={received}, replay_file={replay_file}")


def main() -> None:
    """解析命令行参数并按模式执行回放/实时 demo。"""
    base_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Jin10 replay/realtime demo")
    parser.add_argument(
        "--mode",
        choices=[OperationMode.REPLAY, OperationMode.REALTIME],
        default=OperationMode.REALTIME,
        help="运行模式",
    )
    parser.add_argument("--max-items", type=int, default=5, help="最多处理条数")
    parser.add_argument(
        "--input-file",
        type=Path,
        default=base_dir / "data/jin10.jsonl",
        help="回放模式输入 JSONL",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=base_dir / "data/jin10_realtime.jsonl",
        help="实时模式输出 JSONL",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="实时模式超时秒数（默认不超时，需手动 Ctrl+C 结束）",
    )
    parser.add_argument(
        "--include-last-list",
        action="store_true",
        help="实时模式是否保留 last_list 历史消息",
    )
    args = parser.parse_args()

    if args.mode == OperationMode.REPLAY:
        run_replay(args.input_file, args.max_items)
        return
    run_realtime(
        args.output_file,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
        include_last_list=args.include_last_list,
    )


if __name__ == "__main__":
    main()
