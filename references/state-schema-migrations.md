# State schema / migration

State schema 是宪法。运行时只支持当前结构；旧存档只能通过显式 migration 进入当前结构。

## 原则

- `INITIAL_STATE`、schema、工具、派生逻辑描述同一套结构。
- 运行时只读当前字段。
- 旧字段只出现在 migration。
- patch 拒绝未知顶层 root。
- 有专用工具/组合函数负责的字段，禁止裸 patch。
- 派生值不写 state。
- 状态排序只服务 diff/readability，不参与逻辑。

## Root 白名单

未知 root 直接拒绝。不要让模型创建：

```txt
/player
/user
/玩家
/角色
/旧同伴
```

动态内容放在已知 root 下：

```txt
/背包/<itemId>
/关系/<npcId>
/任务/<questId>
/战斗/NPC/<npcId>
```

## Protected paths

凡有规则的字段不允许裸 patch，例如：

- 金钱/资源
- 经验/等级/属性点
- 背包/装备/技能
- 任务/章节
- 地点/时间
- 好感/关系

light 方案用专用工具；standard 方案用 CodeAct 组合函数/scene。

## Schema version

state 里保留版本号。发现旧版本时，不要运行时猜字段；提示需要 migration。

```txt
StateMigrationRequired: v2 → v3
```

是否自动迁移由项目决定，但迁移本身必须确定、可测试、可审计。

## Migration 契约

每个 migration 应有：

```txt
from
to
description
migrate(raw) -> current state
```

要求：

- deterministic：同输入同输出。
- tested：fixture 输入输出固定。
- no LLM：迁移是代码，不是推理。
- cleans old fields：迁完旧字段消失。

`migrate_state` 放 `debug` 或 `setup` toolset，不进 `always`。可提供 dry-run diff。

## Runtime 禁区

不要这样：

```ts
state.核心系统 ?? state.旧同伴 ?? state.companion
```

应该在 migration 里一次性转成当前字段，runtime 只读：

```ts
state.核心系统
```

自然语言输入归一化可以保留，例如“饰品”映射到 `饰品1/2/3`；这不是旧 state 兼容。

## 测试

至少覆盖：

- `INITIAL_STATE` 符合 schema。
- 非法 root 被拒绝。
- protected path 被拒绝。
- 旧版本触发 migration required。
- migration 能把旧 fixture 升到当前 schema。
- 迁移后旧字段不存在。
- 派生值不落盘。

## 发版

breaking state 变化：

1. bump schema version。
2. 添加 migration。
3. 更新 changelog/玩家说明。
4. 加 fixture 回归。
5. 跑测试。

不要承诺无限兼容旧字段。保持当前结构干净更重要。
