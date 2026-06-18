# 工具抽象设计

RP 工具让 GM 以自然叙事决策单位安全提交领域事件。不要按数据库字段切工具，也不要把复杂工作流写进 prompt 让模型背；把工作流做成可执行的高层 API。

v2 中，工具/CodeAct API 的权威输出是 domain event，state 是 reducer 结果。工具名和参数应表达世界里发生了什么：关系转变、资金流动、伤势施加、秘密揭示、后台行动、turn 提交，而非「把某字段改成某值」。

核心原则：**入口宽，核心严**。

- 入口宽：接受模型自然表达，例如 flat payload、自然语言 handle、`current` / `all` 上下文引用、事务摘要默认 reason。
- 核心严：engine 仍严格维护 canonical state、protected paths、hidden/public 边界和领域不变量。

CodeAct 是实现这套抽象的一种载体，不是唯一答案。稳定、可枚举的场景动作可以做成 typed pi tools；计算、循环、批量结算和时间压缩更适合 CodeAct 沙箱。无论载体如何，最终都应进入同一套 event catalog、reducer 和 protected path 规则。

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

人类写代码时有类型提示、字段补全、必填红线、hover 文档和编译器定位；模型调用工具时往往是在盲写 JSON。复杂 nested payload 会逼模型手写无 LSP 的 transaction AST，因此「低级错误」通常是 interface 错，不是 prompt 不够严。

把工具做成命令面板，别做成函数签名大全：

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
- 不做运行时 toolset 切换。工具清单是 prompt cache 前缀的一部分，动态增删工具每次都作废缓存；可见性在注册期决定，条件限制写进 description 和工具错误。

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

### LLM-facing schema 不等于 serde

不要把 pi tool schema / JSON Schema 当成 Rust `serde`。模型调用工具时没有 LSP、补全和编译器定位；复杂 `Type.Union([Type.Literal(...)])`、多分支 object union、深层 enum 很容易在 pi validation 层展开成一串 `must be equal to constant` / `must match anyOf`，这类错误对模型不可恢复。

推荐边界：

```txt
LLM-facing tool schema  只挡基本形状：object / string / number / array，description 写允许值
tool normalizer/assert  unknown → typed domain input，抛一个中文领域错误
engine/state schema     继续严格验证 canonical state 和领域不变量
```

也就是在 TypeScript 里显式做一层 serde boundary：

```ts
function tool(params: unknown) {
  const input = assertDomainInput(params); // unknown → typed input
  return engine(input);                    // core remains strict
}

function assertContractStatus(value: unknown): ContractStatus {
  if (value === "stable" || value === "weak" || value === "cut" || value === "masterless") {
    return value;
  }
  throw new Error(`非法 contractStatus: ${String(value)}。允许值: stable, weak, cut, masterless。`);
}
```

高频 LLM 工具尤其不要在注册 schema 里暴露复杂 union：

```ts
// 好：schema 宽，description 给模型提示；工具入口负责窄化
parameters: Type.Object({
  kind: Type.String({ description: "允许: ensure-public-npc, upsert-public-npc, upsert-servant" }),
  npc: Type.Optional(Type.Object({
    actorId: Type.Optional(Type.String()),
    displayName: Type.String(),
    relationshipToProtagonist: Type.Optional(Type.Object({
      stance: Type.String({ description: "self / ally / friendly / neutral / wary / hostile / unknown" }),
      summary: Type.String(),
    })),
  })),
})

// 差：模型填错时爆出多条 constant/anyOf，无从恢复
parameters: Type.Object({
  kind: Type.Union([Type.Literal("ensure-public-npc"), Type.Literal("upsert-public-npc")]),
  npc: Type.Union([FullNpcSchema, SkeletonNpcSchema]),
})
```

仍然要保留严格性，但严格性放在工具 normalizer 和 engine：

- 归一化用共享 schema 模块：内部 TypeBox tagged-union + 统一 parse 入口，错误翻译成领域语言。单个 enum 才值得手写 assert；手写 assert 会繁殖成几十个克隆（fsn 迁移时删了 70+）。
- 每个 union object 由 `kind` 或当前工具语义选择一个 parser，不让 LLM-facing JSON Schema 同时尝试所有分支。
- 必填业务字段在 parser 报「缺少 npc.actorId」，不要让 validator 报多个分支缺字段。
- parser 返回 typed input；不要让 `any` 扩散进 engine。
- 为常见错误写工具层测试，断言错误消息，而不只断言 throw。

