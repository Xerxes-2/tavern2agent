# 多 Agent

多 agent 用来隔离认知，不是提升“智能”的默认手段。

## 什么时候用

至少满足一项：

| 类型 | 信号 |
|---|---|
| 信息隔离 | NPC 秘密、阵营、凶手身份、未揭晓真相、PC 信息不对等 |
| 角色分离 | 反派、队友、吟游诗人等需要和 GM 完全不同的文风/目标 |
| 进程隔离 | 多地点并行、多 NPC 同时反应、可异步生成的新闻/传闻 |

不要因为卡复杂就拆 subagent。战斗/经济复杂通常进 engine/CodeAct，不进 subagent。

## 什么时候不用

- NPC 少且无秘密。
- 只是想让 GM 更聪明。
- 一个 TS 函数能解决的规则结算。
- 状态存储、patch 兜底、schema 校验。
- 高频轻量操作。

## 架构

```txt
用户 → GM → 调用相关 subagent → GM 汇总成主叙事
```

GM 负责：场景、规则、状态写入、最终叙事。

subagent 负责：某个视角的台词、反应、建议、异步文本。它不掌握完整状态，不直接写 state。

## 推荐分层

```txt
agent prompt       稳定职责、边界、输出格式
subagent extension 动态人格、状态切片、世界摘要
task               本轮触发原因 / 最近事件
chat history       叙事脉络
```

不要每次 task 里塞完整世界。动态事实由 extension 注入，task 只说近因。

## 文件

```txt
.pi/agents/*.md                 项目级 subagent 定义
extensions/subagents/*.ts        动态注入/轻量工具
tools/registry.ts               GM 调用入口
```

发布给玩家时，项目依赖写 `.pi/settings.json`；不要要求玩家装全局 subagent。开发用内置 coding agents 应在玩家模式禁用。

## Subagent prompt

只写角色事实：

```md
你是 <NPC>。

## 你知道
<公开信息 + 你的秘密>

## 你不知道
<其他人的秘密 / 完整世界状态 / GM 内部规则>

## 输出
只给你的台词、动作、反应。不要接管场景叙事。
```

不要写“这是 extension 注入的 system prompt”这类实现词。

## GM 调用

task 短：

```txt
最近事件：玩家当面质问你是否背叛公会。请按你的秘密和当前情绪回应。
```

GM 收到返回后，把台词/动作织入主叙事。多个 NPC 可并行调用。

## 状态写入

subagent 不拿 `code_act`，也不直接 patch state。需要状态变化时返回结构化建议：

```json
{ "suggestedChange": "relation", "target": "npc_a", "reason": "被玩家威胁" }
```

GM 决定是否通过主 engine 写入。

## 反模式

- 每个 NPC 都拆 agent。
- 子代理持有完整 state。
- 子代理负责修正 GM 遗漏的 patch。
- 用 subagent 代替工具 description、strict path、migration。
- 单线程场景硬拆并行。
