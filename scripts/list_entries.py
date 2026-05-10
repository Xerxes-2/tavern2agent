#!/usr/bin/env python3
"""列出角色卡 JSON 中所有世界书条目的概览。

Usage:
    python3 list_entries.py card.json                  # 列出所有条目
    python3 list_entries.py card.json --filter mvu     # 只看 MVU 条目
    python3 list_entries.py card.json --filter mvu_update  # 只看 [mvu_update]
    python3 list_entries.py card.json --filter initvar     # 只看 [initvar]
    python3 list_entries.py card.json --search 战斗      # 搜索含关键词的条目
"""

import json
import sys


def list_entries(card: dict, filter_tag: str | None = None, search: str | None = None):
    data = card.get("data", card)
    entries = data.get("character_book", {}).get("entries", [])
    print(f"共 {len(entries)} 条世界书条目\n")

    shown = 0
    for i, entry in enumerate(entries):
        comment = entry.get("comment", "") or "(无注释)"
        keys = entry.get("keys", []) or []
        content = entry.get("content", "") or ""
        content_preview = content[:80].replace("\n", " ").replace("\r", "") if content else "(空)"

        # 提取标签
        comment_lower = comment.lower()

        # 过滤
        if filter_tag:
            if filter_tag in ("mvu", "mvu_plot", "mvu_update", "initvar"):
                if filter_tag == "mvu":
                    if "[mvu" not in comment_lower:
                        continue
                else:
                    if f"[{filter_tag}]" not in comment_lower:
                        continue

        if search:
            combined = comment + " ".join(keys) + content[:200]
            if search.lower() not in combined.lower():
                continue

        # 标记类型
        tags = []
        if "[mvu_plot]" in comment_lower:
            tags.append("📖plot")
        elif "[mvu_update]" in comment_lower:
            tags.append("📝update")
        if "[initvar]" in comment_lower:
            tags.append("🔰initvar")
        if "[mvu" in comment_lower:
            pass  # already tagged
        if entry.get("constant"):
            tags.append("🔒常驻")
        if entry.get("selective"):
            tags.append("⚡选择性")
        if not entry.get("enabled", True):
            tags.append("❌禁用")

        tag_str = " ".join(tags) + " " if tags else ""

        print(f"[{i:3d}] {tag_str}{comment}")
        if keys:
            print(f"      触发词: {', '.join(keys[:6])}")
        print(f"      内容: {content_preview}")
        print()
        shown += 1

    print(f"\n显示 {shown} / {len(entries)} 条")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    card_path = sys.argv[1]

    with open(card_path, "r", encoding="utf-8") as f:
        card = json.load(f)

    filter_tag = None
    search = None

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--filter" and i + 1 < len(args):
            filter_tag = args[i + 1]
            i += 2
        elif args[i] == "--search" and i + 1 < len(args):
            search = args[i + 1]
            i += 2
        else:
            print(f"未知参数: {args[i]}")
            sys.exit(1)

    list_entries(card, filter_tag, search)


if __name__ == "__main__":
    main()
