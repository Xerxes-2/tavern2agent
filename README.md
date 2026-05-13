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

SillyTavern 的角色卡本质上是一套完整的游戏规则被人肉塞进了 prompt 里——骰子公式、伤害计算、状态追踪、叙事推进，全都靠自然语言指令驱动 LLM 脑补。为了让它勉强跑通，作者不得不写一堆补丁：强化思考链、认知隔离、JSON Patch 输出格式……这些东西跟游戏本身毫无关系，纯粹是在给 LLM 打绷带。

agent 时代这些东西可以扔掉。agent 会调工具、会写文件、会自己查自己算——把游戏规则从 prompt 里抽出来，写成真正的代码引擎，让 agent 自主调度。一张原本需要 LLM"假装"在跑的游戏卡，变成了一套真的在跑的游戏系统。

迁移的目标不是复刻 SillyTavern 的机制，而是还原作者的设计意图。
