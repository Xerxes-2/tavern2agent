---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 agent 平台（pi / Claude Code）时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策——这些补丁不需要了。

**核心优势**：agent 可以 loop（查询→掷骰→计算→更新→叙事，真实执行而非 LLM 脑补），可以自我纠正（算错了 dispatch 修正事件），可以动态管理上下文（数据文件 + 查询工具，而非全塞 prompt）。

## 快速开始

先确认输入是 SillyTavern 卡：PNG 需含 `chara` tEXt chunk，JSON 顶层应有 `data.name` + `data.description`（v2/v3 spec）。`extract_png.py` 拿不到 chunk 时会报错——这种情况直接告诉用户「不是 SillyTavern 角色卡」并停手。

```bash
# 如果是 PNG → 先解包
python3 scripts/extract_png.py <角色卡.png> card.json

# 如果是 JSON → 直接用

# 快速判断复杂度（只看 MVU 条目）
python3 scripts/list_entries.py card.json --filter mvu
```

- 有 MVU 条目 → 继续读 `references/mvu-mapping.md`，再按下方决策表选轻量 / 完整方案
- 没有 MVU 条目 → 纯角色 / 世界书卡，走「纯 prompt 方案」

> 脚本均位于本 skill 目录的 `scripts/`，使用相对路径调用即可（pi 与 Claude Code 都适用）。

### 脚本接口

| 脚本 | 用法 | 输出 | 退出码 |
|------|------|------|-------|
| `extract_png.py <png> [out.json]` | 从 PNG `tEXt` chunk（`chara` 或 `ccv3`）提取 base64 解码后的卡片 JSON | 给了 `out.json` 写文件并打印 `Saved to ...`；否则 JSON 打到 stdout | 找不到 chunk → `ValueError` traceback，非 0 |
| `list_entries.py <card.json> [--filter mvu\|mvu_plot\|mvu_update] [--search 关键词]` | 概览 `data.character_book.entries[]` | 人类可读列表（`[索引] 标签 注释` + 触发词 + 80 字内容预览），末尾 `显示 N / M 条` | 参数错误非 0；条目为 0 仍是 0 |
| `get_entry.py <card.json> <索引谱>` | 读单条/多条完整内容；索引谱形如 `0`、`0,3,5`、`0-5`、`0,3-5,8` | 每条打印所有字段 + 完整 `content`（不截断） | 索引全部越界非 0 |

注意：`list_entries.py`/`get_entry.py` 的输出**是给人/agent 读的格式化文本，不是机器可解析的 JSON**。需要结构化数据时直接 `python3 -c` 或加 `--json` 选项前先扩展脚本，不要 grep 现有输出。

## card.json 结构速查

```
data.name / data.description / data.personality  → 角色基础信息
data.first_mes                                    → 开场白
data.mes_example                                  → 对话示例
data.character_book.entries[]                     → 世界书条目（核心！）
  entry.comment  → 条目标题，[mvu_plot]/[mvu_update] 前缀是关键信号
  entry.keys     → 触发词（酒馆用，pi 忽略）
  entry.content  → 正文（纯文本/Markdown/JSON/EJS 模板）
data.extensions.regex_scripts[]                   → 几乎全是 UI 格式化，丢弃
```

## 决策：你需要什么

看完 `--filter mvu` 的输出后，判断：

| 情况 | 走哪条路 |
|------|---------|
| 没有 MVU 条目 | **纯 prompt 方案**：只写 system prompt，不写 engine |
| 有 MVU、但只涉及轻量状态（好感度追踪、简单计数器、无骰子/战斗） | **轻量方案**：`engine/state.ts` 骨架（见下方）+ 数据文件 + 查询工具，不搞全套 engine |
| 有 MVU、含骰子/战斗/经济/复杂状态 schema | **完整 engine 方案**：全套 engine 模块 + 多 agent 架构 |

## 纯 prompt 方案

不需要 engine。世界书条目用 `scripts/get_entry.py` 逐条读取，判断去向：
- 对话示例 → system prompt「文风示例」
- 世界观/角色描述 → system prompt「世界设定」
- 文风指引 → system prompt「规则」

