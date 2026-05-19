---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 pi coding agent 时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策。核心优势：agent 可以 loop（查询→掷骰→计算→更新→叙事）、自我纠正（算错了重新发事件修正）、动态管理上下文（数据文件 + 查询工具）。

目标平台是 pi coding agent，详见 `references/pi-integration.md`。

**能力边界**：本 skill 只产出**文字交互**的 agent。前端面板/状态条 HTML、文生图（SD/NAI/ComfyUI）提示词、预设与上下文模板等一律剥离或丢弃——不是做不到，而是这些大多是 ST 运行时补丁，agent 不需要，强行复刻反而锁死灵活性。需要的人转换完成后自行接入。

---

## 〇、开工前确认

1. **先读 `references/design-principles.md`**——十条核心原则（agent 是程序本身、所有计算进引擎、prompt 极简、砍掉强化思考链等）决定了产出的形态，不读容易把 ST 机制直译为代码，错过 agent 的核心优势。
2. **确认输出目录**：用户如果说「输出到 xxx 目录」「放到 cards/ 下」，直接照做。如果用户只说「转换这张卡」没指定路径，主动问一句：「输出到哪个目录？目录名用卡片名还是自定义？」用户没指定命名规则时，默认取卡片 `data.name` 作为目录名（非法字符替换为下划线），放在卡片 PNG 同级目录下。
3. **检查工作目录**：如果目标目录已存在 `agents/`、`engine/`、`skills/start-game/SKILL.md` 等，先和用户确认是覆盖、增量更新、还是另开目录。用户没明说时直接问一句。
   - **增量更新模式**（用户选「增量」时的硬约束）：
     - **不要 `rm -rf` 或全量重写**——目标目录可能有用户手改过的 prompt、engine 公式、data 字段
     - 动手前 `git log --oneline -20` + `git diff` 当前 worktree，识别人工调整的痕迹
     - 改动只针对用户要求的部分；其他文件**只有在 schema 不兼容时才动**，动之前先在回复里列出来
     - **不要碰 `refs/pi-rewind/*` 或 `sessions/`**——那是玩家存档/会话数据，不归迁移流程管

---

## 一、快速开始

```bash
python3 scripts/extract_card.py <角色卡>  card.json   # PNG/WEBP/JPEG/JSON 解包
python3 scripts/list_entries.py card.json --filter mvu     # 看 MVU 条目
python3 scripts/list_entries.py card.json --filter initvar # 看初始值
```

| 脚本 | 用途 |
|------|------|
| `extract_card.py <file> [out.json]` | 角色卡 → JSON（PNG/WEBP/JPEG/JSON） |
| `list_entries.py <json> [--filter mvu\|initvar]` | 世界书条目概览 |
| `get_entry.py <json> <索引>` | 读条目完整内容 |

> **支持 v1 / v2 / v3 卡**：v2/v3 卡（`spec` 为 `chara_card_v2` 或 `chara_card_v3`）原样处理；**v1 老卡（字段直接挂顶层）由 `extract_card.py` 自动归一化为 v2 schema**（产出 JSON 带 `_normalized_from_v1: true` 标记），下游一律按 v2 路径读。v1 卡通常无世界书 + 无 MVU，几乎只落「纯 prompt」档——可以正常跑，但 agent 的复杂决策（多 agent / engine 模块）基本用不上。v3 新增字段（`assets` / `group_only_greetings` / `creator_notes_multilingual` / `source` 等）当前不专门处理：`group_only_greetings` 与 `alternate_greetings` 同等对待（路线选项 / 合并 setup），其余视为元数据忽略。

**大数据量卡片（条目 ≥100）**：脚本工具仅供探索阶段使用；构建阶段用 `python3 -c` 批量提取 + 紧凑索引法（先建 5-10K tokens 索引，再按需 lazy load 正文）。具体样例代码见 `references/mvu-mapping.md` §「探索阶段：紧凑索引」。

---

## 二、卡片分析

### 卡片 JSON 速览（v2）

提取后的 `card.json` 关键路径：

