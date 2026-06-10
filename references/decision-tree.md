# 方案判定

本文是方案分档的唯一权威；其他文档只引用，不另立表。

## 主表

| 条件 | 方案 | 形态 |
|---|---|---|
| 纯设定，无可变世界、无秘密边界 | prompt-only | `agents/` + `data/` + start skill；v2 退化形态 |
| 少量可变概念，无复杂公式 | evented light | `engine/events.ts`、`engine/reducers.ts`、少数 typed domain tools |
| 骰子/战斗/经济/多字段联动/时间压缩/级联 | evented standard | event packs + reducer + typed tools / CodeAct API |
| 隐藏信息/秘密视角/多阵营 | pack 叠加 | secret / faction / offscreen + project subagent |
| 现实题材/开放资料/API 文档 | research 叠加 | web/fetch/code-search 只读事实源 + local canonical data |

临界场景按下文判定。

## 第一问：有没有 mutable concept？

没有可变世界、没有秘密边界、没有持续记忆要求：可以 prompt-only。

只要出现以下任一项，就进入 evented：

- 好感、信任、关系阶段、承诺。
- 金钱、物品、装备、任务、等级、伤势、HP/SAN。
- 时间、地点、章节、路线、场景 objective。
- 隐藏身份、凶手、秘密真相、玩家知道但角色未必知道的信息。
- NPC 后台行动、阵营计划、多视角。

状态键数量不是核心标准；**有没有领域不变量和可审计变化**才是标准。

## 第二问：typed tools 还是 CodeAct？

- 规则稳定、动作少、hidden/public 边界强：typed deep tools。
- 公式多、循环多、批量结算多、时间压缩多：CodeAct domain API。
- 两者可混用：核心 seam typed tools，局部复杂结算 CodeAct。

无论载体如何，最终都提交 domain event 并经 reducer。

## 信号

- 有 `[mvu_update]` / `[mvu_plot]` / Zod schema：至少 evented light。
- 有骰子、战斗、伤害公式、经济流通、多字段联动：evented standard。
- 状态键 ≤10 且只有简单加减：evented light，不是裸 patch。
- 只有 1-2 个偶发 roll：可 light；若 roll 改变状态，仍要事件。
- 卡反复强调「严格公式/禁止自由发挥」：偏 standard。
- 死亡回溯/读档/撤销：不升档；用 session tree/fork。
- 周目继承记忆：加 `meta/persistent.json` 或 permanent custom entry。
- 非 MVU 自定义变量：按语义映射到 mutable concept，不单开方案。

- 伤害公式 + 装备护甲 + 命中：standard，通常用 CodeAct。
- 稳定 RP 场景流程（进入 beat、完成 beat、撤退记录）：standard 可用少数深 typed tools，不必强上 CodeAct。
- 若 prompt 里出现「先 A，再 B，再 C」且 playtest 反复漏步骤：把工作流升成 scene/action API 或 turn commit，不要只加提示词。
- 模型需要循环/批量/条件计算：CodeAct 优先；模型只需要提交少数叙事动作：typed deep tools 优先。

## 样例

| 特征 | 档位 |
|---|---|
| 纯地理/势力/NPC，无变量、无秘密边界 | prompt-only |
| 只有开局选阵营/难度，之后不维护状态 | prompt-only + start skill |
| 30+ 键值状态，简单 ± | evented light，按领域 pack 分组 |
| 偶发 `{{roll:1d6}}` 占卜，不写状态 | prompt-only 或 light lookup |
| 偶发 roll 影响关系/资源 | evented light |
| 伤害公式 + 装备护甲 + 命中 | evented standard / combat pack |
| 秘密身份、凶手、真名 | secret pack，必要时 subagent 隔离 |
| 死亡循环只是叙事 | 按计算复杂度判 |
| 真回档到存档点 | 按计算复杂度判 + session-backed state |
| 周目保留记忆字段 | 上者 + persistent meta |
| 多结局章节读档 | session-backed state + quest pack |
