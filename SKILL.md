---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 pi coding agent 时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策。核心优势：agent 可以 loop（查询→掷骰→计算→更新→叙事）、自我纠正（算错了重新发事件修正）、动态管理上下文（数据文件 + 查询工具）。

目标平台是 pi coding agent，详见 `references/platform-adapters.md`。

**能力边界**：本 skill 只产出**文字交互**的 agent。前端面板/状态条 HTML、文生图（SD/NAI/ComfyUI）提示词、预设与上下文模板等一律剥离或丢弃——不是做不到，而是这些大多是 ST 运行时补丁，agent 不需要，强行复刻反而锁死灵活性。需要的人转换完成后自行接入。

---

## 〇、开工前确认

1. **先读 `references/design-principles.md`**——七条核心原则（agent 是程序本身、所有计算进引擎、prompt 极简、砍掉强化思考链等）决定了产出的形态，不读会写出"翻译 ST 咒语"风格的代码。
2. **确认输出目录**：用户如果说「输出到 xxx 目录」「放到 cards/ 下」，直接照做。如果用户只说「转换这张卡」没指定路径，主动问一句：「输出到哪个目录？目录名用卡片名还是自定义？」用户没指定命名规则时，默认取卡片 `data.name` 作为目录名（非法字符替换为下划线），放在卡片 PNG 同级目录下。
3. **检查工作目录**：如果目标目录已存在 `agents/`、`engine/`、`skills/start-game/SKILL.md` 等，先和用户确认是覆盖、增量更新、还是另开目录。用户没明说时直接问一句。

---

## 一、快速开始

```bash
python3 scripts/extract_png.py <角色卡.png> card.json   # PNG 解包
python3 scripts/list_entries.py card.json --filter mvu     # 看 MVU 条目
python3 scripts/list_entries.py card.json --filter initvar # 看初始值
```

| 脚本 | 用途 |
|------|------|
| `extract_png.py <png> [out.json]` | PNG → JSON |
| `list_entries.py <json> [--filter mvu\|initvar]` | 世界书条目概览 |
| `get_entry.py <json> <索引>` | 读条目完整内容 |

> **支持 v2 / v3 卡**：JSON 顶层 `spec` 为 `chara_card_v2` 或 `chara_card_v3`，且 `data.character_book` 存在即可。v3 新增字段（`assets` / `group_only_greetings` / `creator_notes_multilingual` / `source` 等）当前不专门处理：`group_only_greetings` 与 `alternate_greetings` 同等对待（路线选项 / 合并 setup），其余视为元数据忽略。v1 老卡（字段直接挂在顶层、无 `data` 包装）请先用 SillyTavern 或第三方工具升级到 v2/v3 再迁移。

**大数据量卡片（条目 ≥100）**：脚本工具仅供探索阶段使用；构建阶段直接用 `python3 -c` 批量提取，避免几百次 `get_entry.py` 调用。

**提取策略**：先建紧凑索引（每条只留 `comment` + 前几行 + 长度，整张 5-10K tokens），再按需 lazy load 完整正文。不要一次性 dump 所有条目（轻松 200K+ tokens）。样例：

```bash
# 一次性提取所有 [mvu_update] 条目正文到独立文件
python3 -c "
import json, pathlib, re
card = json.load(open('card.json'))
entries = card['data']['character_book']['entries']
out = pathlib.Path('mvu_dump'); out.mkdir(exist_ok=True)
for e in entries:
    if '[mvu_update]' in e.get('comment',''):
        name = re.sub(r'[^\w-]','_', e['comment'])[:80]
        (out / f'{name}.md').write_text(e['content'])
print(f'dumped {len(list(out.iterdir()))} entries')
"

# 建紧凑索引（comment + 前 5 行预览）
python3 -c "
import json
entries = json.load(open('card.json'))['data']['character_book']['entries']
for i,e in enumerate(entries):
    if not e.get('enabled', True): continue
    preview = '\n'.join(e['content'].splitlines()[:5])
    print(f'--- [{i}] {e.get(\"comment\",\"\")} ({len(e[\"content\"])} chars) ---')
    print(preview)
    print()
" > index.md
```

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

得到完整条目清单后，**逐条分类决策去向**——不要跳到「条目 0 看起来够了」就收工：

