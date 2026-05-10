---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 agent 平台（pi / Claude Code）时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策——这些补丁不需要了。

**核心优势**：agent 可以 loop（查询→掷骰→计算→更新→叙事，真实执行而非 LLM 脑补），可以自我纠正（算错了 dispatch 修正事件），可以动态管理上下文（数据文件 + 查询工具，而非全塞 prompt）。

## 快速开始

输入合法性校验见下文「边界与陷阱」第一行。

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

> **大数据量卡片**（条目 ≥100、角色卡 ≥20、章节模板 ≥50）：`get_entry.py` 逐条读取效率低。直接用 `python3 -c` 写批量提取脚本—— `scripts/` 里的工具是为**探索阶段**设计的，到了**构建阶段**应切换到批量 Python。

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

## 三条 MVU 摘录 → 落点示例

帮助直观判断「这条进 prompt 还是进 engine」。同一张卡里可能三种都有：

```
# 摘录 A（来自 [mvu_update]）
好感度: 0       # 范围 -100~100
单次互动调整: ±5（友善 +5、敌对 -5、特殊事件最多 ±15）
```
→ 如果这是卡里**唯一**的游戏系统 → **轻量方案**。`INITIAL_STATE.好感度 = 0`；`gm.md` 里写「友善互动后调用 `update_status` ±5」。**不要**写 `engine/affection.ts`。
→ 但如果这张卡**已经有骰子/战斗**（即已决定走完整 engine）→ 好感度也应写成 `engine/affection.ts`，工具化处理。一致性优先。

```
# 摘录 B（来自 [mvu_plot]）
攻击判定: {{roll:1d20}} + 力量调整 vs 目标 AC
暴击: 自然 20 → 伤害 ×1.5
```
→ **完整 engine**。`engine/dice.ts` 实现 `check()`/暴击；GM prompt 只说「攻击时调 `skill_check` 工具」。

```
# 摘录 C（来自 [mvu_update]）
<强化思考要求>
step1: 检查变量是否被读取
step2: 进行认知隔离
...
```
→ **丢弃**。这是酒馆补丁，agent 不需要。

## 决策：你需要什么

看完 `--filter mvu` 的输出后，判断：

| 情况 | 走哪条路 | state 写入 | 回滚粒度 |
|------|---------|-----------|---------|
| 没有 MVU 条目 | **纯 prompt 方案**：只写 system prompt，不写 engine | — | — |
| 只涉及键值状态（好感度、计数器、任务标记），无骰子/战斗/公式 | **轻量方案**：state 骨架 + `get_status`/`update_status` 两个工具 | `patchState` | 重置即可 |
| 有骰子/战斗/经济/复杂 schema，但**不需要在一轮内部精确回退** | **中等方案**：轻量 state + 按需 `engine/dice.ts`、`engine/combat.ts` 等模块；每轮开始前快照 `state.json` | `patchState` + `snapshotBeforeTurn(turnId)` | 整轮（用户 swipe / 删消息后能回到对应轮次） |
| 含死亡回溯、章节存档、需要按事件 ID 回退 | **完整 engine 方案**：事件溯源 state + 全套模块 + 多 agent | `dispatch(event)` | 任意事件 |

注意 swipe 场景：用户回退聊天后，state 必须跟上，否则叙事和数值发散。轻量方案不在乎（值简单，重置可接受），中等方案靠每轮快照，完整方案靠重放事件。事件溯源**只为**「一轮内部精确回退」服务，没这需求别上。

## 纯 prompt 方案

不需要 engine。世界书条目用 `scripts/get_entry.py` 逐条读取，判断去向：
- 对话示例 → system prompt「文风示例」
- 世界观/角色描述 → system prompt「世界设定」
- 文风指引 → system prompt「规则」

输出物：
```
agents/gm.md              # system prompt（角色 + 世界 + 规则，不含开场白）
narrator.log              # 种子：first_mes 剥离 HTML/状态面板后的纯叙事
data/world.json           # 世界设定数据
data/characters.json      # 角色卡数据（角色≥5个时建议拆分）
data/chapters.json        # 章节剧情模板（按需加载，不预注入 prompt）
```

### 当 first_mes 是前端 HTML 说明书

部分卡片（尤其复杂系统卡）用 first_mes 承载 HTML 使用说明而非开场叙事。此时：
1. HTML 中提取可用规则文本（如系统说明、背景摘要），不处理 UI 样式
2. **合成**一段符合卡片世界观和文风的文学性开场叙事写入 `narrator.log`——不要留空
3. 合成开场应基于卡片背景描述和第一个可用章节剧情