| 路径 | 内容 |
|------|------|
| `data.name` / `data.description` / `data.personality` / `data.scenario` | 角色基础设定 |
| `data.first_mes` | 开场白（迁移时改写后内联到开局 skill） |
| `data.alternate_greetings[]`（v3 另含 `data.group_only_greetings[]`） | 替选开场白数组。**不要忽略**——通常是不同路线/分支的开局。处理方式：作为开局 skill 的路线选项让用户选，或合并入 setup checklist |
| `data.system_prompt` / `data.post_history_instructions` | 卡片自带 system prompt（可能含规则） |
| `data.character_book.entries[]` | 世界书条目数组。每条有 `comment`（标签，如 `[mvu_update]`）、`content`（正文）、`keys`（触发词）、`enabled` |
| `data.extensions.tavern_helper.scripts[]` | TH 脚本（Zod 模型 / 游戏逻辑） |
| `data.extensions.regex_scripts[]` | 正则脚本（UI 渲染 / 内容注入） |
| `data.creator_notes` | 作者使用说明（往往透露隐藏机制） |

> 实际操作前先 `python3 -c "import json; print(list(json.load(open('card.json'))['data'].keys()))"` 看一眼，不同卡片可能省略部分字段。

### 条目全量审计（写任何产出文件前必须执行）

不先看全所有条目就动手，是本次迁移中最常见的返工原因。

```bash
# 第一步：无过滤列出全部条目（只输出 comment + keys + 前 3 行正文 + 字符数）
python3 scripts/list_entries.py card.json
```

得到完整条目清单后，**逐条分类决策去向**——不要跳到「条目 0 看起来够了」就收工。常见五类速查：

| 条目类型 | 判断信号 | 去向 |
|---------|---------|------|
| 系统规则/术语/地区 | `comment` 含「系统设定」/「地区设定」/「术语」 / `constant: true` | `data/world.json`（或拆 `regions.json`） |
| 角色/NPC 模板 | `comment` 含 `<character_card>` / 角色名 | `data/characters.json` |
| 章节剧情 | `comment` 含「第X卷」「章节」 | `data/chapters.json` + 查询工具 |
| 骰子/键值状态 | `content` 含 `{{roll:`、伤害公式；或 `comment` 含 `[initvar]`/`[mvu_update]` | `engine/dice.ts` 等 / `engine/state.ts` → `INITIAL_STATE` |
| ST 补丁 | `content` 含「强化思考」「JSON Patch」「`__结束__`」 | **丢弃** |

**特殊处理**（必读）：路线/分支专属条目、disabled 条目——这两类极易被默认丢弃，必须按完整分类表逐条审计。完整 10 类分类表 + 路线联动 + disabled 渐进披露处理见 `references/mvu-mapping.md` §「条目分类决策完整表」。

**做完这一步再决定方案档位**——条目数量决定了 world.json 的规模：纯地理念卡 world.json ≤5KB 合理；大量常驻系统条目的卡，world.json 自然 20-30KB。

### 信息源排查

按顺序排查四个信息源，详情见对应 reference：

| 步骤 | 看什么 | 关键信号 | 详参 |
|------|--------|---------|------|
| 1 | `tavern_helper.scripts` | 有 Zod 脚本？有外链游戏脚本？ | `references/script-analysis.md` |
| 2 | `regex_scripts` | 有游戏内容注入（非纯 UI）？ | `references/script-analysis.md` |
| 3 | 世界书 `[initvar]` 条目 | 初始状态权威来源（YAML） | `references/mvu-mapping.md` |
| 4 | 世界书 `[mvu_update]`/`[mvu_plot]` 条目 | 骰子公式？伤害规则？变量定义？ | `references/mvu-mapping.md` |

按表格顺序排查；如脚本（步骤 1-2）没有线索，再从世界书 MVU 条目（步骤 3-4）自行提取规则。

### 开局 setup 分析（必须）

扫描 `first_mes` 和世界书，汇总「缺失信息清单」——user 卡定义、开局选项等。详见 `references/setup.md`。

---

## 三、决策表

| 情况 | 方案 | state 写入 | 产出 |
|------|------|-----------|------|
| 没有 MVU 条目 | **纯 prompt** | — | `agents/gm.md`、`data/` |
| 只有键值状态，无骰子/公式 | **轻量** | `patchState` | 上者 + `engine/state.ts` + `get_status`/`patch_state` 工具 |
| 有骰子/战斗/经济等计算模块 | **标准** | `patchState` | 上者 + `engine/dice.ts` 等模块（多 agent 见下方独立判定） |

