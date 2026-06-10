---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 pi coding agent 时使用；覆盖纯 prompt、世界书、MVU、骰子、战斗、好感度、经济、隐藏信息、多 agent 场景。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent

把 SillyTavern 卡编译成 pi-native 互动叙事 runtime。还原作者想做的游戏：prompt 描述世界，领域事件改变世界，engine/reducer 维护正确性，session 保存存档。不复刻 ST 宏、COT、JSON Patch、HTML 状态栏，不把状态栏字段搬进 `patch_state`。

## 开工

1. 解包卡片，确认输出目录。目录存在时先问：覆盖、增量、另建？
2. 先读 `references/evented-runtime.md`、`references/card-ir.md`、`references/event-packs.md`、`references/design-principles.md`。
3. 全量审计 `data` 字段、世界书、TH scripts、regex scripts、开场白。
4. 先输出或草拟 `data/card-ir.json`；不要直接从原卡文本生成代码。
5. 从 IR 形成 Runtime Plan：archetype、event packs、state roots、visibility policy、fact sources、tool surface、subagent roles、prompt modules、validation plan。
6. 写代码前先给用户看 Runtime Plan；复杂卡还要给 state schema、event catalog、reducer/API 清单、事实源边界和子代理边界。

增量更新：先看 `git log -20` + `git diff`。只改本次需求相关文件；不碰 `sessions/`、`state/`、`.pi/agent/`。

## 探索命令

```bash
python3 scripts/extract_card.py <card.png|webp|jpg|json> card.json
python3 scripts/list_entries.py card.json
python3 scripts/list_entries.py card.json --filter mvu
python3 scripts/list_entries.py card.json --filter initvar
python3 scripts/get_entry.py card.json <index>
```

脚本支持 v1/v2/v3。v1 会归一化为 v2；v3 的 `group_only_greetings` 按 `alternate_greetings` 处理。

## 信息源 → IR

| 看什么 | 路径/信号 | IR 产出 |
|---|---|---|
| 基础设定 | `description/personality/scenario/system_prompt` | persona / settingFacts / style |
| 开场 | `first_mes/alternate_greetings/group_only_greetings` | openings / playerSetup / route signals |
| 世界书 | `character_book.entries[]` | worldbookEntries + disposition |
| 初始状态 | `[initvar]`、YAML、变量表 | mutableConcepts initial values |
| 规则更新 | `[mvu_update]`、变量变化 | mechanics + event candidates |
| TH scripts | Zod、外链、游戏脚本 | schema / mechanics / reducer hints |
| regex scripts | 非 UI 注入、状态栏 | fields + triggers；丢 UI 外壳 |
| 作者说明 | `creator_notes` | hidden rules / play constraints / visibility facts |

世界书要全量审计，含 disabled。每条给去向：data、mechanic、event-pack、setup、progressive reveal、prompt-style、discarded。

## 方案

三档：prompt-only（纯设定，无可变世界、无秘密边界）、evented light（少量可变概念，无复杂公式）、evented standard（骰子/战斗/经济/多字段联动/时间压缩）。秘密视角叠加 secret / faction / offscreen pack 与 project subagent；现实题材叠加 web/fetch/code-search 只读事实源。主表与临界场景见 `references/decision-tree.md`。

typed tools 与 CodeAct 只是执行载体之争，取舍见 decision-tree 第二问；无论载体如何，状态变化都落成 domain event 并经 reducer。

## 多 agent 判定

多 agent 只解决认知隔离。卡复杂本身不构成拆分理由。

| 信号 | 做法 |
|---|---|
| NPC 少、无秘密 | 单 GM |
| NPC 有秘密/阵营/不同视角 | 拆 subagent |
| 悬疑答案不该进 GM context | 真相/凶手视角隔离 |
| 只为「更聪明」 | 不拆 |

