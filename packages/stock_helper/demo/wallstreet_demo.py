import argparse
import json
import threading
import time
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Optional

from stock_helper.news.interface import NewsItem
from stock_helper.news.wallstreet import WallstreetLiveFetcher, WallstreetMockFetcher


class OperationMode(StrEnum):
    """运行模式。"""

    REPLAY = "replay"
    REALTIME = "realtime"


def run_replay(input_file: Path, max_items: int, replay_interval: float) -> None:
    """回放本地 Wallstreet JSONL 数据。"""
    if not input_file.exists():
        print(f"replay file not found: {input_file}")
        return

    received = 0

    def on_news(item: NewsItem) -> None:
        nonlocal received
        received += 1
        print(
            f"[wallstreet] #{received} id={item.news_id} "
            f"time={item.news_time} content={item.content[:80]}"
        )

    fetcher = WallstreetMockFetcher(
        mock_file=str(input_file),
        replay_interval=replay_interval,
        loop_replay=False,
        max_items=max_items,
        channels=["global-channel"],
    )
    fetcher.subscribe(on_news)

    print(f"start wallstreet replay demo, file={input_file}")
    fetcher.start()
    try:
        while fetcher._thread and fetcher._thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("interrupted by user")
    finally:
        fetcher.destroy()
    print(f"done, received={received}")


def run_realtime(
    output_file: Path, max_items: int, timeout_seconds: Optional[int]
) -> None:
    """实时抓取 Wallstreet 数据并写入 JSONL。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.touch(exist_ok=True)
    received = 0
    done = threading.Event()
    lock = threading.Lock()

    def on_news(item: NewsItem) -> None:
        nonlocal received
        payload = item.metadata.get("raw")
        if not isinstance(payload, dict):
            return

        row = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "type": "STREAM",
            "content": payload,
        }
        with lock:
            with output_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            received += 1
            index = received

        print(
            f"[wallstreet-live] #{index} id={item.news_id} "
            f"time={item.news_time} content={item.content[:80]}"
        )
        if index >= max_items:
            done.set()

    fetcher = WallstreetLiveFetcher(channels=["global-channel"])
    fetcher.subscribe(on_news)
    timeout_text = f"{timeout_seconds}s" if timeout_seconds is not None else "infinite"
    print(
        f"start wallstreet realtime demo, output={output_file}, "
        f"max_items={max_items}, timeout={timeout_text}"
    )
    fetcher.start()
    try:
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
    print(f"done, received={received}, replay_file={output_file}")


def main() -> None:
    """解析参数并执行实时/回放模式。"""
    base_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Wallstreet replay/realtime demo")
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
        default=base_dir / "data/wallstreet_realtime.jsonl",
        help="回放模式输入 JSONL",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=base_dir / "data/wallstreet_realtime.jsonl",
        help="实时模式输出 JSONL",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="实时模式超时秒数（默认不超时，需手动 Ctrl+C 结束）",
    )
    parser.add_argument(
        "--replay-interval", type=float, default=0.1, help="回放模式每条消息间隔（秒）"
    )
    args = parser.parse_args()

    if args.mode == OperationMode.REPLAY:
        run_replay(
            input_file=args.input_file,
            max_items=args.max_items,
            replay_interval=args.replay_interval,
        )
        return
    run_realtime(
        output_file=args.output_file,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
