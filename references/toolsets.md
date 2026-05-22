# 工具集设计：少即是多，按场景切换

复杂互动卡的工具数量很快会膨胀：状态、战斗、经济、制作、社交、世界查询、setup、debug、迁移……如果全部常驻，模型会把注意力浪费在无关工具签名上，也更容易误调用低频维护工具。

经验结论：**工具不是越多越好；同一轮只暴露当前场景需要的最小集合。**

## 设计目标

1. **降低 token 与选择成本**：模型每轮都能看到工具签名；常驻工具越多，越容易漏掉真正该用的工具。
2. **减少误操作面**：`migrate_state`、`get_state_schema`、debug/维护工具不该出现在普通叙事轮。
3. **强化场景纪律**：战斗轮看到战斗工具，制作轮看到制作工具，setup 轮看到 setup 工具。
4. **保留人工调试能力**：开发者仍能切到 `debug`/`full` 做维护。

## 推荐分组

| toolset | 常见工具 | 何时使用 |
|---|---|---|
| `always` | `get_status`、`lookup`、`switch_toolset`、少量核心状态工具 | 默认常驻，必须极少 |
| `setup` | `setup_game`、角色/世界/DLC 初始化工具 | 开局配置、重开、迁移后初始化 |
| `combat` | 攻击、防御、伤害、NPC 入场/离场、战利品 | 进入战斗/追逐/清剿场景 |
| `craft` / `economy` | 制作、购买、卖出、休息、物价 | 商店、工坊、长时间制作、补给 |
| `social` | 好感、任务、命名、关系更新 | NPC 社交、任务接取/结算 |
| `world` | 场景切换、地点查询、新闻/传闻 | 旅行、换房间/街区/城市、公告板 |
| `debug` | `get_state_schema`、`migrate_state`、宽松 patch、审计工具 | 仅开发/修档/迁移 |
| `full` | 所有工具 | 仅人工排查，不作为正常游戏模式 |

命名建议用 `toolset`，不要用 `context`。`context` 容易和叙事上下文、模型 context、世界状态混淆。

## `switch_toolset` 模式

注册一个常驻切换工具：

```typescript
const TOOLSETS = {
  always: ["get_status", "lookup", "switch_toolset"],
  setup: ["get_status", "lookup", "switch_toolset", "setup_game"],
  combat: ["get_status", "lookup", "switch_toolset", "resolve_combat_round", "generate_loot"],
  social: ["get_status", "lookup", "switch_toolset", "manage_quest", "update_relation"],
  debug: ["get_status", "lookup", "switch_toolset", "get_state_schema", "migrate_state"],
  full: [/* 所有工具 */],
} as const;
```

`switch_toolset` 的 description 要写清：

- 进入战斗前切 `combat`
- 开局配置切 `setup`
- 修档/迁移才切 `debug`
- 普通叙事结束后可切回 `always` 或对应常用场景

不要把 `debug`、`setup`、`migrate_state` 这类低频维护工具放进 `always`。

## 工具 API 兼容性取舍

pi 会把当前可见工具签名注入给模型，模型按**当前签名**调用即可。因此迁移产物内部不需要长期保留旧工具名/旧参数兼容层。

推荐策略：

- 改名后直接更新 prompt、skill、工具描述和测试；不要长期双轨。
- 旧 state 结构只在 migration 里读；运行时只支持当前 schema。
- 输入归一化可以保留（例如「饰品」映射到 `饰品1/2/3`），但不要把它写成旧运行时兼容。

## 专用工具优先于裸 patch

如果某类状态变化有规则，就写专用工具，不要让 GM 直接 patch：

| 状态变化 | 推荐工具 |
|---|---|
| 金钱收入/支出 | `earn_money` / `spend_money` 或统一经济工具 |
| 物品获取/购买/卖出/丢弃 | `manage_item` |
| 装备穿脱 | `manage_equipment` |
| 技能生成/入栏 | `commit_skill` |
| 任务接取/推进/结算 | `manage_quest` |
| 场景/时间/地点变化 | `change_scene` |
| 升级/属性点 | `try_level_up` / `allocate_attribute_points` |

`patch_state` 仍然保留，但应增加 strict path 保护：凡已有专用工具负责的字段，禁止裸 patch 绕过。

## 子代理工具集

子代理默认应拿**轻量工具集**，甚至只读工具：

- companion/队友心声：通常只需查询工具；当前人格和状态由子代理 extension 注入。
- news-writer/传闻作者：只需查询工具；世界状态由 extension 注入，返回文本给 GM，写 state 仍由 GM 负责。

每个子代理若需要动态状态，优先为它写 `extensions/subagents/<name>.ts`，而不是要求 GM 每次把完整状态塞进 task。

## 防腐原则

- 常驻工具越少越好。
- 维护工具只在 `debug`/`full`。
- 有规则的状态变化进专用工具。
- 工具 description 写触发条件和禁令。
- 发现模型反复误用，不要只堆 prompt：改工具集、改 schema、加 strict path、加测试。
