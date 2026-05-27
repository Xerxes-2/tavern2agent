# 工具集

主要给轻量方案用。标准 CodeAct 常驻通常只有 `code_act`、`get_status`、`lookup`、`switch_toolset`；多步操作在沙箱里组合。

subagent 也适用：子代理不拿 `code_act`，只拿只读/轻量工具。

## 目标

- 常驻工具少。
- debug/setup/migration 不进普通叙事轮。
- 场景工具只在对应场景出现。
- 保留 `debug/full` 给开发者排查。

## 分组

| toolset | 工具 | 场景 |
|---|---|---|
| `always` | `get_status`、`lookup`、`switch_toolset` | 默认 |
| `setup` | 初始化、角色配置、DLC 开关 | 开局/重开 |
| `combat` | 攻击、防御、伤害、掉落 | 战斗/追逐 |
| `craft`/`economy` | 制作、买卖、休息 | 商店/工坊 |
| `social` | 好感、任务、关系 | NPC 社交 |
| `world` | 地点、传闻、旅行 | 探索 |
| `debug` | schema、migration、审计 | 修档/开发 |
| `full` | 全部 | 人工排查 |

用 `toolset`，不用 `context`。

## switch_toolset

```ts
const TOOLSETS = {
  always: ["get_status", "lookup", "switch_toolset"],
  setup: ["get_status", "lookup", "switch_toolset", "setup_game"],
  combat: ["get_status", "lookup", "switch_toolset", "resolve_combat_round"],
  social: ["get_status", "lookup", "switch_toolset", "manage_quest", "update_relation"],
  debug: ["get_status", "lookup", "switch_toolset", "get_state_schema", "migrate_state"],
} as const;
```

description 写：何时切入、何时切回、`debug` 仅修档/迁移。

## API 兼容

不长期保留旧工具名/旧参数。

- 改名后同步 prompt、skill、description、测试。
- 旧 state 只在 migration 里读。
- 输入归一化可以保留；旧运行时兼容不要保留。

## 专用工具优先

有规则的变化不要裸 patch：

| 状态变化 | 工具 |
|---|---|
| 金钱 | `earn_money` / `spend_money` |
| 物品 | `manage_item` |
| 装备 | `manage_equipment` |
| 技能 | `commit_skill` |
| 任务 | `manage_quest` |
| 场景/时间 | `change_scene` |
| 升级 | `try_level_up` / `allocate_attribute_points` |

`patch_state` 保留，但 protected paths 禁止绕过专用工具。

## 子代理

子代理默认只读：lookup + 动态状态注入。需要状态时写 `extensions/subagents/<name>.ts` 注入，不让 GM 每次塞完整上下文。

## 防腐

- 常驻少。
- 维护工具进 `debug/full`。
- 有规则就写专用工具。
- description 写触发条件和禁令。
- 反复误用时改工具集/schema/测试，不堆 prompt。
