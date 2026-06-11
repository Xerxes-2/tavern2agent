# Evented runtime v2

`tavern2agent` v2 不再把 SillyTavern 卡当成 prompt/worldbook/status 的集合翻译。它把卡片当成一个待编译的叙事领域模型：

```txt
SillyTavern card
  → Card Semantic IR
  → Runtime Plan
  → Event Packs + State Schema + Reducers + Tools
  → Prompt Orchestrator
  → pi-native narrative runtime
```

核心宪法：**prompt 描述世界，领域事件改变世界。**

## 硬切边界

旧范式废弃：

- 不生成万能 `update_state` / `patch_state` 作为常规玩法入口。
- 不把 ST 状态栏字段直接暴露成 LLM 可改字段。
- 不把世界书整块塞进 prompt。
- 不靠 prompt 要求模型「别泄密 / 别乱改钱 / 记得推进时间」。
- 不为了兼容 ST 宏保留运行时 alias、旧字段 fallback 或旧工具入口。

唯一保留的兼容层是：持久化 state 的程序化 migration。卡片输入解析可以兼容 ST v1/v2/v3；生成后的 runtime 不兼容旧运行时概念。

## 分层

### Card Semantic IR

IR 是卡片语义的唯一中间层。它保留作者意图，不保留 ST 运行时补丁。详见 `references/card-ir.md`。

### Runtime Plan

Runtime Plan 把 IR 转成生成决策：

```txt
runtimePlan = {
  archetypes,
  selectedEventPacks,
  stateRoots,
  hiddenPublicPolicy,
  toolSurface,
  promptModules,
  validationPlan
}
```

它是 prompt orchestrator、engine scaffold、tools scaffold 和测试生成的共同输入。

### Event Packs

Event pack 是扩展单位。每个 pack 交付：

- event 类型
- state root / schema 片段
- reducer
- LLM-facing tool 或 CodeAct API
- tool-policy prompt 片段
- tests

详见 `references/event-packs.md`。

### Fact Source Layer

事实读取走独立的事实源层，不靠 prompt 塞料。Runtime Plan 应声明事实源：

```txt
local lookup      卡片 canonical facts：NPC、地点、规则、秘密索引
external research 现实题材 / 开源项目 / 活资料：web_search、fetch_content、code_search
```

虚构世界默认 local lookup 优先并禁用 web；现实题材可以用 research 工具取代手工知识库。research 结果是只读证据，不能自动写 state。

### Prompt Orchestrator

轻量提示词编排器位于最后一层。它吃 Runtime Plan 和 state projection，输出 prompt bundle。它不能维护领域正确性，也不能替代 reducer / tool invariant。

```txt
Runtime Plan + State Projection → prompt modules
```

编排器允许做：模块排序、条件注入、token budget、style/output contract、tool-policy 渲染。

编排器禁止做：读写 canonical state、兼容旧字段、从 prompt 里兜底修正领域规则、把 hidden truth 注入 public context。

## 领域事件流水线

所有可变世界都走同一条链：

```txt
LLM tool call / CodeAct command
  → tool normalizer: unknown → typed domain input
  → domain event
  → reducer
  → canonical state
  → event / turn log
  → state projection
  → prompt orchestrator
```

状态字段由 reducer 产出，模型无权直接编辑。

## Patch 纪律

本节是裸 patch 规则的唯一权威；其他文档只引用，不另立清单。

受保护路径——凡有规则的字段，禁止裸 `patch`：

- 金钱/资源
- 背包/装备
- 技能/经验/等级/属性点
- 任务/章节/scene objective
- 好感/关系
- 场景/地点/时间
- hidden/public 可见性边界

规则：

- 受保护字段必须走领域事件、组合函数或 scene/action API；常规玩法不暴露 `update_state` / `patch_state` 这类万能 setter。
- `patch` 只用于 debug/setup/migration，description 标明 debug-only；不靠运行时 toolset 切换隔离（动态增删工具毁 prompt cache）。
- `patch` 命中受保护路径时 throw，并提示正确事件/函数。
- 若保留 patch 兜底，每次必须有 reason，且只能改无规则、无联动的 cosmetic 字段。

