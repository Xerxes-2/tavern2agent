---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 pi coding agent 时使用；覆盖纯 prompt、世界书、MVU、骰子、战斗、好感度、经济、隐藏信息、多 agent 场景。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent

把 SillyTavern 卡转成 pi 原生文字游戏项目。目标不是复刻 ST 宏、COT、JSON Patch、HTML 状态栏，而是还原作者想做的游戏：prompt 管叙事，data 管事实，engine 管计算，session 管存档。

## 开工

1. 解包卡片，确认输出目录。目录存在时先问：覆盖、增量、另建？
2. 先读 `references/design-principles.md`。
3. 全量审计 `data` 字段、世界书、TH scripts、regex scripts、开场白。
4. 按下表加载 reference。
5. 写代码前先给用户看方案；标准方案还要给 state schema + engine API 清单。

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

## 信息源

| 看什么 | 路径/信号 | 产出 |
|---|---|---|
| 基础设定 | `description/personality/scenario/system_prompt` | `agents/gm-*.md` |
| 开场 | `first_mes/alternate_greetings/group_only_greetings` | `skills/start-game/SKILL.md` |
| 世界书 | `character_book.entries[]` | `data/*.json` / engine / 丢弃清单 |
| 初始状态 | `[initvar]`、YAML、变量表 | `INITIAL_STATE` |
| 规则更新 | `[mvu_update]`、骰子、伤害、经济 | CodeAct / 轻量工具 |
| TH scripts | Zod、外链、游戏脚本 | schema / engine |
| regex scripts | 非 UI 注入、状态栏 | 保留逻辑，丢 UI |
| 作者说明 | `creator_notes` | 隐藏规则、玩法约束 |

世界书要全量审计，含 disabled。每条给去向：data、engine、setup 选项、渐进披露、丢弃。

## 方案

| 条件 | 方案 | 形态 |
|---|---|---|
| 纯设定，无运行状态 | prompt | `agents/` + `data/` + start skill |
| 少量键值状态，无复杂公式 | light | 加 `engine/state.ts`、`get_status`、`patch_state` |
| 骰子/战斗/经济/多字段联动/时间压缩/级联 | standard | CodeAct：`code_act` + session-backed state |

标准方案默认 CodeAct。不要默认生成一堆 `dice/combat/economy/attention` 工具；把规则收进沙箱 API。详见 `references/codeact.md`。

## 多 agent 判定

多 agent 是认知隔离，不是复杂度奖励。

| 信号 | 做法 |
|---|---|
| NPC 少、无秘密 | 单 GM |
| NPC 有秘密/阵营/不同视角 | 拆 subagent |
| 悬疑答案不该进 GM context | 真相/凶手视角隔离 |
| 只为“更聪明” | 不拆 |

subagent 只给建议或文本；状态写入仍由 GM 走主 engine。详见 `references/multi-agent-architecture.md`。

## Reference 路由

| 任务 | 读 |
|---|---|
| 总原则 | `references/design-principles.md` |
| 方案拿不准 | `references/decision-tree.md` |
| TH/regex 脚本 | `references/script-analysis.md` |
| 世界书/MVU/initvar | `references/mvu-mapping.md` |
| 开局 setup | `references/setup.md` |
| CodeAct 标准方案 | `references/codeact.md` |
| 数据查询层 | `references/data-layer.md` |
| session state / 轻量引擎 | `references/ts-engine.md` |
| schema/migration | `references/state-schema-migrations.md` |
| pi extension/tools/prompt | `references/pi-integration.md` |
| toolset 切换 | `references/toolsets.md` |
| 多 agent | `references/multi-agent-architecture.md` |
| 下场测试 | `references/validation.md` |
| 目标模型特化 | `references/models/<model>.md` |
| 工程纪律 | `references/engineering-discipline.md` |

## 产出

最小：

```txt
agents/gm.md
data/world.json
skills/start-game/SKILL.md
start.sh
```

轻量/标准追加：

```txt
extension.ts
tools/registry.ts
engine/state.ts
.pi/settings.json
```

标准追加：

```txt
engine/codeact.ts
engine/codeact-sandbox.d.ts
```

按需追加：`data/*_index.json`、`extensions/subagents/*.ts`、`.pi/agents/*.md`、migration/debug 工具。

## 硬约束

- prompt 极简；计算进 engine；大数据进 data + lookup。
- ST 宏、强化思考链、JSON Patch 输出格式、HTML 状态栏默认剥离。
- state 真相源是 pi session custom entry；`state/` 只做 debug export，不发布。
- schema 变更要 bump version + deterministic migration。
- 工具 description 写调用场景和禁区；结构化数据不能只放 `details`。
- `start.sh` 从本仓库 `scripts/start.sh` 复制，保留项目级 `PI_CODING_AGENT_DIR` 隔离。
- TS 产物必须启用严格工程基线；typecheck/lint/format 不过不算完成。

## 完工

1. 跑残留扫描：见 `references/validation.md`。
2. 你作为测试玩家 Agent 下场玩至少 20-30 轮，覆盖主要系统；你可以明说自己在测试，请 GM 配合触发场景。
3. 标准方案确认 `code_act` 被调用，且脚本使用组合/场景 API，不只裸 patch。
4. TS 项目通过 typecheck/lint/format。
5. 所有 alternate greetings、disabled entries、世界书条目都有去向。
6. 报告只说已完成项和文件路径；未完成就继续做。
