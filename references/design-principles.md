# 设计原则

## 1. 卡片先变成 IR，再变成 runtime

不要直接从 ST 原文拼 prompt 或生成工具。迁移链路是：

```txt
card → Card Semantic IR → Runtime Plan → generated pi project
```

IR 保留作者意图：人物、世界、可变概念、机制、可见性、开局和风格。ST 宏、HTML、COT、JSON Patch 文本只是旧运行时补丁，提取语义后丢弃。

## 2. Prompt 描述世界，领域事件改变世界

不要把「检查变量」「输出更新指令」「好感变化」「扣钱」「受伤」「泄密」写进 prompt 让模型自觉遵守。给领域事件和 reducer：

```txt
record_relationship_shift
spend_money
apply_condition
reveal_secret
commit_turn
```

状态字段由 reducer 产出，模型无权直接编辑。凡有规则的可变概念，都必须走 event pack、组合 API 或 CodeAct domain API。

## 3. TS 跑时，Python 探索

```txt
engine/*.ts  → pi extension 直接 import
scripts/*.py → 解包、审计、一次性 CLI
```

不要用 Python 做运行时 engine；子进程/IPC 太重。

## 4. Agent 是程序

LLM 负责表达；代码负责规则。

agent 的 loop 应该是：查状态 / lookup → 判断 → 调领域事件或 CodeAct API → 读取结构化结果 → 叙事渲染。

不调用工具或 CodeAct，就不能声称机械层事实已经改变。

## 5. 计算进 engine

骰子、伤害、价格、好感阈值、轮次计数、定时触发都进 engine。LLM 只管叙事，账目归 engine。

CodeAct 只是承载领域 API 的一种执行载体，禁止当自由脚本入口。稳定、可枚举的场景动作优先做 typed deep tools；计算、循环、批量结算和时间压缩更适合 CodeAct。

## 6. 状态可追溯

所有写入走工具 / CodeAct API / engine，保留结构化 domain event 和 turn log。

状态真相源是 pi session custom entry。`state/` 只做 debug export，不发布。读档靠 session tree/fork 分支恢复。

## 7. Public / hidden / player knowledge 分层

必须区分：

| 层级 | 含义 | 落点 |
|---|---|---|
| player-only | 现实玩家知道，角色未必知道 | 不写 public state；最多用于 GM guard |
| protagonist-known | 玩家角色知道 | protagonist memory / actor public facts |
| scene-public | 场景中他人也知道 | public state / public memory |
| hidden-canonical | 真实存在但未公开 | secrets / hidden state / subagent context |

不要因为 ST 卡把秘密写在 prompt 里，就把它迁移到 public memory。

## 8. Prompt 按职责拆分，由编排器渲染

Prompt orchestrator 是 Runtime Plan 的 view/compiler backend；领域规则不归它管。复杂 RP 项目使用 `agents/preset.json` 管理模块开关、slot 和 priority；具体文本拆到 `agents/gm-*.md`。

推荐职责：

```txt
pre-history：创作宪法、世界索引、输入协议、社交/文风/渲染滤镜
pre-response：状态简报、工具策略、硬规则、本轮 driver
final-contract：短输出闸门
```

不要把世界书、公式、COT、JSON Patch 指令塞进去。大数据进 data + lookup；状态进 engine；prompt 只做阅读滤镜、工具纪律、叙事渲染和输出合同。

## 9. 不加戏

不要加原作者没写的游戏机制。没有上限就不要加防囤积；没有耐久就不要加装备损耗；没有疲劳就不要加精力条；没有通货膨胀就不要加动态物价。

世界书、MVU、TH scripts、regex scripts 和开场是机制来源；不从中推导出来的规则不存在。

## 10. 删 ST 补丁

默认剥离：强化思考链、MVU 输出格式、JSON Patch 文本、`__结束__`、角色强制格式、HTML 状态栏、前端模板。

这些都是 ST 运行时补丁。字段、公式、触发条件可以进入 IR；补丁语法不进入 runtime。

## 11. Data 按需查

- 世界/规则：`data/world.json`
- 角色：`data/characters.json` + lookup
- 地点：`data/locations.json` + lookup
- 章节：`data/chapters.json` + lookup
- 开场：`skills/start-game/SKILL.md`

大数据不进 prompt。地点 ≥20、NPC ≥5、DLC/物价表存在时，必须配查询工具。

## 12. 工具 description 是决策入口

模型是否调工具，主要看工具 description。关键工具要写：

- 必须调用场景
- 严禁凭记忆编造或叙事绕过
- 工具职责边界
- 常见错误后的正确下一步

## 13. 工具粒度按领域事件

工具对应 GM 的叙事动作，而不是 state 字段：进入调查、完成撤退、休息一晚、采购整备、战斗交换、记录长期后果。

| 可变概念 | 事件 / 工具 |
|---|---|
| 时间/地点 | `commit_turn` / `move_location` |
| 好感/信任 | `record_relationship_shift` |
| 金钱 | `earn_money` / `spend_money` / `transfer_money` |
| 伤势/异常 | `apply_condition` / `relieve_condition` |
| 秘密 | `configure_secret` / `reveal_secret` |
| 后台行动 | `record_offscreen_event` |

过粗会参数乱猜，过细会工具爆炸。若总要记调用顺序，合并成更深的 scene/action API 或 turn commit API。
