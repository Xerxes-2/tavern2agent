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
- 不靠 prompt 要求模型“别泄密 / 别乱改钱 / 记得推进时间”。
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

状态字段是 reducer 的结果，不是模型直接写的表格。

## 事件日志

复杂 runtime 必须有审计账本：

- turn log：每轮 startedAt → endedAt、时间推进、事件摘要。
- domain event log：每个事件的 actor / target / source / reason / visible consequence。
- reveal log：hidden → public 的唯一通路。

日志不一定是回滚真相源；pi session custom entry 仍是存档真相源。但日志必须能解释 state 为什么变成现在这样。

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

按需追加：`engine/migrations.ts`、`engine/codeact.ts`、`engine/codeact-sandbox.d.ts`、`extensions/subagents/*`、`.pi/agents/*`、pack-specific data。

纯设定、无运行状态、无秘密边界的卡可以生成 prompt-only 项目；这是 v2 的退化形态，不是默认范式。

## 验收

- [ ] 每个 mutable concept 都有 event pack 或明确丢弃理由。
- [ ] 没有常规玩法用的万能 state setter。
- [ ] protected paths 无法被裸 patch 改动。
- [ ] reducer 测试覆盖关键事件。
- [ ] secret/public/player knowledge 分层有测试或 fixture。
- [ ] prompt orchestrator 只渲染 Runtime Plan，不维护领域正确性。
- [ ] 下场测试证明 GM 会调用领域事件，而不是叙事里口头改状态。
