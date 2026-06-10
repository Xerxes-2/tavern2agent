# 多 Agent

多 agent 用来隔离认知、并行候选和题材审计。想让 GM 「更聪明」不构成拆分理由。

当前推荐设计来自 evented runtime：**subagent 不写 state，不拿 CodeAct，不当陪聊 NPC；它只输出候选、视角反应或审计意见，由 GM 转成领域事件。**

## 什么时候用

至少满足一项：

| 类型 | 信号 | 推荐形态 |
|---|---|---|
| 信息隔离 | NPC 秘密、阵营、凶手身份、未揭晓真相、PC 信息不对等 | perspective / secret subagent |
| 后台并行 | 多地点并行、多 NPC 自治、阵营计划、可异步生成的新闻/传闻 | parallel-line subagent |
| 题材审计 | 长跑容易 drift、NPC 变成传感器、beat 不收口、世界不动 | timeline/showrunner auditor |
| 风格分离 | 反派、队友、吟游诗人等需要和 GM 完全不同的文风/目标 | perspective subagent |

不要因为卡复杂就拆 subagent。战斗/经济复杂通常进 engine/CodeAct，不进 subagent。

## 什么时候不用

- NPC 少且无秘密。
- 只是想让 GM 更聪明。
- 一个 TS 函数能解决的规则结算。
- 状态存储、patch 兜底、schema 校验。
- 高频轻量操作。
- 可以由 event pack / tool description 解决的调用纪律问题。

## 架构

```txt
用户 → GM → 调用相关 subagent → GM 选择/改写 → domain event → reducer → 主叙事
```

GM 负责：场景、规则、状态写入、最终叙事。

subagent 负责：某个视角的台词/反应、后台事件候选、时间线审计、风险提示。它不掌握完整状态，不直接写 state。

## 项目级硬约束

生成的 subagent 必须是 project-scope，不依赖用户全局 agent：

```txt
.pi/agents/*.md                  项目级 subagent 定义
extensions/subagents/<name>.ts    动态注入/lookup/tool 限制
tools/registry.ts                GM 调用入口
.pi/settings.json                项目依赖声明
```

约束：

- `inheritProjectContext: false`：不要继承整包项目上下文。
- `inheritSkills: false`：不要加载玩家技能目录。
- 显式配置 `tools`：通常只给 lookup / readonly 工具；不给 `code_act`。
- 显式配置 `extensions`：只加载该 subagent 的 context injector；不要省略。路径从 extension 文件所在目录推导，不靠 cwd 猜。
- 输出格式稳定：候选类 subagent 用 bare JSON；审计类 subagent 用短结构化 report。
- 发布包包含 `.pi/agents/` 和 `extensions/subagents/`；不要要求玩家装 user-scope subagent。

## 推荐分层

```txt
agent prompt        稳定职责、边界、输出格式
subagent extension  动态状态切片、秘密切片、lookup、timeline context
task                本轮触发原因 / 最近事件
chat history        必要叙事脉络
```

不要每次 task 里塞完整世界。动态事实由 extension 注入，task 只说近因。

extension 注入必须带游戏内日期、时间和时区。subagent 拿不到主时钟就会自己猜，产出「凌晨发生在白天」这类错位候选。

## 典型 subagent

### perspective / secret

用于 NPC 秘密、凶手视角、阵营视角。输出台词、动作倾向、隐瞒策略，不输出最终叙事。

```json
{
  "actorId": "npc_a",
  "visibleResponse": "...",
  "privateIntent": "...",
  "suggestedEvents": []
}
```

`privateIntent` 给 GM 决策，不进入 public memory。

### parallel-line

用于后台平行线候选。它不写新闻稿，不替代事件本体；只输出可被 GM 审核的 offscreen 候选。

输出必须是 bare JSON：

```json
{
  "events": [
    {
      "actorOrFactionId": "guild_red",
      "locationId": "old_port",
      "action": "move contraband before dawn",
      "consequence": "guards redirected from north gate",
      "frontstageTrace": "dock workers mention an unscheduled convoy",
      "suggestedDomainEvent": "record_offscreen_event"
    }
  ]
}
```

GM 选择后，通过 `record_offscreen_event` 或 `commit_turn` 写入。新闻、传闻、门响只是 trace，不是后台事件本体。

写入侧拒绝晚于当前时钟的候选：offscreen 事件记录已经发生的事，未来计划留在候选池或 faction plan 里。

### timeline / showrunner auditor

用于长跑审计。它检查：

- 世界是否在玩家视野外运动。
- NPC 是否有自主目标，而不是只响应玩家。
- beat 是否悬挂未收口。
- hook 是否重复滥用。
- hidden/public 是否串层。
- 当前题材是否 drift。

输出建议，不写正文，不写 state。

```json
{
  "findings": [
    { "severity": "warning", "issue": "current beat has no closure pressure", "suggestedFix": "finish_current_beat after next concrete choice" }
  ],
  "candidateEvents": []
}
```

## Subagent prompt

只写角色事实和输出边界：

```md
你是 <NPC / faction / auditor>。

## 你知道
<公开信息 + 你的秘密 / 审计上下文>

## 你不知道
<其他人的秘密 / 完整世界状态 / GM 内部规则>

## 输出
只输出指定 JSON / 反应 / 审计。不要接管场景叙事，不要写 state。
```

不要写「这是 extension 注入的 system prompt」这类实现词。

## GM 调用

task 短：

```txt
最近事件：玩家当面质问你是否背叛公会。请按你的秘密和当前情绪回应。
```

GM 收到返回后，把台词/动作织入主叙事，或把候选转成领域事件。多个 NPC / parallel-line 可并行调用。

## 状态写入

subagent 不拿 `code_act`，也不直接 patch state。需要状态变化时返回结构化建议：

```json
{
  "suggestedEvent": "record_relationship_shift",
  "actorId": "npc_a",
  "targetId": "protagonist",
  "reason": "被玩家威胁后转为戒备"
}
```

GM 决定是否通过主 engine 写入。

## 反模式

- 每个 NPC 都拆 agent。
- 子代理持有完整 state。
- 子代理负责修正 GM 遗漏的 patch。
- 子代理拿 `code_act` 或 debug/migration 工具。
- 用 subagent 代替工具 description、strict path、migration。
- 单线程场景硬拆并行。
- 候选 subagent 输出 Markdown 长文，迫使 GM 再抽结构。
