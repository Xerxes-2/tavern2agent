# tavern2agent

把 SillyTavern 角色卡编译成 pi-native 互动叙事 runtime。

v2 不再把角色卡视为 prompt、世界书和状态栏的拼接物。它先提取卡片语义，再生成领域事件驱动的 runtime：

```txt
SillyTavern card
  → Card Semantic IR
  → Runtime Plan
  → Event Packs + State Schema + Reducers + Tools
  → Prompt Orchestrator
  → pi project
```

核心宪法：**prompt 描述世界，领域事件改变世界。**

## 范围

支持输入：

- ST v1/v2/v3：PNG、WEBP、JPEG、JSON
- 纯设定卡
- 世界书/MVU 卡
- 骰子、战斗、好感度、经济、任务、时间等系统卡
- 隐藏信息、多 NPC、多 agent 场景

默认剥离：HTML 状态栏、前端面板、文生图提示词、ST 宏运行时补丁、COT 标签、JSON Patch 输出格式。可迁移其背后的字段、规则、触发条件和 prompt composition 思路。

## 安装

```bash
git clone --depth 1 https://github.com/Xerxes-2/tavern2agent \
  ~/.pi/agent/skills/tavern2agent
```

更新：

```bash
cd ~/.pi/agent/skills/tavern2agent && git pull
```

## 使用

```bash
mkdir my-card && cd my-card
cp ~/Downloads/card.png .
pi
# 对 agent 说：帮我转换这张角色卡
```

agent 会解包、审计世界书和脚本、生成 `data/card-ir.json`、给出 Runtime Plan、选择 event packs、事实源和 subagent roles，再生成 pi 项目并下场校验。复杂卡写代码前会先给你看 Runtime Plan、state schema、event catalog、工具/API 清单和子代理边界。

## 产物形态

无可变世界的纯设定卡可以退化成 prompt-only：

```txt
project/
├── agents/preset.json
├── agents/gm-*.md
├── data/card-ir.json
├── data/runtime-plan.json
├── data/world.json
├── skills/start-game/SKILL.md
└── start.sh
```

有任何 mutable concept 的卡默认生成 evented runtime：

```txt
project/
├── .pi/settings.json
├── agents/preset.json
├── agents/gm-*.md
├── data/card-ir.json
├── data/runtime-plan.json
├── data/*.json
├── engine/events.ts
├── engine/reducers.ts
├── engine/state.ts
├── tools/registry.ts
├── extension.ts
├── skills/start-game/SKILL.md
└── start.sh
```

按需追加：`engine/migrations.ts`、`engine/codeact.ts`、`engine/codeact-sandbox.d.ts`、`extensions/subagents/*`、`.pi/agents/*`、event-pack 专用数据和测试。

`state/`、`sessions/`、`.pi/agent/`、`.pi/npm/` 不发布。

## 方案

面向读者的速览；权威判定见 `references/decision-tree.md`。

| 卡片特征 | v2 方案 |
|---|---|
| 无可变世界、无秘密边界 | prompt-only 退化形态 |
| 少量可变概念 | evented light：typed domain tools + reducer |
| 多字段联动、骰子、战斗、经济、时间压缩 | evented standard：event packs + reducer + typed tools / CodeAct API |
| 隐藏信息、秘密视角、多阵营 | 叠加 secret / faction / offscreen pack 和 project subagent |
| 现实题材、开源/API/活资料 | external research tools + local canonical data |

CodeAct 只是承载领域 API 的执行载体。无论用 typed tools 还是 CodeAct，状态变化都必须落成领域事件并经过 reducer。

网络搜索 / 抓取 / code search 可以取代手工知识库，但只能作为只读事实源；卡片 canonical facts 仍由本地 data/lookup 管。subagent 只输出视角反应、后台候选或审计意见，不直接写 state。

## 文档

```txt
SKILL.md                         agent 入口流程
references/evented-runtime.md    v2 宪法
references/card-ir.md            卡片语义 IR
references/event-packs.md        领域事件包
references/data-layer.md         本地 lookup 与外部 research 边界
references/multi-agent-architecture.md 子代理设计
references/                      迁移细节
docs/developing-cards.md         迁移后维护
docs/tooling.md                  可选工具
scripts/                         卡片解包/审计脚本
```

## 理念

不复刻 ST 运行时补丁。读懂卡作者想做的游戏，再用 pi 原生能力重建：事实可查，规则可算，事件可审计，状态可迁移，秘密不串层，叙事不破墙。
