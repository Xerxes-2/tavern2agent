# tavern2agent

将 SillyTavern 角色卡迁移为 pi coding agent 可运行的跑团/文字游戏环境。

## 这是什么

SillyTavern 用大量机制（MVU 更新、强化思考链、JSON Patch 等）绕开单次 LLM 调用的限制。agent 原生就能推理、调工具、自主决策——把这些补丁替换成真正的代码逻辑，让 agent 自己掷骰、计算、更新状态、推动叙事。

支持从纯设定卡到带骰子/战斗/好感度/经济系统的复杂游戏卡。

## 能不能用

- **角色卡**：SillyTavern v2 / v3（`spec: "chara_card_v2"` 或 `"chara_card_v3"`）。v1 老卡请先用 ST 或第三方工具升级
- **平台**：pi coding agent。其他平台理论上替换胶水层即可，但未官方支持
- **只做文字交互**：前端面板/状态条 HTML、文生图提示词、预设模板等不迁移——它们多是 ST 运行时补丁，留着反而损失灵活性，想要的人转换完成后自行接入

### 推荐模型

迁移阶段与运行阶段对模型的要求不同，分开看：

**迁移阶段**（跑 skill 把卡转成 agent 项目）——吃指令遵循 + 长上下文 + 代码 + 自检：

| 模型 | 适配点 |
|---|---|
| Claude Sonnet 4.6 / Opus 4.7 | 隐性约定推断最稳、SWE-bench 顶档；skill 默认环境 |
| DeepSeek V4 Pro（Max 推理） | 1M context 整卡塞得下、中文母语级、价格友好 |
| GPT-5.4 | Terminal-Bench 最强，重 agent loop 场景适用 |

**运行阶段**（产出的 GM 跑游戏）——吃中文叙事 + 工具调用 + 长会话一致性：

| 模型 | 适配点 |
|---|---|
| **DeepSeek V4 Pro** ⭐ | 已实测，中文叙事强、1M context、按 token 算极便宜 |
| Kimi K2.6 | 256K 上下文 + 角色扮演场景调优，长跑游戏一致性好 |
| GLM-5 | 国产 agent 调优、中文工具调用稳，比 Pro 更便宜 |
| Claude Sonnet 4.6 | 规则遵循扎实、破第四墙概率低；预算够时优先 |

### ⚠️ 不推荐

- **DeepSeek V4 Flash / Flash@max** 等"省钱档"——实测会漏 `{{user}}`/`{{char}}` 字面量、自报"我已加载设定"破第四墙，隐性约定全靠 prompt 兜底。省下的钱不够调试时间
- **<30B 激活参数的开源小模型**——跑得动 ≠ 跑得对
- **GPT-4o / Gemini 1.5 等旧世代**——上下文小、工具调用绕

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

agent 会自动按 skill 流程：解包 PNG → 分析世界书 → 决定方案档位 → 生成 engine/agents/data → 校验。标准方案（有 engine 模块）的卡会在写代码前发一份 state schema 给你 review，避免后期返工。

迁移完成后，agent 自带交互式调试能力——「这条规则没生效」「这个 NPC 该有秘密」直接告诉它。

## 产出形态

最简（纯设定卡，无游戏系统）：

```
project/
├── agents/gm.md
├── data/world.json
├── data/characters.json     # ≥5 角色时拆分
└── skills/
    └── start-game/
        └── SKILL.md
```

最复杂（带战斗 + 多 NPC 信息隔离）：

```
project/
├── agents/
│   ├── gm.md
│   └── npc_*.md             # 每个有秘密的 NPC 一个
├── engine/
│   ├── state.ts             # patchState (RFC 6902)
│   ├── dice.ts
│   ├── combat.ts
│   └── attention.ts
├── tools/registry.ts
├── extension.ts             # pi 入口
├── data/
│   ├── world.json
│   ├── characters.json
│   └── chapters.json
└── skills/
    └── start-game/
        └── SKILL.md
```

中间还有「轻量」一档，按卡片复杂度自动落档，决策表见 `SKILL.md`。

**回退 / 存档**：tavern2agent 不自建回滚，统一外包给 pi 平台层扩展。推荐 `pi install npm:pi-rewind-hook`——`/fork` 或 Tab 进 `/tree` 选目标轮还原。详见 `SKILL.md` §六。

## 目录

```
├── SKILL.md             # skill 主流程
├── references/          # 各类参考文档
├── scripts/             # Python 探索工具
└── README.md
```

## 设计思路

**酒馆的固有缺陷。** 单次 LLM 调用、被动的上下文窗口、没有真正的工具——卡片作者只能把规则编成 prompt 咒语，让模型"演"出在掷骰、算伤害。游戏机制成了叙事的幻觉，而非程序。

**Agent 是程序本身。** Agent 自己调度、自己查询、算错了自我纠正，是一段持续运行的循环。掷骰是真的，状态写入是真的，回退是真的——不是 LLM 在文字里假装。

**不复刻，要还原。** 不把 ST 机制原样翻译，而是读懂作者想做的那个游戏，再用 agent 原生形态把它跑起来。咒语换成代码，幻觉换成事实。