| 条目类型 | 判断信号 | 去向 |
|---------|---------|------|
| 系统规则 | `comment` 含「系统设定」/ `constant: true`（常驻） | `data/world.json` 对应 section |
| 地区/场景 | `comment` 含「地区设定」/ 城市名/区域名 | `data/regions.json` 或按需拆分 |
| 角色/NPC 模板 | `comment` 含 `<character_card>` / 角色名 | `data/characters.json` |
| 章节剧情 | `comment` 含「第X卷」「章节」 | `data/chapters.json` + 查询工具 |
| 术语表 | `comment` 含「术语」「黑话」 | `data/world.json` → `terminology` section |
| 骰子/伤害公式 | `content` 含 `{{roll:` / 伤害公式 / DC 分级 | `engine/dice.ts` 等 |
| 键值状态 | `comment` 含 `[initvar]` / `[mvu_update]` | `engine/state.ts` → `initialState()` |
| 路线/分支专属 | `comment` 含路线名（如「NTR 路线」「真结局」）/ 仅在特定条件下 enabled | 与 `alternate_greetings` 联动：每条路线对应一个开局选项，路线专属设定挂到 `data/routes/<路线名>.json`，开局选定后按需注入 |
| ST 补丁 | `content` 含「强化思考」「JSON Patch」「`__结束__`」 | **丢弃** |

**做完这一步再决定方案档位**——条目数量决定了 world.json 的规模：纯地理念卡 world.json ≤5KB 合理；大量常驻系统条目的卡，world.json 自然 20-30KB。

> 大数据量（≥100 条）用紧凑索引法（见上文「提取策略」），但分类决策这一步不能省。

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
| 只有键值状态，无骰子/公式 | **轻量** | `patchState` | 上者 + `engine/state.ts` + `get_status`/`update_status` 工具 |
| 有骰子/战斗/经济，不需一轮内精确回退 | **中等** | `patchState` + 每轮快照 | 上者 + `engine/dice.ts` 等模块 |
| 需死亡回溯/章节存档/事件级回退 | **完整 engine** | `dispatch(event)` | 事件溯源 + 全套模块 + 多 agent |

### 多 agent 判定（独立维度，不跟 engine 档位绑定）

多 agent 的核心用途是 **认知隔离**——任何"某个视角不该看到的信息"都可以拆进独立 context。NPC 秘密只是最常见的一种：模型在单一 context 里读到 NPC A 的秘密，就会让 NPC B 做出不该有的反应。但隔离对象不限于 NPC——悬疑/侦探题材里凶手身份、未揭晓的真相、玩家尚未推理出的线索，都该挡在主 context 之外，否则 GM 会"剧透式叙事"。GM 仍是主叙事者，subagent 只负责自己那块被隔离的视角。

**多 agent 的决策跟 game engine 复杂度无关**。一张无骰子的纯 prompt 卡，只要存在认知隔离需求（NPC 秘密、信息不对等、隐藏真相），就该走多 agent。

| 触发信号 | 行动 |
|----------|------|
| NPC ≤4 且无隐藏信息、无隐藏剧情 | 单 agent（GM 自己扮演所有 NPC） |
| NPC ≥5 且有隐藏信息/秘密/阵营 | 多 agent：每个有秘密的 NPC 独立 subagent，GM 织入叙事 |
| 视角间信息不对等（NPC 之间、PC 之间，或 GM 不该看到的真相）| 多 agent——这正是认知隔离的核心价值 |
| 悬疑/侦探等"答案不能泄漏给叙事者"的题材 | 多 agent：真相/凶手视角独立 context，主 GM 只拿到该揭晓的部分 |

### subagent 适用场景速查

判断标准：**该角色不该看到的东西**（信息隔离）、**跟 GM 完全不同的人格/文风**（角色分离）、**适合异步/并行**（进程隔离）。三者至少占一个才用。

| 类别 | 适用 | 不适用（反模式） |
|------|------|-----------------|
| 信息隔离 | NPC 秘密、PC 信息不对等、GM 隐藏剧情 | 单 agent 能靠 prompt 约束的信息边界 |
| 角色分离 | 反派 AI（和 GM 人格冲突）、吟游诗人/旁白（不同文风）、队友 AI | 普通 NPC 扮演（GM 自己就能演） |
| 进程隔离 | 战斗结算器（确定性）、经济模拟（异步）、章节存档校验 | 简单规则引擎、状态存储、频繁轻量操作 |
| 并行天然适合 | 多地点同时叙事、多 NPC 同时反应 | 单线程场景拆成并行是徒增复杂度 |

详见 `references/multi-agent-architecture.md`。

**辅助判定信号**（综合考量，非硬性流程；矛盾时偏向上一档）：

