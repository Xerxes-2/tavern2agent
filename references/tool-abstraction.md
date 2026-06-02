# 工具抽象设计

RP 工具的目标不是「让模型能改 state」，而是让 GM 以自然叙事决策单位安全提交世界变化。不要按数据库字段切工具，也不要把复杂工作流写进 prompt 让模型背；把工作流做成可执行的高层 API。

核心原则：**入口宽，核心严**。

- 入口宽：接受模型自然表达，例如 flat payload、自然语言 handle、`current` / `all` 上下文引用、事务摘要默认 reason。
- 核心严：engine 仍严格维护 canonical state、protected paths、hidden/public 边界和领域不变量。

CodeAct 是实现这套抽象的一种载体，不是唯一答案。稳定、可枚举的场景动作可以做成 typed pi tools；计算、循环、批量结算和时间压缩更适合 CodeAct 沙箱。

## 选择取舍

CodeAct 和 typed pi tools 都可以承载同一套 API 架构。区别是执行载体：

```txt
CodeAct       GM 写受限 JS，调用沙箱 API 完成一段状态命令
Typed tools   GM 调 pi tools；工作流由每个工具 interface 固化
```

优先用 CodeAct：

- 战斗、经济、任务、日程、经营、好感、伤害等规则需要多字段联动。
- 一轮经常要计算、循环、筛选、批量处理 NPC / 物品 / 日程。
- 时间压缩需要连续推进多个时段，并在中途触发事件。
- 公式、随机、条件分支比「调用几个固定工具」更自然。
- 若生成一堆 `dice/combat/economy/task` 独立工具，工具面会爆炸。

优先用 typed deep tools：

- 规则稳定，核心动作能枚举成少数深 interface。
- hidden/public、权限、锁定事实、审计边界很强，不希望 GM 写临时脚本靠近 raw state。
- 需要 TypeScript 编译期约束、细粒度单元测试和明确工具审计。
- 场景动作比公式计算更重要，例如 `start_scene_beat`、`finish_current_beat`、`commit_turn`、`set_scene_presence`。

可以混合：typed tools 管核心 state seam，CodeAct 只管局部高复杂结算。

```txt
主状态写入：start_scene_beat / finish_current_beat / commit_turn / record_memory / reveal_secret
局部 CodeAct：combat_exchange / rest_period / investigation_pass / downtime_sim
```

无论选哪种，不要让模型背工作流；把工作流变成可执行 API。

## 高层设计准则

### LLM 没有 LSP

人类写代码时有类型提示、字段补全、必填红线、hover 文档和编译器定位；模型调用工具时往往是在盲写 JSON。复杂 nested payload 会逼模型手写无 LSP 的 transaction AST，因此“低级错误”通常是 interface 错，不是 prompt 不够严。

工具应像命令面板，而不是像函数签名大全：

```txt
好：finish_current_beat(outcome, memory?, nextBeat?)
差：commit_turn(events: [{ kind: "scene-beat", event: { kind: "transition-beat", input: { completedBeatId, nextBeat: { storyWindow... } } } }])
```

设计目标：让模型选择叙事命令，并填写少量玩家可见字段；内部 ID、当前 beat、arc、objective id、默认 reason、storyWindow 账本字段由工具补齐。

### Macro 覆盖后要隐藏半底层工具

高频叙事动作一旦有 macro tool，就不要继续把它覆盖的半底层工具暴露给 GM，否则模型会在多个近似入口之间摇摆。

```txt
保留可见：start_scene_beat, finish_current_beat, commit_turn
隐藏/降级：scene_beat begin/transition 的直接工具入口
保留内部：beginSceneBeat, transitionSceneBeat, moveToSceneBeat engine functions
```

原则：

- scene/action macro 是日常入口。
- turn commit 是非常规组合 / fallback。
- domain primitives 可以继续存在于 engine 和测试中，但不一定注册成 LLM 可见工具。
- debug/toolset 开关若不能真正控制工具可见性，就是假 affordance，应删除。

### 按叙事决策单位建模

工具对应 GM 的叙事动作，而不是 state 字段：进入调查、完成撤退、休息一晚、采购整备、战斗交换、记录长期后果。若模型经常连续调用 3 个以上工具完成同一类动作，说明缺少更深的 scene/action API 或 turn commit API。

高频动作应有 macro：

