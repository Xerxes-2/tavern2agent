# tavern2agent

SillyTavern 角色卡 → pi coding agent 迁移引擎。

将 SillyTavern 角色卡（PNG/JSON）迁移为 pi coding agent 可运行的跑团/文字游戏环境，覆盖纯角色卡到带骰子/战斗/好感度/经济等完整游戏系统的复杂卡。

## 为什么用 agent 跑角色卡？

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁（MVU 更新、强化思考链、JSON Patch 格式等）。agent 天生能推理、调工具、自主决策：

- **loop**：查询状态 → 掷骰 → 计算 → 更新 → 叙事，每一步都是真实工具调用，不是 LLM 脑补
- **自我纠正**：算错了 dispatch 修正事件，不需要预设校验规则
- **动态上下文**：数据文件 + 查询工具按需加载，不把整个世界书塞进 prompt

## 产出物

```
project/
├── skills/开局.md          # 游戏入口 skill
├── agents/
│   ├── gm.md               # GM system prompt
│   └── narrator.md         # 叙事 subagent（有游戏系统时）
├── engine/                 # TS 引擎模块
│   ├── state.ts            # 状态引擎（事件溯源）
│   ├── dice.ts             # 骰子系统
│   └── ...                 # combat / affection / economy 等按需
├── tools/registry.ts       # 工具注册
└── data/                   # 世界书拆解数据
    ├── world.json          # 世界设定
    └── characters.json     # 角色数据
```

## 使用方式

作为 pi coding agent 的 skill 使用。将本仓库放到 `~/.pi/agent/skills/tavern2agent/`，用户提供角色卡后 agent 自动加载此 skill 执行迁移。

## 设计原则

- **引擎用 TS，探索用 Python**：运行时逻辑用 TypeScript（被 extension import 零开销调用），卡片解包/浏览脚本用 Python
- **agent 是程序本身**：不把计算逻辑写入 prompt，写成工具让 agent 自己调度
- **所有计算进 engine**：骰子/伤害/好感度进 `engine/*.ts`，LLM 不做算术
- **prompt 极简**：GM prompt 核心规则 ≤5 条
- **状态事务化**：事件溯源支持到任意历史回合的回退

## 目录结构

```
tavern2agent/
├── SKILL.md                        # skill 主文件
├── references/                     # 参考文档
│   ├── design-principles.md        # 设计原则
│   ├── script-analysis.md          # 卡内脚本分析
│   ├── mvu-mapping.md             # MVU 条目 → engine 映射
│   ├── setup.md                    # 开局 setup
│   ├── platform-adapters.md        # pi 平台胶水层
│   ├── ts-engine.md                # TS 引擎代码参考
│   ├── multi-agent-architecture.md # GM + Narrator 架构
│   ├── storytelling.md             # 叙事节拍参考
│   └── validation.md               # 产出校验
└── scripts/                        # Python 探索工具
    ├── extract_png.py              # PNG → JSON
    ├── list_entries.py             # 世界书条目概览
    └── get_entry.py                # 读单条完整内容
```

## 方案档位

| 情况 | 方案 | 产出范围 |
|------|------|---------|
| 无 MVU 条目（纯角色卡） | **纯 prompt** | agents/gm.md + data/ |
| 有键值状态，无骰子/公式 | **轻量** | 上者 + engine/state.ts + 查询/更新工具 |
| 有骰子/战斗/经济 | **中等** | 上者 + engine/dice.ts 等 + 每轮快照 |
| 需死亡回溯/章节存档 | **完整 engine** | 事件溯源 + 全套模块 + 多 agent |
