# tavern2agent

将 SillyTavern 角色卡迁移为 pi coding agent 可运行的跑团/文字游戏环境。

## 这是什么

SillyTavern 用大量机制（MVU 更新、强化思考链、JSON Patch 等）绕开单次 LLM 调用的限制。agent 原生就能推理、调工具、自主决策——把这些补丁替换成真正的代码逻辑，让 agent 自己掷骰、计算、更新状态、推动叙事。

支持从纯设定卡到带骰子/战斗/好感度/经济系统的复杂游戏卡。

## 能不能用

- **角色卡**：SillyTavern v2（`spec: "chara_card_v2"`）。v1 老卡请先用 ST 或第三方工具升级到 v2 再迁移
- **推荐模型**：DeepSeek V4 Pro / GPT-5.5 / Claude Sonnet 4.6+ / Opus 4.5+。弱模型（Flash 档）能跑但可能需要反复调试
- **平台**：pi coding agent。其他平台理论上替换胶水层即可，但未官方支持

## 最小示例

```bash
# 1. 安装为 pi skill
git clone https://github.com/Xerxes-2/tavern2agent ~/.pi/agent/skills/tavern2agent

# 2. 在工作目录放一张角色卡
mkdir my-card && cd my-card
cp ~/Downloads/某角色卡.png .

# 3. 启动 pi 告诉 agent
pi
> 帮我把这张卡迁移成 agent 跑团环境
```

agent 会自动按 skill 流程：解包 PNG → 分析世界书 → 决定方案档位 → 生成 engine/agents/data → 校验。中等以上复杂度的卡会在写代码前发一份 state schema 给你 review，避免后期返工。

迁移完成后，agent 自带交互式调试能力——「这条规则没生效」「这个 NPC 该有秘密」直接告诉它。

## 产出形态

最简（纯设定卡，无游戏系统）：

```
project/
├── agents/gm.md
├── data/world.json
├── data/characters.json     # ≥5 角色时拆分
└── skills/开局.md
```

最复杂（带战斗 + 死亡回溯 + 多 NPC 信息隔离）：

```
project/
├── agents/
│   ├── gm.md
│   └── npc_*.md             # 每个有秘密的 NPC 一个
├── engine/
│   ├── state.ts             # 事件溯源
│   ├── dice.ts
│   ├── combat.ts
│   └── death.ts
├── tools/registry.ts
├── extension.ts             # pi 入口
├── data/
│   ├── world.json
│   ├── characters.json
│   └── chapters.json
└── skills/开局.md
```

中间还有「轻量」「中等」两档，按卡片复杂度自动落档，决策表见 `SKILL.md`。

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