> **回退 / 存档不进 engine**。死亡回溯、章节存档、撤销上一轮——以前用事件溯源做，现在统一外包给 pi 平台层的回退扩展（推荐 `pi-rewind-hook`），档位判定里不再考虑此维度。详见 §六「回退 / 存档」。

### 多 agent 判定（独立维度，不跟方案档位绑定）

多 agent 的核心用途是 **认知隔离**——任何"某个视角不该看到的信息"都可以拆进独立 context。NPC 秘密只是最常见的一种：模型在单一 context 里读到 NPC A 的秘密，就会让 NPC B 做出不该有的反应。但隔离对象不限于 NPC——悬疑/侦探题材里凶手身份、未揭晓的真相、玩家尚未推理出的线索，都该挡在主 context 之外，否则 GM 会"剧透式叙事"。GM 仍是主叙事者，subagent 只负责自己那块被隔离的视角。

**多 agent 的决策跟 game engine 复杂度无关**。一张无骰子的纯 prompt 卡，只要存在认知隔离需求（NPC 秘密、信息不对等、隐藏真相），就该走多 agent。

| 触发信号 | 行动 |
|----------|------|
| NPC ≤4 且无隐藏信息、无隐藏剧情 | 单 agent（GM 自己扮演所有 NPC） |
| NPC ≥5 且有隐藏信息/秘密/阵营 | 多 agent：每个有秘密的 NPC 独立 subagent，GM 织入叙事 |
| 视角间信息不对等（NPC 之间、PC 之间，或 GM 不该看到的真相）| 多 agent——这正是认知隔离的核心价值 |
| 悬疑/侦探等"答案不能泄漏给叙事者"的题材 | 多 agent：真相/凶手视角独立 context，主 GM 只拿到该揭晓的部分 |

### subagent 适用场景

判断标准三选一：**信息隔离**（角色不该看到的东西）、**角色分离**（跟 GM 完全不同的人格/文风）、**进程隔离**（适合异步/并行）。完整分类（含信息隔离/角色分离/进程隔离/并行/状态跟踪/反模式）见 `references/multi-agent-architecture.md` §附录。

**临界场景拿不准时**，去 `references/decision-tree.md` 查辅助判定信号（5 条）+ 归档样例（8 条具体卡片特征 → 落档结论），按样例粒度对齐，不要纠结临界条款的字面。

---

## 四、实现要点

### 纯 prompt 方案

产出 `agents/gm.md`（角色+世界+规则，核心规则≤5条）+ `data/world.json` + `data/characters.json`（≥5角色时拆分）+ `data/chapters.json`（如有）。

开场白：所有方案都必须生成开局 skill，`first_mes` 改写后内联其中、由 agent 在开局时主动交付。命名规则、模板、checklist 生成规则统一见 `references/setup.md`。

### 轻量 / 标准方案

state 骨架代码见 `references/ts-engine.md`「轻量 / 标准方案」。engine 模块按需写（`dice.ts`/`combat.ts`/`affection.ts`/`economy.ts` 等），识别信号见 `references/mvu-mapping.md`。

如果同时触发多 agent 条件（见上文），叠加多 agent 架构，详见 `references/multi-agent-architecture.md`。

标准方案的 `gm.md` 末尾建议加一行引用 `references/storytelling.md`，让 GM 在叙事卡壳时按需自查节拍——具体引用句式见 storytelling.md §「在 gm.md 里如何引用」。

### 中间检查点（标准方案必走）

写 `engine/*.ts` 前，先把 **state schema** + **engine 操作清单** 单独发给用户 review。schema 必须覆盖**用户卡创建字段**（姓名/性别/外貌等）——它们不在 InitVar 里，遗漏会让 `patch_state` 的 `replace` 操作静默失败。技术细节与 RFC 6902 陷阱见 `references/mvu-mapping.md` §「⚠️ 用户卡字段不在 InitVar 里」+ §「⚠️ RFC 6902 陷阱」。

轻量方案 schema 一眼能看完，可跳过此步。

### 注意力调度（标准方案强烈推荐）