subagent 只给建议、候选事件或文本；状态写入仍由 GM 走主 engine。生成的 subagent 必须 project-scope、显式 tools、显式 extensions、不继承完整项目上下文/技能目录；候选类输出 bare JSON。详见 `references/multi-agent-architecture.md`。

## Reference 路由

| 任务 | 读 |
|---|---|
| v2 宪法 | `references/evented-runtime.md` |
| Card Semantic IR | `references/card-ir.md` |
| event pack 选择 | `references/event-packs.md` |
| 总原则 | `references/design-principles.md` |
| 方案分档与临界判定 | `references/decision-tree.md` |
| TH/regex 脚本 | `references/script-analysis.md` |
| 世界书/MVU/initvar | `references/mvu-mapping.md` |
| 开局 setup | `references/setup.md` |
| 工具抽象 / typed tools vs CodeAct 取舍 | `references/tool-abstraction.md` |
| CodeAct 沙箱契约 / `.d.ts` | `references/codeact.md` |
| 数据查询层 / external research | `references/data-layer.md` |
| session state / 轻量引擎 | `references/ts-engine.md` |
| schema/migration | `references/state-schema-migrations.md` |
| pi extension/tools/prompt | `references/pi-integration.md` |
| prompt orchestrator / ST prompt_order 迁移 | `references/prompt-composition.md` |
| toolset 切换 | `references/toolsets.md` |
| 多 agent | `references/multi-agent-architecture.md` |
| 下场测试 | `references/validation.md` |
| 工程纪律 | `references/engineering-discipline.md` |

## 产出

prompt-only 退化形态：

```txt
agents/preset.json
agents/gm-*.md
data/card-ir.json
data/runtime-plan.json
data/world.json
skills/start-game/SKILL.md
start.sh
```

evented light / standard 追加：

```txt
extension.ts
tools/registry.ts
engine/events.ts
engine/reducers.ts
engine/state.ts
.pi/settings.json
```

standard 按需追加：

```txt
engine/codeact.ts
engine/codeact-sandbox.d.ts
engine/migrations.ts
```

按需追加：`data/*_index.json`、`extensions/subagents/*.ts`、`.pi/agents/*.md`、migration/debug 工具、event-pack 测试。

## 硬约束

- prompt 极简；计算进 engine；大数据进 data + lookup；状态变化进 domain event。
- 每个 mutable concept 必须有 event pack、变成 immutable data，或有明确丢弃理由。
- patch 纪律唯一权威见 `references/evented-runtime.md`：常规玩法不暴露万能 setter，裸 patch 不碰受保护路径。
- ST 宏、强化思考链、JSON Patch 输出格式、HTML 状态栏默认剥离，只迁移语义。
- state 真相源是 pi session custom entry；`state/` 只做 debug export，不发布。
- schema 变更要 bump version + deterministic migration。
- 工具 description 写调用场景和禁区；结构化数据不能只放 `details`。
- LLM-facing tool schema 不要用复杂 union/enum 当 serde；schema 挡基本形状，工具入口 `unknown → typed input`，错误用领域语言，engine/state 继续严格。
- prompt orchestrator 只渲染 Runtime Plan + state projection；不读写 canonical state，不兜底领域规则，不泄露 hidden-canonical。
- 现实题材可用 web/fetch/code-search 取代手工知识库；虚构 canonical facts 默认只走本地 data/lookup。
- subagent 不写 state、不拿 CodeAct、不当陪聊 NPC；后台候选必须能转成领域事件。
- `start.sh` 从本仓库 `scripts/start.sh` 复制，保留项目级 `PI_CODING_AGENT_DIR` 隔离。
- TS 产物必须启用严格工程基线；typecheck/lint/format 不过不算完成。

## 完工

完工闸门唯一权威见 `references/validation.md`：残留扫描、人工清单、作为测试玩家 Agent 下场 20-30 轮实测，全过才算完成。报告只说已完成项和文件路径；未完成就继续做。
