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
4. 先输出或草拟 `world-data/card-ir.json`；不要直接从原卡文本生成代码。
5. 从 IR 形成 Runtime Plan：archetype、event packs、state roots、visibility policy、fact sources、tool surface、subagent roles、prompt modules、validation plan。
6. 写代码前先给用户看 Runtime Plan；复杂卡还要给 state schema、event catalog、reducer/API 清单、事实源边界和子代理边界。

增量更新：先看 `git log -20` + `git diff`。只改本次需求相关文件；不碰 `sessions/`、`runtime/`、`.pi/agent/`。

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
| 不可逆拐点/隐藏真相 | 一次性开场分支、世界书一次性条目、`creator_notes` 秘密、阵营视角；可无 MVU | one-way / secret / hidden event candidates |
| TH scripts | Zod、外链、游戏脚本 | schema / mechanics / reducer hints |
| regex scripts | 非 UI 注入、状态栏 | fields + triggers；丢 UI 外壳 |
| 作者说明 | `creator_notes` | hidden rules / play constraints / visibility facts |

世界书要全量审计，含 disabled。每条给去向：data、mechanic、event-pack、setup、progressive reveal、prompt-style、discarded。

## 方案

先过退出闸门：纯设定、无可变世界、无秘密边界的卡**不转换**——收益不抵成本，向用户说明并建议直接玩原卡。过闸的卡分两档：evented light（少量可变概念，无复杂公式）、evented standard（骰子/战斗/经济/多字段联动/时间压缩）。秘密视角叠加 secret / faction / offscreen pack 与 project subagent；现实题材叠加 web/fetch/code-search 只读事实源。主表与临界场景见 `references/decision-tree.md`。

分档信号不是「卡里有没有 MVU/公式」，而是「有没有承重且必须被后续可靠查询的转换或隐藏真相」——无任何 MVU 的不可逆拐点或隐藏真相照样进 evented，满屏 MVU 先祛魅只编译承重项。展开论证与信号清单的唯一权威是 `references/decision-tree.md`。

typed tools 与 CodeAct 只是执行载体之争，取舍见 decision-tree 第二问；无论载体如何，状态变化都落成 domain event 并经 reducer。

## 多 agent 判定

多 agent 只解决认知隔离。卡复杂本身不构成拆分理由。

| 信号 | 做法 |
|---|---|
| NPC 少、无秘密 | 单 GM |
| NPC 有秘密/阵营/不同视角 | 拆 subagent |
| 悬疑答案不该进 GM context | 真相/凶手视角隔离 |
| 后台导演要读隐藏真相才有戏 | engine spawn 密闭子进程（薄接缝，非框架） |
| 只为「更聪明」 | 不拆 |

subagent 只给建议、候选事件或文本；状态写入仍由 GM 走主 engine。载体按「子代理要不要知道秘密」选：

- **in-process 顾问型**（审计、视角反应、无密候选）：project-scope、显式 tools、显式 extensions、不继承完整项目上下文/技能目录；候选类输出 bare JSON；state 投影由主进程在 `tool_call` hook 里注入 task（不自读 debug 快照）。
- **detached 密闭导演型**（知密后台平行线）：engine 自持薄 spawn 接缝——`pi -p --no-tools --no-approve --no-context-files` 密闭子进程 + engine 收割 + pending-harvest 台账；不用 subagent 框架。

详见 `references/multi-agent-architecture.md`。

## Reference 路由

| 任务 | 读 |
|---|---|
| v2 宪法 | `references/evented-runtime.md` |
| Card Semantic IR | `references/card-ir.md` |
| event pack 选择 | `references/event-packs.md` |
| 总原则 | `references/design-principles.md` |
| 方案分档与临界判定 | `references/decision-tree.md` |
| TH/regex 脚本 | `references/script-analysis.md` |
| 世界书/MVU/initvar | `references/mvu-mapping.md`（概括 MVU 前必读「MVU 实情」节；拿不准就 fetch 官方原文，不凭记忆编） |
| 开局 setup | `references/setup.md` |
| 工具抽象 / typed tools vs CodeAct / 入口收敛 | `references/tool-abstraction.md` |
| CodeAct 沙箱契约 / `.d.ts` | `references/codeact.md` |
| 数据查询层 / external research | `references/data-layer.md` |
| session state / 轻量引擎 / 记忆分层 | `references/ts-engine.md` |
| schema/migration | `references/state-schema-migrations.md` |
| pi extension/tools/prompt | `references/pi-integration.md` |
| prompt orchestrator / ST prompt_order 迁移 | `references/prompt-composition.md` |
| GM 叙事节拍素材（生成 gm prompt 时引用，GM 卡壳时读） | `references/storytelling.md` |
| 多 agent / 密闭导演 spawn 接缝 | `references/multi-agent-architecture.md` |
| 两段式结算/渲染、双模型、compaction 接管 | `references/two-pass-rendering.md` |
| 下场测试 / 三层测试轴 | `references/validation.md` |
| 工程纪律 / 目录命名 | `references/engineering-discipline.md` |

## 产出

evented light 基础：