```txt
start_scene_beat     开启复杂 beat，自动补 arc/beat/storyWindow 默认字段
finish_current_beat  收口当前 beat，自动读取 currentBeatId、解决当前目标、可选记录 memory/nextBeat
settle_purchase      购买：资金扣减 + 可选 tracked item + 交易 memory
record_reveal        secret reveal + public memory claim
settle_rest          时间推进 + 恢复/代价 + offscreen hooks
```

不要让模型手写内部账本字段：`currentArcId`、`currentBeatId`、`completedBeatId`、`objectiveId`、`storyWindow.allowedActions` 这类字段应尽量由工具从当前上下文推导或自动生成。

### 子事件像原工具调用

组合工具应像「批量调用领域工具」，不要要求模型学习一套额外 DSL。

好：

```ts
commitTurn({
  summary: "进入新都调查并采购",
  events: [
    { kind: "scene-beat", event: { kind: "move-location", location, storyWindow, objectives } },
    { kind: "economy", event: { kind: "spend-money", ownerActorId: "protagonist", amount: 3500 } },
  ],
});
```

差：

```ts
commitTurn({
  events: [{ kind: "scene-beat", event: { kind: "move-location", input: { location } } }],
});
```

如果内部实现需要嵌套，也要兼容 flat payload。

### 事务字段向下继承

事务层全局字段应能为子事件提供同语义默认值：

```txt
commit.summary → event.reason
turn.actorId   → child event actorId
turn.source    → child event source
```

不要让模型重复写同一段 reason；重复字段越多，失败点越多。默认值只能填同语义字段，不能凭空猜业务事实。

### 当前上下文优先于内部 ID

RP 模型最自然的引用顺序：

```txt
当前上下文 > 领域主体 / 自然语言 handle > 内部 ID
```

优先提供：`current beat`、`resolveAllObjectives`、`ownerActorId`、角色别名、objective summary、item label、claim + evidence。内部 ID 可以返回给日志和精确操作，但不要成为唯一入口。

### 复杂 beat 成对设计入口和出口

复杂场景不只需要进入接口，也需要收口接口。

```txt
入口：start_scene_beat / moveToBeat
  移动 + 时间 + title + objectives + threats + presence；内部补 storyWindow/beatId

出口：finish_current_beat / completeBeat
  当前 beat 完成 + 关闭窗口 + 可选 nextBeat + memory + presence
```

只做入口不做出口，会留下悬挂 storyWindow、未清 objective、漏写 memory 等问题。

### Runtime optional 必须真的 optional

tool schema 里 optional 的字段，在 engine 里必须有默认值或领域错误。

```txt
optional array  → default []
optional object → default null 或明确报缺字段
optional next   → default no next beat
```

禁止出现 `ids is not iterable` 这类实现泄漏；应改成「仍有未解决目标，可用 resolveAllObjectives=true」。

## 四层 API

```txt
scene/action 层        GM 的叙事动作：进入场景、完成 beat、战斗交换、休息、购物、调查
turn commit 层         一轮内多个状态变化的事务收口：按顺序提交、验证、返回 warnings
domain composition 层  常用领域联动：交易、推进时间、结算任务、转移物品、记录后果
primitive/debug 层     status、lookup、log、assert、受保护低层事件；patch 只 debug/兜底
```

规则：

- GM 优先用最高层；覆盖不到再降层。
- 有「持续活动 + 结算 + 事件」就建 scene/action 层。
- 一轮内多个状态变化要有 turn commit / transaction。
- `patch` 只能 debug 或兜底，不能绕过有规则的组合函数。

### Scene / Action

scene 层不是题材分类，而是 GM 的一次叙事承诺。API 名称尽量贴近玩家行动句子：

```ts
declare function startSceneBeat(input: StartSceneBeatInput): SceneBeatResult;
declare function finishCurrentBeat(input: FinishCurrentBeatInput): SceneBeatTransitionResult;
declare function combatExchange(input: CombatExchangeInput): CombatResult;
declare function restPeriod(input: RestInput): RestResult;
declare function shoppingTrip(input: ShoppingInput): ShoppingResult;
declare function investigationPass(input: InvestigationInput): InvestigationResult;
```

好 API：

```ts
startSceneBeat({
  title: "柳洞寺外围侦察",
  objectives: ["确认结界", "安全撤回"],
  purpose: "前往柳洞寺外围确认结界边界",
  location: "柳洞寺外围",
  elapsedMinutes: 35,
});

finishCurrentBeat({
  outcome: "结界边界确认完成，队伍安全撤回",
  nextBeat: { title: "撤回后的情报整理", objectives: ["决定是否夜探山门"] },
});
```

差 API：

