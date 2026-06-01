# 工具抽象与 CodeAct 取舍

RP 项目的工具设计目标不是「让模型能改 state」，而是让 GM 以自然叙事决策单位安全提交世界变化。不要按数据库字段切工具，也不要把复杂工作流写进 prompt 让模型背；把工作流做成可执行的高层 API。

CodeAct 是实现这种工具抽象的一种载体，不是唯一答案。稳定、可枚举的场景动作可以做成 typed pi tools；计算、循环、批量结算和时间压缩更适合 CodeAct 沙箱。

## CodeAct 定义

标准 CodeAct 方案使用单个 `code_act` 工具 + 沙箱。GM 写一小段 JS，沙箱执行计算、随机、状态写入、查询，再把结构化结果交给 GM 叙事。

纯 prompt / light 不要套 CodeAct。CodeAct 不是让 LLM 在沙箱里写小说，也不是自由脚本入口；它是受限的 typed command layer。沙箱只产机械结果、结算摘要和叙事钩子。

## 目的

CodeAct 解决多工具形态的三个问题：

- 多步结算要跨很多 tool call。
- LLM 容易忘顺序或心算错误。
- 状态扫描、条件分支、批量结算和时间压缩很难一轮完成。

看到 prompt 里出现「先 A，再 B，再 C，最后 D」时，优先考虑把这个工作流做成 CodeAct API，而不是继续加自然语言纪律。

## 选择取舍

CodeAct 和一组 typed pi tools 都可以承载三层架构。区别是执行载体：

```txt
CodeAct       GM 写受限 JS，调用沙箱 API 完成一段状态命令
Typed tools   GM 调 pi tools；工作流由每个工具 interface 固化
```

### 优先用 CodeAct

满足任一强信号时倾向 CodeAct：

- 战斗、经济、任务、日程、经营、好感、伤害等规则需要多字段联动。
- 一轮经常要计算、循环、筛选、批量处理 NPC / 物品 / 日程。
- 时间压缩需要连续推进多个时段，并在中途触发事件。
- 公式、随机、条件分支比「调用几个固定工具」更自然。
- 如果生成一堆 `dice/combat/economy/task` 独立工具，工具面会爆炸。
- playtest 中模型反复需要连续调用 3 个以上状态工具完成同一种动作。

### 优先用 typed deep tools

满足这些信号时，不要为了标准方案机械上 CodeAct，可以用深 typed tools：

- 项目规则稳定，核心动作能枚举成少数深 interface。
- hidden/public、权限、锁定事实、审计边界很强，不希望 GM 写临时脚本靠近 raw state。
- 需要 TypeScript 编译期约束、细粒度单元测试和明确工具审计。
- 场景动作比公式计算更重要，例如 `scene_beat`、`commit_turn`、`set_scene_presence`。
- 高层 typed tools 已经覆盖模型的自然决策单位。

### 混合方案

可以混合：typed tools 管核心 state seam，CodeAct 只管局部高复杂结算。

例：

```txt
主状态写入：scene_beat / commit_turn / record_memory / reveal_secret
局部 CodeAct：combat_exchange / rest_period / investigation_pass / downtime_sim
```

无论选哪种，原则相同：不要让模型背工作流；把工作流变成可执行的高层 API。

## 三层 API

```txt
scene/action 层   GM 的叙事动作：进入场景、完成 beat、战斗交换、休息、购物、调查
turn commit 层    一轮内多个状态变化的事务收口：按顺序提交、验证、返回 warnings
组合函数层       常用多字段联动：交易、推进时间、结算任务、转移物品、记录后果
原语/debug 层     status、lookup、log、assert、受保护低层事件；patch 只 debug/兜底
```

规则：

- GM 优先用最高层；覆盖不到再降层。
- 原语层 + 组合层必须有。
- 有「持续活动 + 结算 + 事件」就建 scene/action 层。
- 一轮内多个状态变化要有 turn commit / transaction 概念。
- `patch` 只能 debug 或兜底，不能绕过有规则的组合函数；有 protected path 时必须 throw。

