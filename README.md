# tavern2agent

将 SillyTavern 角色卡迁移为 pi coding agent 可运行的跑团/文字游戏环境。

## 这是什么

SillyTavern 用大量机制（MVU 更新、强化思考链、JSON Patch 等）绕开单次 LLM 调用的限制。agent 原生就能推理、调工具、自主决策——把这些补丁替换成真正的代码逻辑，让 agent 自己掷骰、计算、更新状态、推动叙事。

支持从纯设定卡到带骰子/战斗/好感度/经济系统的复杂游戏卡。

## 用法

本仓库是 pi coding agent 的一个 skill。放到 `~/.pi/agent/skills/tavern2agent/` 下，给 agent 一张角色卡，它就会自动按 skill 流程完成迁移。输出的具体目录和文件取决于卡的复杂程度。

生成的卡有问题或者不知道怎么用，直接问 agent。

## 目录

```
├── SKILL.md             # skill 主流程
├── references/          # 各类参考文档
├── scripts/             # Python 探索工具
└── README.md
```

## 设计思路

**酒馆的固有缺陷。** 单次 LLM 调用、死板的上下文管理、没有真正的工具调用——所以角色卡作者才需要把游戏规则写成 prompt 里的魔法咒语，靠自然语言驱动 LLM"假装"在掷骰子、算伤害。

**Agent 的 meta 能力。** Agent 可以自己调工具、自己读文件、自己查状态、算错了自我纠正。它不是一个被动等待 prompt 的 LLM，而是一个真正在跑的游戏循环。

**不追求复刻，追求还原。** 迁移的目标不是把 SillyTavern 的机制一比一搬过来，而是理解作者想在卡片里做什么游戏，然后用 agent 原生的方式实现它。
