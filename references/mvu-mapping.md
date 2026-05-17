# MVU 条目 → Engine 模块映射详解

MVU 条目（`[mvu_update]` 和 `[mvu_plot]`）是卡片作者写给 LLM 的「系统设计文档」。
**不要当垃圾丢掉——它是你的设计文档。** 逐条用 `scripts/get_entry.py` 读取后自行判断。

> ⚠️ 关键区分：MVU 条目里**混着两类内容**——① ST 补丁（强化思考链、JSON Patch 格式、`__结束__` 标记等——丢弃）；② 真正的游戏系统设计（骰子公式、伤害计算、好感度规则、变量 schema ——这是你设计 engine 的蓝图）。**丢弃前先判断是否含游戏逻辑。**

## 探索阶段：紧凑索引

大数据量卡片（条目 ≥100）不要一次性 dump 所有条目（轻松 200K+ tokens）。先建紧凑索引（每条只留 `comment` + 前几行 + 长度，整张 5-10K tokens），再按需 lazy load 完整正文。

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

# 建紧凑索引（comment + 前 5 行预览，含 disabled 条目——先看到再决策）
python3 -c "
import json
entries = json.load(open('card.json'))['data']['character_book']['entries']
for i,e in enumerate(entries):
    disabled = '' if e.get('enabled', True) else ' ❌禁用'
    preview = '\n'.join(e['content'].splitlines()[:5])
    print(f'--- [{i}]{disabled} {e.get(\"comment\",\"\")} ({len(e[\"content\"])} chars) ---')
    print(preview)
    print()
