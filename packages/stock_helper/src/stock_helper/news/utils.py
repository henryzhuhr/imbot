from pathlib import Path


def jsonl_to_json(jsonl_path, json_path):
    with (
        open(jsonl_path, "r", encoding="utf-8") as fin,
        open(json_path, "w", encoding="utf-8") as fout,
    ):
        fout.write("[\n")
        first = True
        for line in fin:
            line = line.strip()
            if not line:
                continue  # 跳过空行
            if not first:
                fout.write(",\n")
            else:
                first = False
            fout.write(line)
        fout.write("\n]")


# 使用示例
_data_dir = Path(__file__).resolve().parents[3] / "data"
jsonl_to_json(_data_dir / "wallstreet.jsonl", _data_dir / "wallstreet.json")
jsonl_to_json(_data_dir / "jin10.jsonl", _data_dir / "jin10.json")