- `[mvu_update]`/`[mvu_plot]` 条目或 `tavern_helper.scripts` 里的 Zod 模型——存在则走带 state 方案。
- 骰子（`d20`/`roll`/`掷骰`）、战斗判定、伤害公式、好感度阈值、经济流通——任一明显存在即倾向中等。
- 死亡回溯/读档/章节存档/撤销上一回合（搜 `revert`/`undo`/`restore`/`存档`/`回档`/`重来`，且影响 state）——倾向完整 engine。"剧情回忆"不算。
- 临界：状态键值 ≤10 且只有 1-2 处简单加减，偏轻一档；prompt 反复强调"严格按公式""不许 LLM 自由发挥"，偏重一档。
- 非 MVU 状态系统（极少数卡在 `tavern_helper.scripts` 里自定义变量）：按语义手工映射到等价档位，不单开方案。

**归档样例**（拿到具体卡时按这种粒度落档，不要纠结临界条款的字面）：

| 卡片特征 | 落档 | 理由 |
|---------|------|------|
| 纯地理/势力设定 + 几个 NPC 模板，无变量、无骰子 | 纯 prompt | 没有状态需要维护，data/ 够用 |
| `first_mes` 末尾有"选难度/选阵营"问句，但游戏本身无系统 | 纯 prompt + 开局 skill 收 setup | 选项落到开局 skill 而非 engine |
| 30+ 键值状态（好感度、日期、地点），但变化全是 ±1/±5 这类直接加减 | 轻量 | `patchState` 够用，不需要事件溯源 |
| 有 `{{roll:1d6}}` 偶尔用于占卜，其余推进靠 prompt | 轻量 | 1-2 次偶发掷骰直接写进 GM 规则，不值得开 `dice.ts` |
| 有伤害公式 + 装备护甲 + 命中检定，但允许玩家"接受这一击就过" | 中等 | 战斗逻辑进 engine，无需事件溯源式回退 |
| 死亡循环叙事性出现（"你回想起上次失败时…"），但不真回退 state | 中等 | 是叙事手法不是机制，事件溯源是 over-engineering |
| 真死亡回溯：死后变量回到上次存档点、保留"记忆"标记 | 完整 engine | 唯一站得住脚的事件溯源用例 |
| 多结局章节存档，玩家可读档到任一章节起点 | 完整 engine | 同上 |

---

## 四、实现要点

### 纯 prompt 方案

产出 `agents/gm.md`（角色+世界+规则，核心规则≤5条）+ `data/world.json` + `data/characters.json`（≥5角色时拆分）+ `data/chapters.json`（如有）。

开场白：所有方案都必须生成开局 skill（`skills/<skill-name>/SKILL.md`），`first_mes` 改写后内联其中、由 agent 在开局时主动交付。**技能名必须 ASCII（a-z/0-9/-）且与目录名一致**，推荐 `skills/start-game/SKILL.md`。模板和 checklist 生成规则详见 `references/setup.md`。

### 轻量 / 中等方案

state 骨架代码见 `references/ts-engine.md`「轻量/中等方案」。中等方案加每轮快照（`snapshotBeforeTurn`），胶水层在每轮开始前调用。engine 模块按需写（`dice.ts`/`combat.ts`/`affection.ts`/`economy.ts` 等），识别信号见 `references/mvu-mapping.md`。

### 完整 engine 方案

事件溯源，详见 `references/ts-engine.md`。如果同时触发多 agent 条件（见上文），则叠加多 agent 架构，详见 `references/multi-agent-architecture.md`。

### 中间检查点（中等+ 方案必走）

在动手写 `engine/*.ts` 之前，**先把以下两份输出单独发给用户 review**：

1. **state schema**——TS interface 或 JSON 示例，列出所有字段及其类型/初值
2. **事件清单**——中等方案给操作列表（`update_status`、`snapshot`、`rollback` 等）；完整方案给事件名 + payload（`set` / `delta` / `death_rewind` 等）

MVU 模型误读是后期返工最大的成本，前置 5 分钟对齐比写完一整套 engine 再改便宜得多。轻量方案 schema 通常一眼能看完，可跳过此步。

---

## 五、产出清单

迁移完成后，确保以下文件齐全：

| 文件 | 必需？ | 说明 |
|------|:-----:|------|
| `skills/<skill-name>/SKILL.md` | ✅ 必须 | 游戏入口 skill（如 `skills/start-game/SKILL.md`），处理 user 卡/配置/开场 |
| `agents/gm.md` | ✅ 必须 | GM system prompt |
| `agents/<npc_xxx>.md` | NPC≥5 且有隐藏信息 | NPC subagent（每 NPC 一个，上下文隔离） |
| `engine/state.ts` | 轻量+ | 状态引擎 |
| `engine/dice.ts` 等 | 中等+ | 按需 |
| `tools/registry.ts` | 轻量+ | 工具实现集中地（**不要内联到 extension.ts**） |
| `extension.ts` | 轻量+ | pi 入口，只做注册：注入 system prompt + 调用 `registerAllTools(pi)` + hooks。详见 `references/platform-adapters.md` |
| `data/world.json` | ✅ 必须 | 世界设定 |
| `data/characters.json` | ≥5 角色时 | 角色数据 |
| `data/user.json` | 需要 user 卡时 | 用户角色 |