" > index.md
```

## 条目分类决策完整表

SKILL.md §二只列了常见五类，以下是逐条审计用的完整表：

| 条目类型 | 判断信号 | 去向 |
|---------|---------|------|
| 系统规则 | `comment` 含「系统设定」/ `constant: true`（常驻） | `data/world.json` 对应 section |
| 地区/场景 | `comment` 含「地区设定」/ 城市名/区域名 | `data/regions.json` 或按需拆分 |
| 角色/NPC 模板 | `comment` 含 `<character_card>` / 角色名 | `data/characters.json` |
| 章节剧情 | `comment` 含「第X卷」「章节」 | `data/chapters.json` + 查询工具 |
| 术语表 | `comment` 含「术语」「黑话」 | `data/world.json` → `terminology` section |
| 骰子/伤害公式 | `content` 含 `{{roll:` / 伤害公式 / DC 分级 | `engine/dice.ts` 等 |
| 键值状态 | `comment` 含 `[initvar]` / `[mvu_update]` | `engine/state.ts` → `INITIAL_STATE` |
| 路线/分支专属 | `comment` 含路线名（如「NTR 路线」「真结局」）/ 仅在特定条件下 enabled | 与 `alternate_greetings` 联动：每条路线对应一个开局选项，路线专属设定挂到 `data/routes/<路线名>.json`，开局选定后按需注入 |
| ST 补丁 | `content` 含「强化思考」「JSON Patch」「`__结束__`」 | **丢弃** |
| disabled 条目 | `enabled: false` | **不可默认丢弃。** 分两类处理：<br>**开局可选**（玩家在 setup 里选开不开）→ 放入开局 skill 的选项列表，存入 state；例子：DLC 事件模块、可选同伴、难度调节<br>**MVU 渐进披露**（条件满足时自动触发）→ engine 里实现渐进启用逻辑；例子：变量更新规则、章节解锁<br>只有明确标注「废弃」「草稿」且无任何引用者才可丢弃 |

> 大数据量（≥100 条）用紧凑索引法（见上文「探索阶段：紧凑索引」），但分类决策这一步不能省。

## 变量结构的三类来源（读取顺序重要！）

| 来源 | 位置 | 提供什么 |
|------|------|---------|
| **变量结构脚本** | `tavern_helper.scripts` 中 kind=zod 的条目 | zod 4 schema：类型定义、字段约束、默认值、transform |
| **`[initvar]` 条目** | 世界书 entry，comment 含 `[initvar]` | YAML 格式初始值（**权威来源**） |
| **`[mvu_update]` 条目** | 世界书 entry，comment 含 `[mvu_update]` | 更新规则：何时变化、变化幅度、约束条件 |

**读取顺序**：先 Zod 脚本（数据模型）→ 再 `[initvar]`（初始值）→ 最后 `[mvu_update]`（更新规则）。没有 `[initvar]` 也没有 Zod 脚本时，自行从 `[mvu_update]` 描述中提取。

## 直观判断：三条 MVU 摘录 → 落点

同一张卡可能同时出现以下三类，帮助快速判断「这条进 prompt 还是进 engine」：

```
# A（来自 [mvu_update]）
好感度: 0       # 范围 -100~100
单次互动调整: ±5
```
→ 如果这是**唯一**游戏系统 → **轻量方案**。`INITIAL_STATE.好感度 = 0`；`gm.md` 写「友善互动后调 `patch_state` ±5」。不要写 `engine/affection.ts`。
→ 但如果这张卡**已经有骰子/战斗** → 好感度也应写成 engine 模块，一致性优先。

```
# B（来自 [mvu_plot]）
攻击判定: {{roll:1d20}} + 力量调整 vs 目标 AC
暴击: 自然 20 → 伤害 ×1.5
```
→ **完整 engine**。`engine/dice.ts`；GM prompt 只说「攻击时调 `skill_check`」。

```
# C（来自 [mvu_update]）
<强化思考要求> step1: 检查变量 step2: 认知隔离 ...
```
→ **丢弃**。酒馆补丁，agent 不需要。

## 三大去向

| 内容性质 | 去向 | 示例 |
|---------|------|------|
| **可计算的** | engine 模块 | 骰子公式、伤害计算、属性修正、经验值曲线 |
| **叙事指引** | GM prompt | 剧情推进规则、文风设定、并行事件 |
| **酒馆补丁** | 丢弃 | 强化思考链、JSON Patch 格式、UpdateVariable 标签、EJS 模板 |

## 常见内容 → engine 模块映射

只给识别信号和文件名。具体函数签名见 `ts-engine.md`，那是通用骨架示例——按本卡 schema 设计，不要照抄签名。

| 识别信号 | 模块 |
|---------|------|
| `{{roll:2d6}}`、属性检定、DC 分级 | `engine/dice.ts` |
| 伤害公式、HP/护甲、暴击 | `engine/combat.ts` |
| 好感度范围 + 增减规则 + 态度阈值 | `engine/affection.ts` |
| 收入公式、声望、等级经验曲线 | `engine/economy.ts`（按需拆分） |
| 死亡条件、回溯规则、存档点 | `engine/death.ts`（依赖事件溯源 state） |
| 任务生成 + 完成条件 + 章节推进 | `engine/quest.ts` |

## 轻量方案：MVU → INITIAL_STATE（不写 engine 模块）

如果 MVU 条目只描述**键值状态**（好感度、计数器、任务标记、地点/时间），**没有**骰子/伤害/经济公式：

1. **优先读取 `[initvar]` 条目**（如有）→ 这是卡片作者定义的实际初始值（YAML 格式），直接转化为 `INITIAL_STATE` 对象
2. 如果没有 `[initvar]`，退而求其次：`get_entry.py` 读所有 `[mvu_update]` 条目的 `content`，找到变量定义块（JSON / YAML / `name: 默认值` 列表均可）
3. 直接拷成 SKILL.md「轻量方案」中 `INITIAL_STATE` 的字面量。**不要**生成 dice.ts/combat.ts/economy.ts——那些条目本身就不该存在
4. 对 MVU 里描述「何时变化」的自然语言（如「每次帮助 +5」），**不要**翻译成代码——写成 GM prompt 里的一行规则，让 agent 自己判断后调 `patch_state`

判断边界：条目里出现 `{{roll:...}}`、伤害公式、阈值分级（DC/暴击/经验曲线）→ 升级到完整 engine 方案；只有「±N」「设为 X」→ 留在轻量方案。

> **一致性原则**：如果卡片已有骰子/战斗系统（即走了完整 engine），那么好感度也应写成 engine 模块——不要部分系统在 engine、部分在 prompt 规则。agent 面对统一工具接口比混合接口更可靠。

## 角色数据：MVU 条目 → data/characters.json

当世界书包含多条 `<character_card>` 条目（部分卡可能有几十张角色卡）时：

1. 不要把所有角色描述塞进 GM prompt——每轮注入会炸 token
2. 提取到 `data/characters.json`，结构为 `{ "角色名": { "性别", "种族", "外貌", "性格", "背景", "说话特点" } }`
3. GM prompt 只列角色名 + 一句话摘要（如「林老师：30 岁人类法师，魔法学院教师」）
4. 注册一个 NPC 详情查询工具让 GM 按需加载角色详情

## 章节剧情模板：按需加载

部分卡片包含数十至数百条章节剧情模板（如 `第十五卷:终章:…`）。这些是 GM 推动剧情的参考资料：
- **不要**全量预注入 prompt 或 engine（token 不可承受）
- 提取所有章节到 `data/chapters.json`，按「卷章标题」索引
- 注册一个章节查询工具，GM 在需要推进剧情时**按需加载当前章节**
- 工具实现：根据章节标题（或序号）从 `data/chapters.json` 读取对应条目，返回给 GM

## 变量定义 → engine/state.ts（完整 engine 方案）

MVU 条目中的 JSON Schema 或变量列表是**初始状态的蓝图**。

### 提取方法
1. **优先用 `get_entry.py` 读 `[initvar]` 条目** → YAML 格式的初始值，直接转为 `initialBlankState()` 返回值
2. 如果没有 `[initvar]`：用 `get_entry.py` 读 MVU 条目，找到变量定义块（通常是 JSON 或 YAML 结构）
3. 转化为 `initialBlankState()` 函数返回的对象

### ⚠️ 常见遗漏：用户卡字段不在 InitVar 里

InitVar 定义的是**运行时变量**（等级、经验、背包、好感度），不包含**角色创建字段**（姓名、性别、年龄、外貌、背景）。这些字段来自：
- `first_mes` 的 setup 交互（「你的名字是？」）
- user 卡模板（`data/user.json`，**固定档案**——迁移阶段定型，运行时不变）
- 开局 skill 的 checklist

**两类字段都必须在 INITIAL_STATE 中显式声明（默认空字符串或占位值），否则 patch_state 的 `replace` 操作会因 RFC 6902 约束而静默失败。** `data/user.json` 只是固定档案的来源/快照，运行时可变状态一律走 state.json。

### ⚠️ RFC 6902 陷阱：replace 要求路径已存在

`patchState` 使用 `rfc6902` 库的 `applyPatch`。**`replace` 操作的目标路径必须已存在于状态对象中，否则操作静默失败（不抛错，但值不会写入）。** `add` 可以创建新路径，但依赖 GM 正确选择 op 类型。

**防御措施**：INITIAL_STATE 中为所有已知可编辑字段预声明默认值，让 `replace` 始终可用。

### 常见模式

**简单键值对**：
```
好感度: 0
时间: "上午 10:00"
地点: "学院正门"
```
→ 直接转为对象。

**嵌套结构**：
```json
{
  "主角": {
    "姓名": "待初始化",
    "生命值": { "当前值": 10, "最大值": 10 },
    "属性列表": { "力量": 10, "敏捷": 10 }
  },
  "关系列表": {},
  "时间": { "年月日": "", "时间": "" }
}
```
→ `initialBlankState()` 返回完整嵌套对象。

**变更约束**：
```
单回合变化限制: "所有数值型变量单回合变化绝对值不得超过 15 点"
```
→ 写成 `dispatch()` 的校验逻辑。

## 必须丢弃的内容

### 强化思考链 (COT)
```
<强化思考要求>
step1: 我是否已经知道了当前变量内容。
step2: 我是否已经进行认知隔离。
...
```
→ agent 自己会推理。**但先确认条目中是否包含被 COT 包裹的游戏逻辑**——如果 COT 的 step 中混入了伤害公式或骰子规则，先提取公式再丢弃 COT 外壳。纯推理步骤才整体丢弃。

### JSON Patch / UpdateVariable 输出格式
```
<变量修改格式>
rule: you must output the update analysis and the actual update commands at once
the update commands works like the JSON Patch (RFC 6902) standard
```
→ agent 调工具 dispatch 事件。丢弃。

### EJS 条件模板
```
<%_ if (getvar('月宫绾音.拥有联系方式') == true) { _%>
线上聊天气泡: ...
<%_ } _%>
```
→ 这是酒馆的条件注入逻辑。提取条件描述（如「当用户拥有联系方式时显示聊天气泡」），**丢弃模板代码**。

### 角色强制输出格式
```
<角色登场>
请必须在下一次剧情开始之前输出下一次剧情要出现的主要角色。
<出场角色> 林老师,小白 </出场角色>
```
→ agent 自己判断何时引入角色。丢弃。

### `__结束__` 标记
→ 酒馆用来分隔剧情和变量更新的标记。丢弃。
