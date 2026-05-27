# tavern2agent

把 SillyTavern 角色卡迁移成 pi coding agent 可运行的文字游戏。

## 范围

支持：

- ST v1/v2/v3：PNG、WEBP、JPEG、JSON
- 纯设定卡
- 世界书/MVU 卡
- 骰子、战斗、好感度、经济等系统卡
- 隐藏信息、多 NPC、多 agent 场景

不迁移：HTML 状态栏、前端面板、文生图提示词、ST 预设模板。那些多是运行时补丁；迁移后可另接。

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

agent 会解包、审计世界书、选方案、生成项目、下场校验。复杂卡写代码前会先给你看 state schema 和 engine API。

## 产物形态

最小：

```txt
project/
├── agents/gm.md
├── data/world.json
├── skills/start-game/SKILL.md
└── start.sh
```

复杂：

```txt
project/
├── .pi/settings.json
├── .pi/agents/*.md
├── agents/gm.md
├── data/*.json
├── engine/codeact.ts
├── engine/codeact-sandbox.d.ts
├── engine/state.ts
├── tools/registry.ts
├── extension.ts
├── skills/start-game/SKILL.md
└── start.sh
```

`state/`、`sessions/`、`.pi/agent/`、`.pi/npm/` 不发布。

## 方案

| 卡片特征 | 方案 |
|---|---|
| 纯设定 | prompt |
| 少量键值状态 | light |
| 骰子/战斗/经济/多字段联动 | standard / CodeAct |
| 隐藏信息/秘密视角 | 叠加 subagent |

状态真相源是 pi session custom entry；`state/` 只做 debug export。

## 模型

迁移阶段：优先长上下文、代码、自检强的模型，如 Claude Sonnet/Opus、DeepSeek V4 Pro、GPT-5 系列。

运行阶段：优先中文叙事和工具调用稳定的模型，如 DeepSeek V4 Pro、Kimi、GLM、Claude Sonnet。

避免省钱档小模型。跑得动不等于跑得对。

## 文档

```txt
SKILL.md              agent 入口流程
references/           迁移细节
docs/developing-cards.md  迁移后维护
docs/tooling.md       可选工具
scripts/              卡片解包/审计脚本
```

## 理念

不把 ST 机制逐字翻译。读懂卡作者想做的游戏，再用 agent 原生能力重建：数据可查，规则可算，状态可回退，叙事不破墙。
