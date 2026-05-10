#!/usr/bin/env python3
"""从 SillyTavern PNG 角色卡中提取内置 JSON。

Usage:
    python3 extract_png.py <card.png> [output.json]
    python3 extract_png.py <card.png>           # 输出到 stdout
"""

import struct
import base64
import json
import sys


def extract_card(png_path: str) -> dict:
    with open(png_path, "rb") as f:
        f.read(8)  # PNG signature
        while True:
            length = struct.unpack(">I", f.read(4))[0]
            chunk_type = f.read(4)
            data = f.read(length)
            f.read(4)  # CRC

            if chunk_type == b"tEXt":
                keyword, _, value = data.partition(b"\x00")
                if keyword in (b"chara", b"ccv3"):
                    return json.loads(base64.b64decode(value))

            if chunk_type == b"IEND":
                break

    raise ValueError("No chara/ccv3 chunk found in PNG")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    png_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    card = extract_card(png_path)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
        print(f"Saved to {output_path}")
    else:
        print(json.dumps(card, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