LLM 不擅长计数和定时触发。游戏存在「每 N 轮调用同伴」「战斗后必须 try_level_up」「NPC 互动后必更新好感度」「DLC 启用后定期提醒」任一需求，写 `engine/attention.ts`。代码模式 + 注入点 + 双重保障原则见 `references/ts-engine.md` §「注意力调度 (attention.ts)」。

### 数据查询工具（标准方案强烈推荐）

凡是有结构化数据集合（地点 ≥20、NPC ≥5、DLC 模块），必须配查询工具。否则数据等于不存在：

| 数据 | 工具 | 索引文件 |
|------|------|---------|
| 世界地点 | `lookup_location` | `data/location_index.json`（地点名 → world.json 条目映射） |
| 预设 NPC | `lookup_npc` | `data/npc_index.json`（NPC 名 → characters.json 条目映射） |
| DLC 模块 | `get_dlc_info` | `data/dlc_index.json`（模块名 → 数据键 + 摘要 + 文件位置） |

索引文件用 `python3 -c` 批量扫描生成，不要手写。

### 工具 description 工程（所有方案，凡注册工具就必读）

**工具能查数据 ≠ 模型会调用工具。** 强叙事模型（DS V4、Claude Opus 等）会默认凭记忆/即兴创作而不调读取类工具。每个工具的 `description` 必须包含「必须调用的场景」+「严禁的行为」（+ 战斗类的「你的职责」）。模板、双层框架、few-shot、模型差异微调表、实测效果对比见 `references/pi-integration.md` §「工具 description 工程」。

---

## 五、产出清单

迁移完成后，确保以下文件齐全：

| 文件 | 必需？ | 说明 |
|------|:-----:|------|
| `skills/<skill-name>/SKILL.md` | ✅ 必须 | 游戏入口 skill（如 `skills/start-game/SKILL.md`），处理 user 卡/配置/开场 |
| `agents/gm.md` | ✅ 必须 | GM system prompt |
| `.pi/agents/<npc_xxx>.md` | 有隐藏信息/视角隔离需求时 | pi-subagents 项目级 NPC subagent（每个需隔离的 NPC 一个，上下文隔离）；触发条件详见 §三「多 agent 判定」 |
| `engine/state.ts` | 轻量+ | 状态引擎 |
| `engine/dice.ts` 等 | 标准 | 按需 |
| `tools/registry.ts` | 轻量+ | 工具实现集中地（**不要内联到 extension.ts**） |
| `extension.ts` | 轻量+ | pi 入口，只做注册：注入 system prompt + 调用 `registerAllTools(pi)` + hooks。详见 `references/pi-integration.md` |
| `start.sh` | ✅ 必须 | 启动脚本，用户直接 `./start.sh` 进游戏。从 `tavern2agent/scripts/start.sh` 复制到项目根目录。**已内置 `PI_CODING_AGENT_DIR` 隔离**——首次运行自动初始化 `.pi/agent/` 并复制全局 auth，后续运行完全隔离全局扩展/skills |
| `.pi/settings.json` | 使用 pi 包时 ✅ | 项目级 pi 包清单。需要 `pi-subagents` / `pi-rewind-hook` 等扩展时写入 `packages`，发布时保留；`.pi/npm/` 不打包 |
| `data/world.json` | ✅ 必须 | 世界设定 |
| `data/characters.json` | ≥5 角色时 | 角色数据 |
| `data/user.json` | 需要 user 卡时 | 用户角色**固定档案**（运行时可变状态走 state.json，详见下方说明） |

> `user.json` 只放迁移阶段定型字段（姓名/性别/外貌/背景等），运行时不变；HP/好感度/装备等可变状态走 `INITIAL_STATE` + `state.json`，不要混进 `user.json`。

### 完工自检清单（向用户报告"完成"之前必须逐项对照）

**不要等用户提醒漏项。** 本清单只查**迁移完整性**（"该产的都产了吗？"）；**产出正确性**（"产的内容对吗？"）见 `references/validation.md` §人工检查清单——两份都得跑。

在你认为迁移完成、准备说「迁移完毕」之前，**主动**逐项核对：

