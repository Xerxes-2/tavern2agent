# tavern2agent

将 SillyTavern 角色卡迁移为 pi coding agent 可运行的跑团/文字游戏环境。

## 这是什么

SillyTavern 用大量机制（MVU 更新、强化思考链、JSON Patch 等）绕开单次 LLM 调用的限制。agent 原生就能推理、调工具、自主决策——把这些补丁替换成真正的代码逻辑，让 agent 自己掷骰、计算、更新状态、推动叙事。

支持从纯设定卡到带骰子/战斗/好感度/经济系统的复杂游戏卡。

## 用法

本仓库是 pi coding agent 的一个 skill。放到 `~/.pi/agent/skills/tavern2agent/` 下，给 agent 一张角色卡，它就会自动按 skill 流程完成迁移。输出的具体目录和文件取决于卡的复杂程度。

## 目录

```
├── SKILL.md             # skill 主流程
├── references/          # 各类参考文档
├── scripts/             # Python 探索工具
└── README.md
```

## 设计思路

- **引擎用 TS，探索用 Python**：运行时逻辑放 engine，卡片解包和浏览用脚本
- **计算不进 prompt**：骰子、伤害、好感度等全部写成工具，LLM 不做算术
- **状态可回溯**：事件溯源，支持回到任意历史回合
- **GM prompt 极简**：核心规则不超过 5 条，agent 知道自己该干什么
