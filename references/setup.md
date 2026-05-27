# 开局 setup

每张迁移卡都要有 `skills/start-game/SKILL.md`。它负责收集开局缺失信息，然后交付开场叙事。

## 找缺失信息

| 信号 | 含义 |
|---|---|
| 世界书有 `{{user}}设定` / 用户人设 | 需要用户角色字段 |
| 主字段含 `{{user}}` | 需要用户身份 |
| `first_mes` 末尾是问句/选项 | 需要开局选择 |
| 世界书有“开局设置”条目 | 需要配置 |
| 纯叙事无占位 | 直接开场 |

`alternate_greetings` / `group_only_greetings` 按路线选项处理，不能丢。

## ST 宏剥离

写入 `agents/`、`skills/`、`data/` 前处理：

| 残留 | 处理 |
|---|---|
| `{{user}}` | 具体姓名、第二人称，或 user 数据引用 |
| `{{char}}` | 角色名 |
| `{{random:*}}` / `{{pick:*}}` | 迁移时定值，或改成选项 |
| `{{roll:*}}` | 迁入 engine |
| `{{getvar:*}}` / `{{setvar:*}}` | 改为状态工具 |
| HTML/status/thinking/EJS | 删除或改写为叙事 |

检查：

```bash
grep -rnE '\{\{(user|char|random|roll|pick|getvar|setvar)' agents/ skills/ data/
```

不应有命中。

## Skill 模板

```md
---
name: start-game
description: 开始/重新开始《卡片名》游戏。收集用户角色信息后交付开场叙事。当用户说「开始」「开局」「开始游戏」「重新开始」时使用此技能。
---

# 开局

你是《卡片名》的 GM。用户请求开始游戏。

## setup

叙事前检查信息是否齐全。缺失项一次性列出，每项给参考默认值。等用户逐项确认或修改后继续。

{{setup_checklist}}

规则：
- 所有缺失项一轮问完。
- 每项给默认值。
- 用户不能整体跳过；必须确认或修改。

## 开场参考

{{opening_narrative}}

## 开场

信息齐全后，基于参考展开开场。不要复述原文，不要自报“设定已加载”。直接进场。
```

## checklist 生成

| 情况 | 文本 |
|---|---|
| 无缺失 | 无需额外信息，直接进入开场。 |
| 缺少少数字段 | 列字段 + 默认值，请确认或修改。 |
| 用户卡全缺 | 给姓名/性别/外貌/背景默认值。 |
| 开局选项 | 列选项 + 推荐默认项。 |
| 多类混合 | 合并一轮问完。 |

## 平台集成

extension 注入 GM prompt + 注册工具。首轮或用户说“开始/开局”时，agent 读 `skills/start-game/SKILL.md`。

流程：

```txt
开始 → 读 start-game skill → 一轮收集缺失项 → 用户确认 → 开场叙事
```