```ts
patch([{ path: "/scene/location", value: "柳洞寺" }]);
patch([{ path: "/scene/objectives/0", value: "确认结界" }]);
```

### Turn Commit / Transaction

turn commit 横跨 scene、memory、economy、condition 等领域，解决「一轮回复中多个状态变化如何按顺序安全落地」。它不是 scene/action 的子项。

```ts
declare function commitTurn(input: {
  summary: string;
  events: TurnEvent[];
}): TurnCommitResult;
```

用途：

- 一轮回复有多个状态变化。
- 需要保证事件顺序。
- 需要统一验证 completion / protected path / hidden-public 边界。
- 需要在叙事前返回 warnings、before/after、narrative hooks。

例：

```ts
commitTurn({
  summary: "撤回卫宫宅并记录柳洞寺侦察发现",
  events: [
    scene.completeBeat({ resolveAllObjectives: true }),
    scene.moveLocation({ location: "卫宫宅", elapsedMinutes: 35 }),
    memory.recordMajorEvent({ title: "柳洞寺外围侦察", summary: "山门是唯一入口" }),
  ],
});
```

## Natural handles

工具 API 应尽量接受玩家可见文本、当前上下文和领域主体，并在内部匹配。

优先支持：

- current beat / current scene
- `resolveAllObjectives` / `clearCurrentThreats` 这类 current-context 操作
- actor display name / alias / `ownerActorId`
- objective summary 或 summary 片段
- item label / location label
- claim + evidence
- memory title

自然语言 handle 至少支持精确匹配和包含匹配。模型很少稳定逐字复述 objective summary；`"检查地面、墙角和排水沟"` 应能匹配 `"沿魔力波动外围用構造把握检查地面、墙角和排水沟"`。多候选时报 ambiguity，并列出候选。

## Protected paths

凡有规则的字段，禁止裸 `patch`：

- 金钱/资源
- 装备/背包
- 技能/属性点
- 任务/章节/Scene Objective
- 好感/关系
- 场景/时间
- hidden/public 可见性边界

这些必须走组合函数或 scene/action API。`patch` 命中受保护路径时 throw，并提示正确函数。standard 方案中 `patch` 应逐步降级为 debug-only；若保留兜底，每次必须有 reason，且只能改无规则、无联动的 cosmetic 字段。

## 错误设计

错误信息是给模型恢复用的 prompt。不要只说 failed；要返回下一次调用所需参数。

```txt
unknown actor: caster。请先 materialize actor：upsert_actor / addActor。
unresolved beat: 仍有未解决目标，可用 resolveAllObjectives=true。候选：...
ambiguous item label: 宝石。候选：宝石项链、红宝石吊坠。
protected path /economy/funds: 请使用 adjustMoney / purchase。
```

工具应主动拒绝常见错法：

- 漏 reason，且无法从事务 summary 派生。
- 未解决 objective 就 transition。
- 写入不存在 actor。
- secret 写进 public memory。
- 用 patch 改受保护字段。
- 多状态收口却绕过 turn commit。

## Prompt 要点

写进 GM 规则：

- 状态变化、掷骰、时间推进、经济/战斗/任务结算必须走工具或 CodeAct。
- 一轮多个状态变化优先用最贴近叙事意图的 macro；非常规组合才用 `commitTurn` / transaction。
- 时间跳跃用一段 scene/advance 序列，不拆成多轮。
- 脚本或工具调用只做机械层；叙事在工具返回后写。
- 不调用工具就不能声称状态已改变。

工具 description 写四件事：

1. 必须调用场景。
2. 严禁行为。
3. 四层优先级：scene/action > turn commit / transaction > domain composition > primitive/debug。
4. 若是 CodeAct，嵌入 `.d.ts`。

## 交互测试驱动加深

下场测试不是只确认工具被调用，而是观察模型实际怎么误用 API。

记录这些信号：

- 模型是否频繁降层。
- 是否漏 reason，或重复写相同 reason。
- 是否记不住内部 id / purse id / objective id。
- 是否自然写 flat payload，而 API 只接受 nested payload。
- 是否想表达「当前 beat 全部完成」，但 API 要求逐条列 objective。
- 是否把多个状态变化拆散。
- 是否先叙事后工具。
- 是否把 hidden truth 写进 public。
- 工具失败后是否能恢复。

如果同一种误用重复出现，按顺序处理：