- [ ] `first_mes` 已处理：改写后内联进开局 skill 的开场叙事参考，**ST 宏已按 setup.md §「改写时必须剥离的 ST 宏」逐项剥离/替换**
- [ ] **`alternate_greetings` 已处理**：每条都有去向（路线选项 / 合并 setup / 显式丢弃并说明原因）
- [ ] **所有世界书条目（含 disabled）都有去向**：按条目分类表落到 `data/*.json` / `engine/*.ts` / 开局可选开关 / 渐进披露逻辑 / 显式丢弃。disabled 条目须逐一判断是否为可选配置或 MVU 渐进披露，不能因「看起来不重要」就默认丢弃
- [ ] `start.sh` 已生成：从 `tavern2agent/scripts/start.sh` 复制到项目根目录，可执行权限已设
- [ ] `.pi/settings.json` 已生成（如用项目级 pi 包）：所有依赖的 pi 扩展写在 `packages`，例如 `npm:pi-subagents`、`npm:pi-rewind-hook`；不要要求玩家手动安装项目级扩展；`.pi/npm/` 不发布
- [ ] `.pi/agent/` 已在 start.sh 首次运行时自动初始化（首次启动会从全局复制 auth 并创建最小 settings.json）。如需手动干预：copy `~/.pi/agent/auth.json` → `.pi/agent/auth.json`，编辑 `.pi/agent/settings.json` 配置模型等
- [ ] `extension.ts` 已生成且只做注册：顶层 `import`（无动态 `import()`）、`registerAllTools(pi)` 被调用
- [ ] `tools/registry.ts` 不是死代码：extension.ts 真的引用了它
- [ ] 中间检查点已交付（标准方案）：state schema + engine 操作清单单独发给用户 review 过
- [ ] 第一层 grep 残留扫描通过
- [ ] 标准方案：`engine/attention.ts` 已覆盖所有"每 N 轮/条件触发"需求
- [ ] 标准方案：结构化数据集合（地点/NPC/DLC）已配查询工具 + 索引文件
- [ ] 项目根已是 git 仓库（`./start.sh` 兜底会跑 `git init`，但确认 `state/` **未**进 `.gitignore`——否则 pi-rewind-hook 等回退扩展会跳过游戏状态。详见 §五）
- [ ] 至少跑过 1 轮下场玩（第二层校验），观察 4 点全部 ✓

任何一项打不上 ✓，**继续做完再报告**，不要把"还差 X"作为收工话术。

---

## 六、回退 / 存档

**结论先行**：tavern2agent **不在 engine 内做回退**。死亡回溯、章节存档、撤销上一轮——一律外包给 pi 平台层的回退扩展。理由：state 能回滚但 chat 是 pi session jsonl 的 append-only 流，agent 删不掉自己已发的消息——半实现的回滚反而比明说做不到更糟。

### 推荐扩展：pi-rewind-hook

迁移产物应把推荐扩展声明在项目根 `.pi/settings.json`，让 pi 首次启动时自动安装到项目本地 `.pi/npm/`：

```json
{
  "packages": [
    "npm:pi-rewind-hook"
  ]
}
```

如果项目同时使用 subagent，把 `"npm:pi-subagents"` 也放进同一个 `packages` 数组。不要在交付说明里要求玩家手动安装项目级扩展；开发者可用 pi 的本地安装命令快速写入 `.pi/settings.json`，但发布物应直接包含这个文件。

用 pi 原生的 `/fork`（或 Tab 开 `/tree`）选目标轮 → "Restore all (files + conversation)"。rewind 元数据写进 session 自己的隐藏 ledger entry，能跨 fork / resume / compaction 存活。

### 项目侧约束（迁移产物必须满足）

1. **项目根必须是 git 仓库**——`start.sh` 内置 `git init` 兜底，但若用户在迁移产物外另做了改动，确认仍是 git repo
2. **`state/` 不能进 `.gitignore`**——否则游戏状态不入 snapshot，回退时数值不会跟着回去
3. **`sessions/` 可以 `.gitignore`**——chat 回滚走扩展自己的 ledger entries，不依赖 git
4. **不进 snapshot 的项**：`toolResult` 和 `bashExecution` 节点没有精确恢复点（影响小，玩家不会从工具调用中途切回）

### 跨回退持久的"永久记忆"

真死亡循环类机制（"你保留了上一周目的记忆"）需要一份**不被回退**的状态文件。模式：

