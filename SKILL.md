---
name: tavern2agent
description: 用户提供 SillyTavern 角色卡（PNG/JSON）并要求转换、迁移、移植到 agent 平台（pi coding agent / Claude Code）时使用；覆盖纯角色卡、世界书、以及带骰子/战斗/好感度/经济等游戏系统的复杂卡。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tavern → Agent：角色卡迁移引擎

SillyTavern 的很多机制是绕过单次 LLM 调用限制的补丁。agent 天生能推理、调工具、自主决策。核心优势：agent 可以 loop（查询→掷骰→计算→更新→叙事）、自我纠正（算错了 dispatch 修正事件）、动态管理上下文（数据文件 + 查询工具）。

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

**大数据量卡片（条目 ≥100）**：脚本工具仅供探索阶段使用；构建阶段直接用 `python3 -c` 批量提取，避免几百次 `get_entry.py` 调用。样例：

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

# 或者批量按关键字索引正文
python3 -c "
import json
entries = json.load(open('card.json'))['data']['character_book']['entries']
for i,e in enumerate(entries):
    if '骰' in e['content'] or 'roll' in e['content'].lower():
        print(i, e['comment'][:60])
"
```

---

## 二、卡片分析

按顺序排查四个信息源，详情见对应 reference：

| 步骤 | 看什么 | 关键信号 | 详参 |
|------|--------|---------|------|
| 1 | `tavern_helper.scripts` | 有 Zod 脚本？有外链游戏脚本？ | `references/script-analysis.md` |
| 2 | `regex_scripts` | 有游戏内容注入（非纯 UI）？ | `references/script-analysis.md` |
| 3 | 世界书 `[initvar]` 条目 | 初始状态权威来源（YAML） | `references/mvu-mapping.md` |
| 4 | 世界书 `[mvu_update]`/`[mvu_plot]` 条目 | 骰子公式？伤害规则？变量定义？ | `references/mvu-mapping.md` |

**数据读取顺序**：Zod 脚本（模型）→ `[initvar]`（初始值）→ `[mvu_update]`（更新规则）。前两者都没有时从 MVU 条目自行提取。

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

**辅助判定信号**（综合考量，非硬性流程；矛盾时偏向上一档）：

- 决定走 prompt 还是带 state：`[mvu_update]` / `[mvu_plot]` 条目是否存在、`tavern_helper.scripts` 里有无 Zod 模型或游戏脚本。
- 决定轻量 vs 中等：是否出现骰子（`d20`/`roll`/`掷骰`）、战斗判定、伤害公式、好感度阈值、经济流通——任一明显存在即倾向中等。
- 决定中等 vs 完整 engine：卡片是否定义了"死亡回溯""读档重来""章节存档""撤销上一回合"等机制（搜 `revert`/`undo`/`restore`/`存档`/`回档`/`重来`）。仅有"剧情回忆"不算，要看是否影响 state。
- 临界情况：若状态键值 ≤10 且只有 1-2 处简单加减，倾向更轻一档；若 prompt 里反复强调"严格按公式""不许 LLM 自由发挥"，倾向更重一档。

---

## 四、实现要点

### 纯 prompt 方案

产出 `agents/gm.md`（角色+世界+规则，核心规则≤5条）+ `data/world.json` + `data/characters.json`（≥5角色时拆分）+ `data/chapters.json`（如有）。

开场白：生成 `skills/开局.md`。`first_mes` 在开局 skill 中由 agent 主动交付。详见 `references/setup.md`。

### 开局 skill（所有方案都必须生成）

每个卡片迁移**必须产出** `skills/开局.md`。模板和 checklist 生成规则见 `references/setup.md`。

### 轻量 / 中等方案

state 骨架代码见 `references/ts-engine.md`「轻量/中等方案」。中等方案加每轮快照（`snapshotBeforeTurn`），胶水层在每轮开始前调用。engine 模块按需写（`dice.ts`/`combat.ts`/`affection.ts`/`economy.ts` 等），识别信号见 `references/mvu-mapping.md`。

### 完整 engine 方案

事件溯源 + 多 agent，详见 `references/ts-engine.md` 和 `references/multi-agent-architecture.md`。

**中间检查点（中等+ 方案建议）**：在动手写 `engine/*.ts` 之前，先把 state schema（TS 类型或 JSON 例样）和事件清单（中等：操作清单；完整：事件名+payload）单独输出一份给用户 review。MVU 模型误读是后期返工最大的成本，前置确认比写完再改便宜得多。轻量方案可跳过。

### narrator.log 为什么是纯文本

`narrator.log` 是开场叙事的归档，给后续 agent 读上下文用——不是给前端渲染的产物。HTML/状态面板/`<thinking>` 标签会污染上下文窗口，让后续叙事 agent 误以为这些是"输出格式约定"。所以这里硬约束：只留人能读、模型能续写的纯散文。

---

## 五、产出清单

迁移完成后，确保以下文件齐全：

| 文件 | 必需？ | 说明 |
|------|:-----:|------|
| `skills/开局.md` | ✅ 必须 | 游戏入口 skill，处理 user 卡/配置/开场 |
| `agents/gm.md` | ✅ 必须 | GM system prompt |
| `agents/narrator.md` | 有游戏系统时 | 纯叙事 subagent |
| `engine/state.ts` | 轻量+ | 状态引擎 |
| `engine/dice.ts` 等 | 中等+ | 按需 |
| `tools/registry.ts` | 轻量+ | 工具注册 |
| `data/world.json` | ✅ 必须 | 世界设定 |
| `data/characters.json` | ≥5 角色时 | 角色数据 |
| `data/user.json` | 需要 user 卡时 | 用户角色 |
| `narrator.log` | ✅ 必须 | 开场叙事（纯文本，无 HTML/状态面板） |

## 六、校验

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留" || echo "✓"
```

完整检查清单见 `references/validation.md`。

---

## references 索引

| 文档 | 适用方案 | 内容 |
|------|:---:|------|
| `design-principles.md` | 全部 | 设计原则（TS vs Python、一致性等） |
| `script-analysis.md` | MVU 卡 | tavern_helper 脚本 + regex_scripts 分类与迁移 |
| `mvu-mapping.md` | 轻量+ | MVU 条目 → engine 映射、initvar 读取、直观示例 |
| `setup.md` | 全部 | 开局 setup 分析、开局 skill 模板、平台集成 |
| `platform-adapters.md` | 全部 | pi/CC 胶水层、MCP 示例 |
| `ts-engine.md` | 中等+ | TS 引擎代码（轻量 state、完整事件溯源、dice.ts） |
| `multi-agent-architecture.md` | 完整 | 多 agent 架构（GM + Narrator） |
| `storytelling.md` | 全部（可选） | 叙事节拍参考 |
| `validation.md` | 全部 | 残留检测 + 人工检查清单 |