### scene/action 层

scene 层不是题材分类，而是 GM 的一次叙事承诺。API 名称尽量贴近玩家行动句子：

```ts
declare function moveToBeat(input: MoveToBeatInput): SceneBeatResult;
declare function completeBeat(input: CompleteBeatInput): SceneBeatTransitionResult;
declare function combatExchange(input: CombatExchangeInput): CombatResult;
declare function restPeriod(input: RestInput): RestResult;
declare function shoppingTrip(input: ShoppingInput): ShoppingResult;
declare function investigationPass(input: InvestigationInput): InvestigationResult;
```

好 API：

```ts
moveToBeat({
  location: "柳洞寺外围",
  elapsedMinutes: 35,
  beat: "柳洞寺外围侦察",
  objectives: ["确认结界", "安全撤回"],
});
```

差 API：

```ts
patch([{ path: "/scene/location", value: "柳洞寺" }]);
patch([{ path: "/scene/objectives/0", value: "确认结界" }]);
```

### turn commit 层

RP agent 最容易漏的是「收口」：撤退、推进时间、完成目标、记录长期后果、扣资源可能发生在同一回复。要提供事务式 API：

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

脚本例：

```ts
commitTurn({
  summary: "撤回卫宫宅并记录柳洞寺侦察发现",
  events: [
    scene.moveLocation({ location: "卫宫宅", elapsedMinutes: 35, reason: "安全撤回" }),
    scene.completeBeat({ resolvedObjectiveSummaries: ["确认结界", "安全撤回"] }),
    memory.recordMajorEvent({ title: "柳洞寺外围侦察", summary: "山门是唯一入口" }),
  ],
});
```

## Natural handles

RP 模型更容易记玩家可见文本，不容易记内部 id。沙箱 API 应尽量接受 natural handles，并在内部匹配。

优先支持：

- objective summary
- actor display name / alias
- item label
- location label
- claim + evidence
- memory title

例：

```ts
completeObjective("安全撤回不触发戒备");
transferItem({ item: "宝石项链", to: "士郎" });
revealSecret({ actor: "Assassin", claim: "佐佐木小次郎", evidence });
```

内部 id 可以返回，但不要成为继续工作流的唯一入口。多重匹配时 throw ambiguity error，并列出候选；未命中时 throw，并提示可用 handles。

## 沙箱契约

沙箱用 `node:vm`（`vm.createContext` + `vm.Script.runInContext`），不是 `child_process`、`eval` 或 Docker。

- 写函数返回结构化结果，如 `{ before, after }`、`{ settlement, events, hooks }`。
- 写函数自动 log 人类可读摘要。
- 查询未命中 throw，供脚本 try/catch。
- `status()` 返回 clone，不给 state 引用。
- 禁止 fs/process/require/import 等 host 出口。
- 设置超时，防死循环。
- 执行后 dirty state 走 session-backed state 链路。
- 脚本中只做机械层；不要生成小说正文。

## `.d.ts` 是 API 权威

为沙箱暴露函数写 `engine/codeact-sandbox.d.ts`。它同时服务：

- GM 每轮看到的函数签名。
- 沙箱实现的类型检查。
- 工具 description 的权威 API 段。

不要用长自然语言逐个解释函数。类型签名 + 少量 JSDoc 足够。

示意：

```ts
declare function status(): Readonly<WorldState>;
declare function log(message: string): void;
declare function lookup(type: string, query: string): LookupEntry[];

declare function commitTurn(input: TurnCommitInput): TurnCommitResult;
declare function moveToBeat(input: MoveToBeatInput): SceneBeatResult;
declare function completeObjective(summaryOrId: string): ObjectiveResult;
declare function adjustMoney(delta: number, reason: string): Change<number>;

/** debug-only；protected paths 会拒绝非法写入 */
declare function patch(ops: PatchOp[], reason: string): void;
```

