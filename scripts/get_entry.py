#!/usr/bin/env python3
"""获取角色卡 JSON 中特定世界书条目的完整内容。

Usage:
    python3 get_entry.py card.json 0           # 查看第 0 条
    python3 get_entry.py card.json 0,3,5       # 查看第 0, 3, 5 条
    python3 get_entry.py card.json 0-5         # 查看第 0 到 5 条
    python3 get_entry.py card.json 0,3-5,8     # 混合
"""

import json
import sys


def parse_indices(raw: str, total: int) -> list[int]:
    indices = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            indices.extend(range(int(start), int(end) + 1))
        else:
            indices.append(int(part))
    return [i for i in indices if 0 <= i < total]


def show_entry(entry: dict):
    for key, value in entry.items():
        if key == "content":
            content = str(value) if value else "(空)"
            print(f"  {key} ({len(content)} 字符):")
            print(f"  {'─' * 40}")
            print(content)
            print(f"  {'─' * 40}")
        elif key == "extensions":
            if value:
                print(f"  {key}: {json.dumps(value, ensure_ascii=False, indent=4)}")
            else:
                print(f"  {key}: (空)")
        else:
            print(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
    print()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    card_path = sys.argv[1]
    index_spec = sys.argv[2]

    with open(card_path, "r", encoding="utf-8") as f:
        card = json.load(f)

    data = card.get("data", card)
    entries = data.get("character_book", {}).get("entries", [])
    total = len(entries)

    indices = parse_indices(index_spec, total)
    if not indices:
        print(f"无效索引，共 {total} 条 (0-{total - 1})")
        sys.exit(1)

    print(f"共 {total} 条，显示 {len(indices)} 条\n")
    for i in indices:
        print(f"=== [{i}] {entries[i].get('comment', '(无注释)')} ===")
        show_entry(entries[i])


if __name__ == "__main__":
    main()
