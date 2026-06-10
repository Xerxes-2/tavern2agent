# Event packs

Event pack 是 tavern2agent v2 的扩展单位。它把一个可变领域从「prompt 规则」提升为可执行 runtime seam。

## Pack 契约

每个 pack 必须定义：

```txt
- domain language：这个领域的名词和不变量
- state roots：canonical state 中的落点
- events：GM 可提交的领域事件
- reducers：事件如何改变 state
- tool surface：typed pi tools 或 CodeAct API
- prompt fragments：tool-policy / render / output contract 片段
- tests：schema、reducer、tool normalizer、关键拒绝路径
```

pack 之间通过事件和 reducer 组合，不通过互相裸改 state。

## 基础 pack 序列

### scene-turn

职责：时间、地点、场景 beat、turn envelope。

典型事件：

```txt
commit_turn
start_scene_beat
finish_current_beat
move_location
advance_time
```

规则：连续叙事必须推进 clock；移动用 travel，非移动用 elapsed。scene event 不替代 time envelope。

### memory

职责：公开记忆、主角记忆、私有 GM 备注的分层。

典型事件：

```txt
record_public_memory
record_protagonist_memory
record_private_note
```

规则：hidden-canonical 不得写入 public memory。

### relationship

职责：好感、信任、立场、承诺、边界。

典型事件：

```txt
record_relationship_shift
record_promise
mark_boundary_crossed
```

规则：关系变化必须有 actor、target、reason、可见后果。不要让模型直接 `affection += 5`。

### condition

职责：伤势、疾病、诅咒、状态异常、外观/装备造成的可见条件。

典型事件：

```txt
apply_condition
worsen_condition
relieve_condition
remove_condition
```

规则：伤害数字可存在，但叙事层应渲染成身体后果和行动限制。

### inventory

职责：物品、装备、消耗品、可追踪道具。

典型事件：

```txt
acquire_item
consume_item
equip_item
transfer_item
```

规则：有来源、有持有者、有 reason；关键道具不能凭空出现。

### economy

职责：货币、账户、收入、支出、价格、债务。

典型事件：

```txt
earn_money
spend_money
transfer_money
rename_purse
```

规则：资金变化必须有 account、source/recipient、reason。修账户名用 rename，不伪造 gain/spend。

### secret

职责：隐藏身份、真名、凶手、动机、未揭示事实。

典型事件：

```txt
configure_secret
reveal_secret
mark_suspicion
```

规则：reveal 是 hidden → public/protagonist-known 的唯一通道。玩家知道不等于角色知道。

### quest

职责：目标、任务、章节、路线分支、完成条件。

典型事件：

```txt
open_quest
advance_quest
complete_objective
fail_objective
```

规则：任务推进是事件结果，不是 narrator 总结。

### faction/offscreen

职责：NPC 自治、阵营后台行动、玩家视野外真实事件。

典型事件：

```txt
record_offscreen_event
advance_faction_plan
surface_trace
```

规则：后台事件必须有 actor/faction、location、consequence、frontstage trace。新闻/门响/传闻不能替代事件本体。

### combat

职责：战斗交换、掷骰、伤害、战术状态、战利品。

典型事件：

```txt
start_combat
resolve_combat_exchange
apply_damage
end_combat
```

规则：战斗叙事不能跳过机械结算；结算结果再渲染成叙事。

## Tool surface 选择

pack 可以用 typed tools，也可以进入 CodeAct API：

```txt
typed tools：规则稳定、动作少、hidden/public 边界强。
CodeAct API：公式多、循环多、批量结算多、时间压缩多。
```

无论载体如何，pack 的领域事件和 reducer 不变。CodeAct 只承载 command layer，LLM 仍无权自由 patch state。

## Prompt fragment

每个 pack 只能注入三类 prompt：

1. 工具何时必须调用。
2. 禁止绕过的叙事行为。
3. 如何把工具结果渲染成玩家可感知后果。

pack prompt 不得成为领域正确性的唯一防线。

## 组合规则

- 一轮多个 pack 的事件用 `commit_turn` 或等价 transaction 收口。
- 事务 summary 可向子事件 reason 继承同语义默认值。
- 子事件 payload 尽量像原工具调用，不发明额外 DSL。
- macro tool 覆盖后隐藏半底层可见入口。

## Pack 选择清单

从 IR 逐项选择：

| IR 信号 | pack |
|---|---|
| 时间、地点、章节推进 | scene-turn |
| 记忆、长期事实 | memory |
| 好感、信任、恋爱、承诺 | relationship |
| HP、伤势、异常、服装状态 | condition |
| 背包、装备、关键道具 | inventory |
| 钱、价格、债务、经营 | economy |
| 秘密身份、真名、凶手、未揭示真相 | secret |
| 任务、路线、目标、结局 | quest |
| 多 NPC 自治、阵营计划、后台线 | faction/offscreen |
| 骰子、攻击、防御、伤害、战利品 | combat |

没有对应 pack 的 mutable concept 不允许留给 prompt 自行维护；要新增 pack、改为 immutable data，或明确丢弃。