### 角色数据独立文件

当世界书包含 ≥5 条 `<character_card>` 条目时，不要把角色描述全塞进 system prompt（token 爆炸）。提取到 `data/characters.json`，结构：
```json
{
  "角色名": {
    "性别": "…",
    "种族": "…",
    "外貌": "…",
    "性格": "…",
    "背景": "…",
    "说话特点": "…"
  }
}
```
GM 需要角色详情时通过 NPC 查询工具按需加载——**不在每轮 prompt 中注入所有角色**。

`agents/gm.md` 模板：`# <世界名> — <角色名>\n\n你是 xxx 世界的叙事者。核心原则：\n- <视角/文风约束>\n- <规则不超过 5 条>`

### 开场白怎么进 agent 的 context

`first_mes` 不进 system prompt（一次性内容，每轮注入是浪费）；也不能只放 narrator.log（那是给用户 `tail -f` 看的，agent 看不到）。**胶水层在第一轮把 narrator.log 内容前置到用户输入**——之后开场就是 chat history 的一部分，享受正常缓存：

```typescript
// pi：input 事件 + transform。用 sessionManager 判空更准确（/resume 旧会话不会误注入）
pi.on("input", async (event, ctx) => {
  if (!existsSync("narrator.log")) return;
  const hasUserMessage = ctx.sessionManager
    .getEntries()
    .some((e) => e.type === "message" && e.role === "user");
  if (hasUserMessage) return;

  const seed = readFileSync("narrator.log", "utf-8");
  return {
    action: "transform",
    text: `[系统：开场叙事如下，请基于此场景回复用户。不要复述开场。]\n\n${seed}\n\n[用户消息]\n${event.text}`,
  };
});
```

Claude Code 等价：`UserPromptSubmit` hook 同样判空注入。注入只发生一次；后续轮 agent 从 chat history 里就能看到开场。

## 轻量方案（有状态但无复杂游戏系统）

只读写键值。`engine/state.ts`：

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";

const STATE_DIR = process.env.TAVERN2AGENT_STATE_DIR ?? "state";
const STATE_FILE = join(STATE_DIR, "state.json");
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

注册两个工具：`get_status`、`update_status`。agent 自己判断何时读写。

## 中等方案（游戏系统 + 整轮回滚）

轻量 state + 按需的 engine 模块（`dice.ts` / `combat.ts` / ...）+ **每轮快照**。

在上面 `state.ts` 末尾加：

```typescript
const SNAP_DIR = join(STATE_DIR, "snapshots");

export function snapshotBeforeTurn(turnId: string) {
  if (!existsSync(STATE_FILE)) return;
  mkdirSync(SNAP_DIR, { recursive: true });
  copyFileSync(STATE_FILE, join(SNAP_DIR, `${turnId}.json`));
}

export function rollbackToTurn(turnId: string) {
  const snap = join(SNAP_DIR, `${turnId}.json`);
  if (!existsSync(snap)) throw new Error(`无快照: ${turnId}`);
  copyFileSync(snap, STATE_FILE);
}
```

胶水层挂钩：每轮开始前调 `snapshotBeforeTurn`。
- pi：`pi.on("before_agent_start", e => snapshotBeforeTurn(e.turnId))`
- Claude Code：`UserPromptSubmit` hook，turnId 用 `session_id + 自增计数` 写到 `state/turn-counter.json`

用户 swipe / 删消息后用 `rollbackToTurn` 回到对应轮次。**注意**：这只支持「整轮回退」，无法在一轮内部回退某次掷骰——需要那个就走完整方案。

### 重 roll / 回滚的可行方案（只做粗粒度）

agent 删不掉自己已经发出的 chat turn，所以「单条 swipe」做不干净。我们只支持**粗粒度回滚**：扔掉整段 chat、保留 state 到某个 snapshot，重开会话。

```typescript
// engine/state.ts 末尾再加一个工具
export function markResume(turnId: string) {
  rollbackToTurn(turnId);
  writeFileSync(join(STATE_DIR, "resume-to.txt"), turnId);
}
```

注册一个 `request_rollback(turnId)` 工具供 agent 调用。流程：

1. 用户说「回到第 5 轮重新开始」
2. agent 调 `request_rollback("5")`：state 已回滚 + 落下 `resume-to.txt`
3. agent 提示用户 `/clear`（Claude Code）/ 关掉重开（pi）
4. 启动 hook 检测 `resume-to.txt`，把 state 内容 + 一句「你回到了第 5 轮开始」前置到第一条用户消息（同开场白注入逻辑），然后删除 marker