### 完工自检清单（向用户报告"完成"之前必须逐项对照）

**不要等用户提醒漏项。** 在你认为迁移完成、准备说「迁移完毕」之前，**主动**逐项核对：

- [ ] `first_mes` 已处理：改写后内联进开局 skill 的开场叙事参考，**ST 宏（`{{user}}`/`{{char}}`/`{{random}}`/`{{roll}}` 等）已剥离/替换**（详见 setup.md「改写时必须剥离的 ST 宏」）
- [ ] **`alternate_greetings` 已处理**：每条都有去向（路线选项 / 合并 setup / 显式丢弃并说明原因）
- [ ] **所有 `enabled: true` 的世界书条目都有去向**：按条目分类表落到 `data/*.json` / `engine/*.ts` / 显式丢弃。**不允许"看起来不重要就跳过"**
- [ ] `extension.ts` 已生成且只做注册：顶层 `import`（无动态 `import()`）、`registerAllTools(pi)` 被调用
- [ ] `tools/registry.ts` 不是死代码：extension.ts 真的引用了它
- [ ] 中间检查点已交付（中等+ 方案）：state schema + 事件清单单独发给用户 review 过
- [ ] 第一层 grep 残留扫描通过
- [ ] 至少跑过 1 轮下场玩（第二层校验），观察 4 点全部 ✓

任何一项打不上 ✓，**继续做完再报告**，不要把"还差 X"作为收工话术。

---

## 六、校验

### 第一层：grep 残留扫描

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留" || echo "✓"

# ST 宏残留（开局/GM prompt 里不允许出现 {{user}}/{{char}}/{{random}}/{{roll}} 字面量）
grep -rnE '\{\{(user|char|random|roll|pick|getvar|setvar)' \
  agents/ skills/ data/ 2>/dev/null && echo "↑ 有 ST 宏残留" || echo "✓"
```

### 第二层：下场玩（强烈推荐）

**你就是测试玩家。** 用 SDK 创建 GM session，以玩家身份逐轮交互——这是唯一能验证「GM 真的按规则运行了吗」的方法。

**最小可行流程**：

1. **想一个玩家角色**——姓名、背景、目标各一句话，能覆盖开局 skill 清单每一项
2. **跑至少 5 轮**：第 1 轮发「开始游戏」触发开局；第 2 轮回答 setup（或直接说「开始」用默认）；第 3-5 轮进入自由交互
3. **观察 4 点**：
   - 开局是否**一轮内列完所有缺失项 + 默认值**（违反："逐项追问"或"漏问关键字段"，详见 setup.md 的交互原则）
   - 开场叙事是否**含具体时空 + 情境**（"新的一天开始"算空洞，扣分）
   - **state 是否真的写入**（看工具调用日志或 `state/state.json`，不是 GM 嘴上说"已记录"）
   - **裸数值不应出现在叙事里**（"粉丝+200" → 应该是「粉丝数量明显上涨」）
4. 如有 engine 模块：第 3-5 轮**主动触发一次**骰子/战斗/经济动作，确认工具被调用而非 LLM 脑补结果

完整 SDK 代码骨架 + 常见问题对照表见 `references/validation.md`。

### 第三层：人工核对

完整检查清单见 `references/validation.md`。

---

## references 索引

| 文档 | 适用方案 | 内容 |
|------|:---:|------|
| `design-principles.md` | 全部 | 设计原则（TS vs Python、一致性等） |
| `script-analysis.md` | MVU 卡 | tavern_helper 脚本 + regex_scripts 分类与迁移 |
| `mvu-mapping.md` | 轻量+ | MVU 条目 → engine 映射、initvar 读取、直观示例 |
| `setup.md` | 全部 | 开局 setup 分析、开局 skill 模板、平台集成 |
| `platform-adapters.md` | 全部 | pi 胶水层 |
| `ts-engine.md` | 中等+ | TS 引擎代码（轻量 state、完整事件溯源、dice.ts） |
| `multi-agent-architecture.md` | NPC 隔离场景 | 多 agent 架构（GM + NPC subagent 上下文隔离，含适用场景速查） |
| `storytelling.md` | 全部（可选） | 叙事节拍参考 |
| `validation.md` | 全部 | 残留检测 + 人工检查清单 |