- 在 `engine/state.ts` 里读写 `meta/persistent.json`
- 把 `meta/` 加进 `.gitignore`——pi-rewind-hook 只 snapshot tracked + 非 ignored untracked 文件，gitignored 路径会被跳过，刚好绕过回退
- 注册 `get_persistent` / `set_persistent` 工具供 GM 在死亡/周目切换时写入"记忆"标记

无此类机制的卡跳过。

### 备选方案

迁移产物本身**不依赖任何特定扩展**——换一个回退扩展只是 UX 差异：

| 扩展 | 入口 | 特点 |
|---|---|---|
| `npm:pi-rewind-hook` | `/fork` + `/tree` | 元数据进 session，跨 fork/compact 存活；推荐 |
| `arpagon/pi-rewind` | `/rewind` 命令 + 浏览器 | 命令式入口最直接 |
| `prateekmedia/pi-hooks` 的 Checkpoint 子模块 | 大包内统一交互 | 捆绑 LSP/Permission 等不相干模块 |

---

## 七、校验

### 第一层：grep 残留扫描

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留" || echo "✓"

# ST 宏残留（开局/GM prompt 里不允许出现 {{user}}/{{char}}/{{random}}/{{roll}} 字面量）
grep -rnE '\{\{(user|char|random|roll|pick|getvar|setvar)' \
  agents/ skills/ data/ 2>/dev/null && echo "↑ 有 ST 宏残留" || echo "✓"
```

### 第二层：下场玩（强烈推荐）

**你就是测试玩家。** 用 `./start.sh` 启动，以玩家身份逐轮交互——这是唯一能验证「GM 真的按规则运行了吗」的方法。

**最小可行流程**：

1. **想一个玩家角色**——姓名、背景、目标各一句话，能覆盖开局 skill 清单每一项
2. **跑至少 5 轮**：第 1 轮 `./start.sh -p "开始游戏"`；第 2 轮 `./start.sh --continue "回应"` 回答 setup；第 3-5 轮进入自由交互
3. **观察 4 点**：
   - 开局是否**一轮内列完所有缺失项 + 默认值**（违反："逐项追问"或"漏问关键字段"，详见 setup.md 的交互原则）
   - 开场叙事是否**含具体时空 + 情境**（"新的一天开始"算空洞，扣分）
   - **state 是否真的写入**（看 `state/state.json`，不是 GM 嘴上说"已记录"）
   - **裸数值不应出现在叙事里**（"粉丝+200" → 应该是「粉丝数量明显上涨」）
4. 如有 engine 模块：第 3-5 轮**主动触发一次**骰子/战斗/经济动作，确认工具被调用而非 LLM 脑补结果

完整玩法流程 + 工具调用验证命令 + 常见问题对照表见 `references/validation.md`。

### 第三层：人工核对

完整检查清单见 `references/validation.md`。

---

## references 索引

| 文档 | 适用方案 | 内容 |
|------|:---:|------|
| `design-principles.md` | 全部 | 设计原则（TS vs Python、一致性等） |
| `decision-tree.md` | 临界场景 | 方案档位辅助判定信号 + 归档样例 |
| `script-analysis.md` | MVU 卡 | tavern_helper 脚本 + regex_scripts 分类与迁移 |
| `mvu-mapping.md` | 轻量+ | MVU 条目 → engine 映射、initvar 读取、紧凑索引、条目分类完整表 |
| `setup.md` | 全部 | 开局 setup 分析、开局 skill 模板、平台集成 |
| `pi-integration.md` | 全部 | pi extension 集成（hook 时机、tool schema、subagent、工具 description 工程） |
| `ts-engine.md` | 标准 | TS 引擎代码（state.ts、dice.ts、attention.ts、工具注册模式） |
| `multi-agent-architecture.md` | NPC 隔离场景 | 多 agent 架构（GM + NPC subagent 上下文隔离，含适用场景速查） |
| `storytelling.md` | 全部（可选） | 叙事节拍参考 |
| `validation.md` | 全部 | 残留检测 + 人工检查清单 |
| `models/deepseek-v4.md` | V4 目标 | DeepSeek V4 特化：system 极简 + 规则入 user 流 + 全链路中文化 |

> **目标模型有特化指南时优先读 `references/models/<model>.md`**——它会覆盖一般规则（如 V4 把规则从 system 搬到 user message 流）。无对应文件时按 SKILL.md 主线即可。
