import time
from pathlib import Path

from stock_helper.news.wallstreet import WallstreetMockFetcher


def main() -> None:
    mock_file = Path(__file__).resolve().parents[1] / "data/wallstreet.jsonl"
    received = 0

    def on_news(item) -> None:
        nonlocal received
        received += 1
        print(
            f"[wallstreet] #{received} id={item.news_id} "
            f"time={item.news_time} content={item.content[:80]}"
        )

    fetcher = WallstreetMockFetcher(
        mock_file=str(mock_file),
        replay_interval=0.1,
        loop_replay=False,
        max_items=5,
        channels=["global-channel"],
    )
    fetcher.subscribe(on_news)

    print(f"start wallstreet mock demo, file={mock_file}")
    fetcher.start()
    time.sleep(2)
    fetcher.destroy()
    print(f"done, received={received}")


if __name__ == "__main__":
    main()
