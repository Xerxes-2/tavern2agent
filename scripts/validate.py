#!/usr/bin/env python3
"""校验 tavern2agent 转换产出是否符合 SKILL.md 的硬性约定。

Usage:
    python3 validate.py <project_dir>

退出码：
    0 = 全部通过
    1 = 有 ERROR（产出不合格）
    2 = 仅有 WARN（值得复查但不阻塞）

检查项见 SKILL.md「产出确认」清单。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 酒馆补丁残留信号——出现在最终 prompt 里基本就是没清干净
TAVERN_LEAKS = [
    "<UpdateVariable>",
    "</UpdateVariable>",
    "JSON Patch",
    "RFC 6902",
    "<%_",  # EJS
    "{{getvar:",
    "{{setvar:",
    "__结束__",
    "强化思考要求",
    "认知隔离",
    "<出场角色>",
]

# Re:0 特有字段——出现在非 Re:0 卡的 engine/state.ts 就是照抄
RE0_FINGERPRINTS = ["魔女残香", "死亡回溯计数", "is_changed_chapter"]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.oks: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)

    def print(self) -> int:
        for m in self.oks:
            print(f"  OK   {m}")
        for m in self.warns:
            print(f"  WARN {m}")
        for m in self.errors:
            print(f"  ERR  {m}")
        print()
        print(f"通过 {len(self.oks)} / 警告 {len(self.warns)} / 错误 {len(self.errors)}")
        if self.errors:
            return 1
        if self.warns:
            return 2
        return 0


def check_gm(root: Path, r: Report) -> None:
    gm = root / "agents" / "gm.md"
    if not gm.exists():
        gm = root / ".claude" / "agents" / "gm.md"
    if not gm.exists():
        r.err("agents/gm.md 不存在（pi 与 Claude Code 路径都查过）")
        return

    text = gm.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    r.ok(f"找到 GM prompt: {gm.relative_to(root)}（{len(lines)} 非空行）")

    # 规则数量：粗略数 markdown 列表项中带有「规则」段落附近的项
    rule_lines = re.findall(r"^\s*[-\d]\.?\s+", text, flags=re.MULTILINE)
    if len(rule_lines) > 8:
        r.warn(f"gm.md 列表项 {len(rule_lines)} 条偏多，SKILL.md 建议核心规则 ≤5 条")

    leaks = [tag for tag in TAVERN_LEAKS if tag in text]
    if leaks:
        r.err(f"gm.md 残留酒馆补丁标记: {', '.join(leaks)}")


def check_engine(root: Path, r: Report) -> None:
    state_ts = root / "engine" / "state.ts"
    if not state_ts.exists():
        r.ok("无 engine/state.ts（纯 prompt 或仅轻量内联状态）")
        return

    text = state_ts.read_text(encoding="utf-8")
    r.ok(f"找到 engine/state.ts（{len(text.splitlines())} 行）")

    fps = [fp for fp in RE0_FINGERPRINTS if fp in text]
    if fps:
        r.err(
            f"engine/state.ts 出现 Re:0 特有字段 {fps}——很可能照抄了 ts-engine.md 的 "
            "initialBlankState 而没替换为本卡 schema"
        )

    if "process.cwd()" in text and "TAVERN2AGENT_STATE_DIR" not in text:
        r.warn(
            "engine/state.ts 用 process.cwd() 但没读 TAVERN2AGENT_STATE_DIR——"
            "跨平台胶水将无法重定向 state 目录"
        )


def check_regex_dropped(root: Path, r: Report) -> None:
    # regex_scripts 应该在转换中丢弃，不该出现在产出里
    for path in root.rglob("*.json"):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if '"regex_scripts"' in text or '"findRegex"' in text:
            r.warn(f"{path.relative_to(root)} 含 regex_scripts，疑似把酒馆 UI 格式化逻辑带进了产出")


def check_narrator(root: Path, r: Report) -> None:
    for candidate in [root / "agents" / "narrator.md", root / ".claude" / "agents" / "narrator.md"]:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8")
        if "tools:" in text and "tools: []" not in text and "tools:\n" not in text:
            r.warn(
                f"{candidate.relative_to(root)} 的 narrator 似乎仍持有工具——"
                "SKILL.md 约定 narrator 只写叙事，tools 应为空"
            )


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"不是目录: {root}")
        return 1

    print(f"校验 {root}\n")
    r = Report()
    check_gm(root, r)
    check_engine(root, r)
    check_regex_dropped(root, r)
    check_narrator(root, r)
    return r.print()


if __name__ == "__main__":
    sys.exit(main())