```txt
prompts/preset.json
prompts/gm-*.md
world-data/card-ir.json
world-data/runtime-plan.json
world-data/world.json
skills/start-game/SKILL.md
start.sh
extension.ts
tools/registry.ts
engine/events.ts
engine/reducers.ts
engine/state.ts
.pi/settings.json
package.json
tsconfig.json
```

standard 按需追加：

```txt
engine/codeact.ts
engine/codeact-sandbox.d.ts
engine/migrations.ts
```

按需追加：`world-data/*_index.json`、`extensions/subagents/*.ts`、`.pi/agents/*.md`、migration/debug 工具、event-pack 测试。

小项目扁平布局即可；项目长大后按领域拆 engine 子目录、prompt 素材按 pass 分目录，且目录名拒绝歧义泛名（`data/` vs 运行时 state、`agents/` vs `.pi/agents/` 撞名等返工教训见 `references/engineering-discipline.md` 结构纪律）。

`start.sh` 从本仓库 `scripts/start.sh` 复制，保留项目级 `PI_CODING_AGENT_DIR` 隔离。

## 硬约束

各条的唯一权威在对应 reference；此处只列红线。

**State 与 engine**

- prompt 极简；计算进 engine；大数据进 data + lookup；状态变化进 domain event。
- 每个 mutable concept 必须有 event pack、变成 immutable data，或有明确丢弃理由。判据是可查询性：下游要以保证正确的方式查询它（gate 行为/防重复触发/锁单向门/隔离秘密）才立事件；能从正文重新读出、只给下一段染色的氛围留 prose。与卡里有没有 MVU 无关。
- state 写入收口到单一 runner：clone draft → 纯 `(draft, event)` 领域函数 → 校验 → commit；领域函数不碰 store，失败即不提交。
- state 真相源是 pi session custom entry；debug 导出目录只做 debug，不发布。
- schema 变更要 bump version + deterministic migration；state 类型从 schema `Static<>` 派生，不养手写平行类型。
- patch 纪律唯一权威见 `references/evented-runtime.md`：常规玩法不暴露万能 setter，裸 patch 不碰受保护路径。
- Prompt 不是防线：能落账的 GM 纪律进 state-backed ledger 由 engine 强制；强制力度与可验证性匹配（机检项硬拒，叙事项催办+留痕）。记忆侧同理：举证成本对齐记忆重量（见 `references/ts-engine.md`）。

**工具面**

- 工具契约与实现同文件；`tools/registry.ts` 只是注册清单。
- 工具清单整局稳定：不做运行时 toolset 切换，动态增删工具会毁掉 prompt cache。
- 入口收敛：同一叙事动作只有一个 LLM 可见入口——命令面板形态或 one-commit-per-turn 形态，二选一，不并存（见 `references/tool-abstraction.md` 入口收敛节）。
- 工具 description 收成「一行用途 + 边界 bullet + 禁区 bullet」；长 checklist 是 reasoning-bait（论证见 `references/engineering-discipline.md` 体量纪律节）。结构化数据不能只放 `details`；大块工具输出配共享 `renderResult`，折叠态摘要，展开态完整 `content`。
- LLM-facing tool schema 不当 serde：schema 挡基本形状，工具入口 `unknown → typed input`，归一化用共享 schema 模块而非手写 assert 克隆，错误用领域语言；engine/state 继续严格。

**Prompt 面**

- prompt 注入栈整局静态：模块开关是配置期决定，任何按当轮输入改前缀都击穿 prefix cache。用测试钉死注入模块数。规则讲清一次即可；体量该减就静态减，行为/schema 由测试锁住不变（教训与实测见 `references/engineering-discipline.md` 体量纪律节）。
- prompt orchestrator 只渲染 Runtime Plan + state projection；不读写 canonical state，不兜底领域规则，不泄露 hidden-canonical。
- 模型可见文本（身份声明、tool label、玩家面板、suggestedActions）不出现工程脚手架措辞（sandbox/framework/「本模块负责…」自报家门），换成世界内/叙事措辞；内部包名、目录、tool id 不动。结构化建议字段去主语用无主语动作短语，避免和玩家角色身份/视角人称错配。
- ST 宏、强化思考链、JSON Patch 输出格式、HTML 状态栏默认剥离，只迁移语义。

**事实源与 subagent**

- 现实题材可用 web/fetch/code-search 取代手工知识库；虚构 canonical facts 默认只走本地 world-data/lookup。
- subagent 不写 state、不拿 CodeAct、不当陪聊 NPC；后台候选必须能转成领域事件，落地前审核，secrets-at-rest gitignored。载体红线见「多 agent 判定」，细节唯一权威 `references/multi-agent-architecture.md`。

**架构与工程**

- 重叙事卡评估两段式结算/渲染拆分；是否采用及边界见 `references/two-pass-rendering.md`。
- TS 产物必须启用严格工程基线；typecheck/lint/format 不过不算完成。

## 完工

完工闸门唯一权威见 `references/validation.md`：残留扫描、人工清单、作为测试玩家 Agent 下场 20-30 轮实测，全过才算完成。报告只说已完成项和文件路径；未完成就继续做。

完工后的可选加深环节：**回访原卡**，判据与流程见 `references/validation.md`「回访原卡」节。
