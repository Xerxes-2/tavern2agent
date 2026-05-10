---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 agent 平台（pi / Claude Code）时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策——这些补丁不需要了。核心优势：agent 可以 loop（查询→掷骰→计算→更新→叙事）、自我纠正（算错了 dispatch 修正事件）、动态管理上下文（数据文件 + 查询工具，而非全塞 prompt）。

---

## 一、快速开始

```bash
python3 scripts/extract_png.py <角色卡.png> card.json   # PNG 解包
python3 scripts/list_entries.py card.json --filter mvu     # 看 MVU 条目
python3 scripts/list_entries.py card.json --filter initvar # 看初始值
```

| 脚本 | 用途 |
|------|------|
| `extract_png.py <png> [out.json]` | PNG → JSON |
| `list_entries.py <json> [--filter mvu\|initvar]` | 世界书条目概览 |
| `get_entry.py <json> <索引>` | 读条目完整内容 |

> 大数据量卡片（条目 ≥100）到构建阶段请直接用 `python3 -c` 批量提取，脚本工具仅供探索。

---

## 二、卡片分析

按顺序排查四个信息源，详情见对应 reference：

| 步骤 | 看什么 | 关键信号 | 详参 |
|------|--------|---------|------|
| 1 | `tavern_helper.scripts` | 有 Zod 脚本？有外链游戏脚本？ | `references/script-analysis.md` |
| 2 | `regex_scripts` | 有游戏内容注入（非纯 UI）？ | `references/script-analysis.md` |
| 3 | 世界书 `[initvar]` 条目 | 初始状态权威来源（YAML） | `references/mvu-mapping.md` |
| 4 | 世界书 `[mvu_update]`/`[mvu_plot]` 条目 | 骰子公式？伤害规则？变量定义？ | `references/mvu-mapping.md` |

**数据读取顺序**：Zod 脚本（模型）→ `[initvar]`（初始值）→ `[mvu_update]`（更新规则）。没有前两者时退回从 MVU 条目提取。

---

## 三、决策表

| 情况 | 方案 | state 写入 | 产出 |
|------|------|-----------|------|
| 没有 MVU 条目 | **纯 prompt** | — | `agents/gm.md`、`data/` |
| 只有键值状态，无骰子/公式 | **轻量** | `patchState` | 上者 + `engine/state.ts` + `get_status`/`update_status` 工具 |
| 有骰子/战斗/经济，不需一轮内精确回退 | **中等** | `patchState` + 每轮快照 | 上者 + `engine/dice.ts` 等模块 |
| 需死亡回溯/章节存档/事件级回退 | **完整 engine** | `dispatch(event)` | 事件溯源 + 全套模块 + 多 agent |

---

## 四、实现要点

### 纯 prompt 方案

产出 `agents/gm.md`（角色+世界+规则，核心规则≤5条）+ `data/world.json` + `data/characters.json`（≥5角色时拆分）+ `data/chapters.json`。开场白不进 system prompt——胶水层第一轮从 `narrator.log` 注入用户输入，详见 `references/platform-adapters.md`「开场白注入」。

### 轻量 / 中等方案

state 骨架代码见 `references/ts-engine.md`「轻量/中等方案」。中等方案加每轮快照（`snapshotBeforeTurn`），胶水层在每轮开始前调用。engine 模块按需写（`dice.ts`/`combat.ts`/`affection.ts`/`economy.ts` 等），识别信号见 `references/mvu-mapping.md`。

### 完整 engine 方案

事件溯源 + 多 agent，详见 `references/ts-engine.md` 和 `references/multi-agent-architecture.md`。

---

## 五、校验

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留" || echo "✓"
```

完整检查清单见 `references/validation.md`。

---

## references 索引

| 文档 | 适用方案 | 内容 |
|------|:---:|------|
| `design-principles.md` | 全部 | 设计原则（TS vs Python、一致性等） |
| `script-analysis.md` | MVU 卡 | tavern_helper 脚本 + regex_scripts 分类与迁移 |
| `mvu-mapping.md` | 轻量+ | MVU 条目 → engine 映射、initvar 读取、直观示例 |
| `platform-adapters.md` | 全部 | pi/CC 胶水层、开场白注入、MCP 示例 |
| `ts-engine.md` | 中等+ | TS 引擎代码（轻量 state、完整事件溯源、dice.ts） |
| `multi-agent-architecture.md` | 完整 | 多 agent 架构（GM + Narrator） |
| `storytelling.md` | 全部（可选） | 叙事节拍参考 |
| `validation.md` | 全部 | 残留检测 + 人工检查清单 |
