# 设计原则

## 1. TS 跑时，Python 探索

```txt
engine/*.ts  → pi extension 直接 import
scripts/*.py → 解包、审计、一次性 CLI
```

不要用 Python 做运行时 engine；子进程/IPC 太重。

## 2. Agent 是程序

不要把「检查变量」「输出更新指令」写进 prompt。给工具，让 agent 自己 loop：查状态 → 判断 → 掷骰/计算 → 写状态 → 叙事。

LLM 负责表达；代码负责规则。

## 3. 计算进 engine

骰子、伤害、价格、好感阈值、轮次计数、定时触发都进 engine。LLM 是叙事者，不是会计。

标准方案优先 CodeAct；轻量方案才用多个专用工具。

## 4. 状态可追溯

LLM 不直接 mutate state。所有写入走工具/engine，保留 patch 或结构化结果。

状态真相源是 pi session custom entry。`state/` 只做 debug export / legacy fallback，不发布。读档靠 session tree/fork 分支恢复。

## 5. Prompt 极简

GM prompt 只放：

```md
# 世界名

你是此世界的 GM。

规则：
- 视角/文风 2-3 条
- 硬规则 ≤5 条
- 工具调用纪律
```

不要把世界书、公式、COT、JSON Patch 指令塞进去。

## 6. 删 ST 补丁

默认剥离：强化思考链、MVU 输出格式、JSON Patch 文本、`__结束__`、角色强制格式、HTML 状态栏、前端模板。

这些是 ST 运行时补丁，不是 agent 需求。

## 7. Data 按需查

- 世界/规则：`data/world.json`
- 角色：`data/characters.json` + lookup
- 章节：`data/chapters.json` + lookup
- 开场：`skills/start-game/SKILL.md`

大数据不进 prompt。地点 ≥20、NPC ≥5、DLC/物价表存在时，必须配查询工具。

## 8. 工具 description 是决策入口

模型是否调工具，主要看工具 description。读取类工具要写：

- 必须调用场景
- 严禁凭记忆编造
- 战斗/检定类的职责边界

## 9. 工具粒度按玩家动作

| 玩家动作 | 工具 |
|---|---|
| 到新地点 | `lookup_location` |
| 见 NPC | `lookup_npc` |
| 找任务 | `generate_quest` |
| 社交结束 | `update_affection` |
| 战斗结算 | `calculate_xp` / `try_level_up` |

过粗会参数乱猜，过细会工具爆炸。若总要记调用顺序，合并工具或改成 CodeAct 组合 API。