低频 debug 工具、非 LLM 内部 schema、state schema 可以继续精确 union；问题只在 LLM-facing 参数面。

## 四层 API

```txt
scene/action 层        GM 的叙事动作：进入场景、完成 beat、战斗交换、休息、购物、调查
turn commit 层         一轮内多个状态变化的事务收口：按顺序提交、验证、返回 warnings
domain composition 层  常用领域联动：交易、推进时间、结算任务、转移物品、记录后果
primitive/debug 层     status、lookup、log、assert、受保护低层事件；patch 只 debug/迁移兜底
```

规则：

- GM 优先用最高层；覆盖不到再降层。
- 有「持续活动 + 结算 + 事件」就建 scene/action 层。
- 一轮内多个状态变化要有 turn commit / transaction。
- `patch` 只能 debug 或一次性迁移兜底，不能绕过有规则的组合函数；常规玩法不暴露万能 `update_state`。

### Scene / Action

scene 层的划分单位是 GM 的一次叙事承诺，与题材分类无关。API 名称尽量贴近玩家行动句子：

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

受保护字段清单与 patch 例外条件见 `references/evented-runtime.md` 的 Patch 纪律。工具层的落点：`patch` 命中受保护路径时 throw，错误信息提示正确事件/函数（见下文错误设计）。

## 错误设计

错误信息是给模型恢复用的 prompt。不要只说 failed；要返回下一次调用所需参数。

union/多分支校验错误要折叠噪声：TypeBox/JSON Schema 对 `anyOf`/`oneOf` 会同一 path 吐三行（`分支1 类型不符`、`分支2 缺字段`、`必须匹配其中一种`），对模型不可恢复。把同一 instancePath 的相邻分支错误吐成一行：具体分支形状 + 从源值（RFC 6901 JSON Pointer）读出的实际 JSON 类型。根治仍是 schema 不对 LLM 面暴露复杂 union（见 「LLM-facing schema 不等于 serde」）。

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

工具 description 是紧凑的使用边界，不是操作手册。忌「【必须调用的场景】/【严禁的行为】」式长清单——那种清单是 reasoning-bait，诱导模型动手前逐条复述整套规约，拖慢非 GPT 模型（详见 `engineering-discipline.md` Prompt/工具体量纪律）。收成四件事，每件一行：

1. 一行用途。
2. 使用边界 bullet（何时用 / 该用哪个替代）。
3. 严禁 bullet（只列真会误用的，不穷举）；四层优先级 scene/action > turn commit / transaction > domain composition > primitive/debug 一行带过。
4. 若是 CodeAct，嵌入 `.d.ts`。

## 交互测试驱动加深

下场测试要观察模型实际怎么误用 API；只确认工具被调用不够。

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

## CodeAct

CodeAct 载体的适用点、沙箱契约、`.d.ts` 权威和实现校验见 `references/codeact.md`。typed tools 与 CodeAct 的取舍见上文「选择取舍」。

## 总校验

本清单是工具设计阶段闸门；完工闸门见 `references/validation.md`。

- [ ] primitive/debug 层 + domain composition 层存在。
- [ ] 有活动单元时 scene/action macro 层存在，覆盖高频进入/收口动作。
- [ ] macro 覆盖半底层入口后，半底层工具不再暴露给 GM。
- [ ] 多状态变化有 turn commit / transaction。
- [ ] 组合工具子事件接受原工具的 flat payload，或至少兼容 flat payload。
- [ ] 事务 summary 能为子事件 reason 提供默认值。
- [ ] API 接受 natural handles，或错误能列出候选。
- [ ] 当前上下文操作存在，例如 current beat / finishCurrentBeat / ownerActorId 自动账户选择。
- [ ] Patch 纪律落实（清单与例外见 `references/evented-runtime.md`）。
- [ ] GM 规则写清四层优先级和禁区。
- [ ] 状态写入走 session-backed state。
- [ ] 工具契约与实现同文件；registry 只是清单，并有 loose-schema 守卫测试。
- [ ] 归一化走共享 schema 模块，无手写 assert 克隆。
- [ ] 工具清单整局稳定，无运行时 toolset 切换。
- [ ] 根据下场误用至少检查一次是否需要加深 API。