输出物：
```
agents/gm.md              # system prompt（角色+世界+规则+开场白）
data/world.json           # 世界书条目数据（可选）
```

`agents/gm.md` 模板：`# <世界名> — <角色名>\n\n你是 xxx 世界的叙事者。核心原则：\n- <视角/文风约束>\n- <规则不超过 5 条>\n\n<开场白>`

## 轻量方案（有状态但无复杂游戏系统）

有少量状态（好感度、任务标记、计数器）但没有骰子/战斗。只需 state 骨架 + 读写工具。

`engine/state.ts` 最小骨架（10 行）：

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const STATE_FILE = "state/state.json";
const INITIAL_STATE: Record<string, unknown> = { /* 从 MVU 条目提取 */ };

export function getState(): Record<string, unknown> {
  if (!existsSync(STATE_FILE)) {
    mkdirSync(dirname(STATE_FILE), { recursive: true });
    writeFileSync(STATE_FILE, JSON.stringify(INITIAL_STATE, null, 2));
    return { ...INITIAL_STATE };
  }
  return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
}

export function patchState(updates: Record<string, unknown>) {
  const state = getState();
  Object.assign(state, updates);
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}
```

注册两个工具：`get_status`（查状态）、`update_status`（更新状态）。不需要事件的完整 engine。agent 自己判断何时读写。

## 完整 engine 方案（复杂游戏系统）

有骰子/战斗/经济/复杂状态 → 全套 engine + 多 agent。

## references 索引（按需查阅）

| 文档 | 纯 prompt | 轻量 | 完整 engine |
|------|:---:|:---:|:---:|
| `design-principles.md` 设计原则 | ✓ | ✓ | ✓ |
| `mvu-mapping.md` MVU 条目映射 |  | ✓ | ✓ |
| `platform-adapters.md` pi/CC 胶水 | ✓ | ✓ | ✓ |
| `multi-agent-architecture.md` 多 agent 架构 |  |  | ✓ |
| `ts-engine.md` TS 引擎参考（`initialBlankState` 是 Re:0 示例，勿照搬） |  |  | ✓ |

## 不在本 skill 范围内

遇到下列情况，明确告知用户并停手——不要硬转：

- **前端卡**：`first_mes` 是完整 HTML UI（状态面板/按钮）。可提取规则文本，但 UI 不处理。
- **群聊卡 / Group Chat**：多角色并发对话调度，需要另一套架构。
- **Tavern v3 嵌套 lorebook**：`character_book` 之外的 `world_info` 引用、跨卡 lorebook。
- **依赖 ST 扩展运行时的卡**：如 `quick reply`、`expressions`、TTS 触发——这些是 ST 客户端能力，不可移植。

## 常见失败模式

1. **regex_scripts 里藏变量逻辑**：大部分 regex 是 HTML 格式化（`<正文>` → `<div style="...">`），直接丢弃。但如果 `findRegex` 匹配的是变量模式（如 `/{{getvar:...}}/` 或状态字段名），说明它不只是格式化——提取逻辑进 engine。

2. **照搬 Re:0 的 initialBlankState**：`魔女残香`、`死亡回溯计数` 是 Re:0 特有字段。必须从当前卡的 MVU 变量定义中动态提取状态结构。

3. **把强化思考链当叙事规则保留**：「请先检查变量...再进行认知隔离...」→ 这是酒馆让 LLM 模拟推理的补丁。丢弃。

## 产出确认

- [ ] `agents/gm.md` 存在，内容 ≤ 5 条核心规则
- [ ] `agents/narrator.md` 存在（如有游戏系统）
- [ ] 如有 engine：模块覆盖了 MVU 条目的计算规则，state 结构与变量 schema 一致
- [ ] `<UpdateVariable>`、JSON Patch、强化思考链、EJS 模板已丢弃
- [ ] regex_scripts 已丢弃
- [ ] 如有 narrator agent：`first_mes` 已剥离 HTML/状态面板，作为开场纯叙事写入 `narrator.log`