## 事件日志

复杂 runtime 必须有审计账本：

- turn log：每轮 startedAt → endedAt、时间推进、事件摘要。
- domain event log：每个事件的 actor / target / source / reason / visible consequence。
- reveal log：hidden → public 的唯一通路。

日志不一定是回滚真相源；pi session custom entry 仍是存档真相源。但日志必须能解释 state 为什么变成现在这样。

## 引擎台账：Prompt 不是防线

GM 纪律凡是能落账的，从 prompt 搬进 state-backed ledger 由 engine 强制。prompt 级纪律在 compaction 时死亡、无法审计、随上下文增长静默退化；台账靠构造在 compaction 后存活，且给审计工具对账的科目而非要通读的转录。三类已实证的台账：

- **回合义务账**（obligations ledger）：裁决类工具（如战斗交换）登记必须落地的状态变化，领域事件按 FIFO 销账；任何债务未清，`commit_turn` 整体硬拒。
- **阵营时钟 / 排程事件**：BITD 式进度钟，到期/填满项在 canonical commit 返回值里催办（dunning）。
- **悬念钩子账**：钩子生命周期入 state，同时施压钩子设硬上限（如 2 条），每次重现强制写 novelty。

强制力度与可验证性匹配：漏掉一个 `add-wound` 事件是机器可查的 → 硬拒；时钟/钩子的叙事跟进不可机检 → 只催办 + 强制留痕（outcomeSummary、novelty、reason），对不可验证的主张上硬闸只会训练出空话填表。硬拒之所以可负担，前提是两段式拆分让结算侧幕后重试（见 `two-pass-rendering.md`）。

## 时间与 turn envelope

只要 runtime 有连续叙事，canonical turn 必须带时间裁决：

```txt
elapsed  非移动耗时
travel   地点移动
```

没有 `none`。瞬间反应也至少落成一个最小 elapsed 单位，除非该项目明确是无时间轴的纯聊天卡。

## Visibility policy

IR 和 Runtime Plan 必须区分：

| 层 | 含义 | 落点 |
|---|---|---|
| player-only | 现实玩家知道，角色未必知道 | 不写 public state；最多进入 GM guard |
| protagonist-known | 玩家角色知道 | protagonist memory / actor public facts |
| scene-public | 场景中他人也知道 | public state / public memory |
| hidden-canonical | 真实存在但未公开 | secrets / hidden state / subagent context |

秘密身份、真名、凶手、幕后动机、未发现地图等，不得因为 ST 卡写在 prompt 里就进入 public memory。

## Subagent roles

subagent 是后台导演组/审计器；禁止充当陪聊 NPC 或状态写入器。Runtime Plan 可以声明：

```txt
perspective/secret       NPC 或阵营秘密视角
parallel-line/offscreen  后台事件候选
timeline/showrunner      drift、beat closure、NPC autonomy 审计
```

所有 subagent 必须 project-scope、显式 tools、显式 extensions；不继承完整项目上下文和技能目录。候选输出由 GM 审核后转成 domain event。

## 生成物基线

有任何 mutable concept 的项目，至少生成：

```txt
data/card-ir.json
data/runtime-plan.json
engine/state.ts
engine/events.ts
engine/reducers.ts
tools/registry.ts
agents/preset.json
agents/gm-*.md
skills/start-game/SKILL.md
```

按需追加：`engine/migrations.ts`、`engine/codeact.ts`、`engine/codeact-sandbox.d.ts`、`extensions/subagents/*`、`.pi/agents/*`、pack-specific data、external research tool wiring。

纯设定、无运行状态、无秘密边界的卡可以生成 prompt-only 项目；这是 v2 的退化形态，仅限满足上述条件的卡。

## 验收

完工闸门唯一权威见 `references/validation.md`：残留扫描、人工清单、下场实测。本文所有约束都已进入该闸门。