chat 全清，state 干净，下一段叙事是基于回滚后世界的全新展开。失去这几轮的具体对白，但游戏世界一致——这正是事件溯源也无法避免的代价（chat 与 state 分层）。

需要保留对白的细粒度 reroll？必须靠平台原生「删最后一轮」API。pi 若有就用；Claude Code 没有干净接口，**不支持**——告诉用户走粗粒度，或在新一轮提示里写「重写上一段，避免雷同」。

## 完整 engine 方案（事件溯源 + 多 agent）

需要按事件 ID 任意回退（死亡回溯、章节存档）→ `dispatch`/`apply`/`rollback` 一整套，详见 `references/ts-engine.md`。

## references 索引（按需查阅）

| 文档 | 纯 prompt | 轻量 | 完整 engine |
|------|:---:|:---:|:---:|
| `design-principles.md` 设计原则 | ✓ | ✓ | ✓ |
| `mvu-mapping.md` MVU 条目映射（含「轻量方案」小节） |  | ✓ | ✓ |
| `platform-adapters.md` pi/CC 胶水 | ✓ | ✓ | ✓ |
| `multi-agent-architecture.md` 多 agent 架构 |  |  | ✓ |
| `ts-engine.md` TS 引擎参考（`initialBlankState` 是 Re:0 示例，勿照搬） |  |  | ✓ |
| `storytelling.md` 叙事节拍参考（GM 可选） | △ | △ | ✓ |

## 边界与陷阱

| 信号 | 处理 |
|------|------|
| `extract_png.py` 报「No chara/ccv3 chunk」，或 JSON 顶层没有 `data.name`/`data.description` | 不是 SillyTavern v2/v3 卡，停手 |
| `first_mes` 是完整 HTML UI（状态面板/按钮） | 前端卡，可提取规则文本，UI 不处理 |
| 多角色并发对话调度 | 群聊卡，另一套架构，停手 |
| `character_book` 之外的 `world_info`、跨卡 lorebook | v3 嵌套 lorebook，停手 |
| 依赖 `quick reply` / `expressions` / TTS 触发 | ST 客户端能力，不可移植 |
| `regex_scripts` 中 `findRegex` 匹配 `/{{getvar:...}}/` 或状态字段名 | 不只是 UI 格式化，含变量逻辑——提取进 engine 而非整体丢弃 |
| `engine/state.ts` 出现 `魔女残香`/`死亡回溯计数`/`is_changed_chapter` 等 Re:0 字段 | 从 ts-engine.md 例子照抄了——必须用本卡 MVU schema 重写 |
| `<强化思考要求>` / `step1...step2...` / `认知隔离` 被原样写进 prompt | 酒馆让 LLM 模拟推理的补丁，agent 不需要，丢弃 |
| 章节剧情模板（如 `第十五卷:终章:…`）198 条全量塞入 prompt | 提取到 `data/chapters.json`，注册章节查询工具让 GM 按需加载当前章节。不要全量预注入 prompt |
| 角色卡 ≥20 张，全部角色描述写进 agents/gm.md | token 爆炸。用 `data/characters.json` 独立存储，GM prompt 只列角色名和一句话摘要 |

## 产出确认

一行 grep 扫残留 + 误抄：

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留，逐条核对" || echo "✓ 无残留"
```

> 以下字段如果出现在 `engine/state.ts` / `engine/types.ts` 中且**用于本卡游戏逻辑**（非照抄 Re:0 示例），属于合理命中，不应判为残留：`魔女残香`、`死亡回溯计数`、`is_changed_chapter`、`好感度`、`生命值`、`魔法值` 等游戏系统原生字段。仅当这些字段出现在一张**非 Re:0 的卡**中时才需要核查。若需确认，额外跑：
> ```bash
> grep -rnE "魔女残香|死亡回溯计数|is_changed_chapter" agents/ engine/ data/ 2>/dev/null
> ```
> 逐条核对：是「本卡 MVU schema 定义的字段」→ 保留；是「ts-engine.md 的 Re:0 例子被照搬」→ 重写。

人工再过一遍：`agents/gm.md` 核心规则 ≤5 条；如有游戏系统则 `agents/narrator.md` 存在且 `tools: []`；engine 模块覆盖 MVU 计算规则、state schema 与 MVU 变量定义一致；角色数据按需拆分到 `data/characters.json`；`first_mes` 的 HTML/状态面板已剥离，纯叙事部分（或合成叙事）作为开场写入 `narrator.log`。