1. 加深 scene/action macro API。
2. 接受模型自然参数形状，例如 flat payload。
3. 增加 natural handle / current-context 操作。
4. 给事务字段增加安全默认值，例如 `summary → reason`。
5. 加 validator / protected path。
6. 改错误信息提示正确路径和候选。
7. 若 macro 已覆盖半底层工具，隐藏或删除半底层可见入口，减少选择分叉。
8. 最后才改 prompt 文案。

不要用 prompt 长期弥补坏 interface。

## CodeAct 章节

CodeAct 是四层 API 的一种执行方式：单个 `code_act` 工具承载 typed command layer。GM 写受限 JS，沙箱执行计算、随机、状态写入、查询，再把结构化结果交给 GM 叙事。

纯 prompt / light 不要套 CodeAct。CodeAct 不是让 LLM 在沙箱里写小说，也不是自由脚本入口；沙箱只产机械结果、结算摘要和叙事钩子。

### CodeAct 适用点

- 多步结算要跨很多 tool call。
- LLM 容易忘顺序或心算错误。
- 状态扫描、条件分支、批量结算和时间压缩很难一轮完成。

看到 prompt 里出现「先 A，再 B，再 C，最后 D」时，优先考虑把这个工作流做成 CodeAct API 或深 typed tool，而不是继续加自然语言纪律。

### 沙箱契约

沙箱用 `node:vm`（`vm.createContext` + `vm.Script.runInContext`），不是 `child_process`、`eval` 或 Docker。

- 写函数返回结构化结果，如 `{ before, after }`、`{ settlement, events, hooks }`。
- 写函数自动 log 人类可读摘要。
- 查询未命中 throw，供脚本 try/catch。
- `status()` 返回 clone，不给 state 引用。
- 禁止 fs/process/require/import 等 host 出口。
- 设置超时，防死循环。
- 执行后 dirty state 走 session-backed state 链路。
- 脚本中只做机械层；不要生成小说正文。

### `.d.ts` 是 API 权威

为沙箱暴露函数写 `engine/codeact-sandbox.d.ts`。它同时服务：

- GM 每轮看到的函数签名。
- 沙箱实现的类型检查。
- 工具 description 的权威 API 段。

示意：

```ts
declare function status(): Readonly<WorldState>;
declare function log(message: string): void;
declare function lookup(type: string, query: string): LookupEntry[];

declare function commitTurn(input: TurnCommitInput): TurnCommitResult;
declare function startSceneBeat(input: StartSceneBeatInput): SceneBeatResult;
declare function finishCurrentBeat(input: FinishCurrentBeatInput): SceneBeatResult;
declare function completeObjective(summaryOrId: string): ObjectiveResult;
declare function adjustMoney(input: { ownerActorId: string; amount: number; reason?: string }): Change<number>;

/** debug-only；protected paths 会拒绝非法写入 */
declare function patch(ops: PatchOp[], reason: string): void;
```

实际签名按卡片生成，不抄示例字段。

### 与底层 state 的关系

CodeAct 不自建存档系统。沙箱函数最终调用同一套 state 基建：

```txt
sandbox write → engine/domain functions → in-memory store → session custom entry → debug export
```

subagent 不拿 `code_act`。子代理只给文本/结构化建议；状态写入仍由 GM 走主 engine。

### CodeAct 校验

- [ ] `code_act` description 嵌入 `.d.ts`。
- [ ] 沙箱有超时和 host 出口限制。
- [ ] status 返回 clone。
- [ ] lookup 失败 throw。
- [ ] 写函数返回结构化结果并自动 log。
- [ ] 状态写入走 session-backed state。
- [ ] 下场测试中至少一次真实调用 `code_act`，且脚本使用 scene/组合 API，不只裸 patch。

## 总校验

- [ ] primitive/debug 层 + domain composition 层存在。
- [ ] 有活动单元时 scene/action macro 层存在，覆盖高频进入/收口动作。
- [ ] macro 覆盖半底层入口后，半底层工具不再暴露给 GM。
- [ ] 多状态变化有 turn commit / transaction。
- [ ] 组合工具子事件接受原工具的 flat payload，或至少兼容 flat payload。
- [ ] 事务 summary 能为子事件 reason 提供默认值。
- [ ] API 接受 natural handles，或错误能列出候选。
- [ ] 当前上下文操作存在，例如 current beat / finishCurrentBeat / ownerActorId 自动账户选择。
- [ ] protected paths 覆盖关键字段。
- [ ] patch 不碰受保护路径；最好 debug-only。
- [ ] GM 规则写清四层优先级和禁区。
- [ ] 状态写入走 session-backed state。
- [ ] 根据下场误用至少检查一次是否需要加深 API。
