import json
from pathlib import Path

from stock_helper.news.jin10 import Jin10Message


def main() -> None:
    jsonl_file = Path(__file__).resolve().parents[1] / "data/jin10.jsonl"
    max_items = 5
    emitted = 0

    print(f"start jin10 jsonl demo, file={jsonl_file}")

    with jsonl_file.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue

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


if __name__ == "__main__":
    main()