实际签名按卡片生成，不抄示例字段。

## protected paths

凡有规则的字段，禁止裸 `patch`：

- 金钱/资源
- 装备/背包
- 技能/属性点
- 任务/章节/Scene Objective
- 好感/关系
- 场景/时间
- hidden/public 可见性边界

这些必须走组合函数或 scene。`patch` 命中受保护路径时 throw，并提示正确函数。standard 方案中 `patch` 应逐步降级为 debug-only；若保留兜底，每次必须有 reason，且只能改无规则、无联动的 cosmetic 字段。

## 错误设计

错误信息是给模型恢复用的 prompt。不要只说 failed；要说明正确路径。

例：

```txt
unknown actor: caster。请先 materialize actor：upsert_actor / addActor。
unresolved beat: 仍有未解决目标 objective-2「安全撤回」。
ambiguous item label: 宝石。候选：宝石项链、红宝石吊坠。
protected path /economy/funds: 请使用 adjustMoney / purchase。
```

工具应主动拒绝常见错法：

- 漏 reason。
- 未解决 objective 就 transition。
- 写入不存在 actor。
- secret 写进 public memory。
- 用 patch 改受保护字段。
- 多状态收口却绕过 turn commit。

## Prompt 要点

写进 GM 规则：

- 状态变化、掷骰、时间推进、经济/战斗/任务结算必须用 `code_act`。
- 一轮多个状态变化必须用 `commitTurn` / transaction 收口。
- 时间跳跃用一段 scene/advance 序列，不拆成多轮。
- 脚本里只做机械层；叙事在工具返回后写。
- 不要 `log(scene(...))`；写函数会自动 log。
- 不调用 `code_act` 就不能声称状态已改变。

`code_act` description：

1. 必须调用场景。
2. 严禁行为。
3. 三层优先级：scene/action > turn commit / 组合 > 原语。
4. 嵌入 `.d.ts`。

## 与底层 state 的关系

CodeAct 不自建存档系统。沙箱函数最终调用同一套 state 基建：

```txt
sandbox write → engine/domain functions → in-memory store → session custom entry → debug export
```

subagent 不拿 `code_act`。子代理只给文本/结构化建议；状态写入仍由 GM 走主 engine。

## 交互测试驱动加深

下场测试不是只确认 `code_act` 被调用，而是观察模型实际怎么误用 API。

记录这些信号：

- 模型是否频繁降层。
- 是否漏 reason。
- 是否记不住内部 id。
- 是否把多个状态变化拆散。
- 是否先叙事后工具。
- 是否把 hidden truth 写进 public。
- 工具失败后是否能恢复。

如果同一种误用在 playtest 中重复出现：

1. 加深 scene/action API。
2. 增加 natural handle。
3. 加 validator / protected path。
4. 改错误信息提示正确路径。
5. 最后才改 prompt 文案。

不要用 prompt 长期弥补坏 interface。

## 校验

- [ ] 原语层 + 组合层存在。
- [ ] 有活动单元时 scene/action 层存在。
- [ ] 多状态变化有 turn commit / transaction。
- [ ] API 接受 natural handles，或错误能列出候选。
- [ ] 写函数返回结构化结果并自动 log。
- [ ] lookup 失败 throw。
- [ ] status 返回 clone。
- [ ] 沙箱有超时和 host 出口限制。
- [ ] protected paths 覆盖关键字段。
- [ ] patch 不碰受保护路径；最好 debug-only。
- [ ] description 嵌入 `.d.ts`。
- [ ] GM 规则写清三层优先级和禁区。
- [ ] 状态写入走 session-backed state。
- [ ] 下场测试中至少一次真实调用 `code_act`，且脚本使用 scene/组合 API，不只裸 patch。
- [ ] 根据下场误用至少检查一次是否需要加深 API。
