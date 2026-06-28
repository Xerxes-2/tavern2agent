# MVU / worldbook 映射

MVU 条目是卡作者写给 LLM 的系统设计文档。不要整块丢弃，也不要把输出格式原样搬到 pi。先区分「游戏语义」和「ST 补丁」，再把语义进入 Card Semantic IR。

## MVU 实情（先读，别想当然）

分析 MVU 卡前先校准心智模型，否则容易凭直觉编。MVU（MagVarUpdate）是独立酒馆助手脚本，**两层结构**：

1. **LLM 提议层**：AI 按 `[mvu_update]变量更新规则` 的 `check[]`（自然语言）决定改什么，在回复末尾吐 `<UpdateVariable>` 块，里面是 JSON Patch 风格命令（`replace`/`delta`/`insert`/`remove`/`move`）。这一步确实靠 LLM 自觉。
2. **代码兜底层（确定性，非 prose）**：MVU 解析命令后,依次过
   - `schema.ts` 的 zod `transform`：解析即施加软约束（clamp、上限、淘汰旧键）；
   - `COMMAND_PARSED` 钩子：改/补/删 LLM 提的命令（如修繁体、加命令）；
   - `VARIABLE_UPDATE_ENDED` 钩子：拿到更新前后变量，可 clamp、限幅、甚至**整个取消** AI 的更新；
   - 写回 `stat_data`。

数据存在楼层变量的 `stat_data`；初值来自 `[initvar]` + schema `.prefault`。

**反幻觉清单（实际审计中出现过的错误概括）：**

- ❌「MVU 全靠 LLM 自觉」→ 错。有 transform + 事件钩子两道确定性强制层。
- ❌「派生计算 = prose check[] 靠 LLM」→ 错。`check[]` 是**更新规则**（何时改/改多少），不是派生计算；派生值在**代码**里算（schema transform / 事件钩子 / 前端 store），不在 prose。
- ❌「数值是绝对赋值」→ 错。数值多用 `delta` 增量（相对值）。
- ❌「JSON Patch 有 add 算子」→ 错。算子是 replace/delta/insert/remove/move,无 add。
- ❌「`[mvu_plot]` 是 MVU 条目」→ 不存在。只有 `[initvar]` 和 `[mvu_update]`。
- 不确定 MVU 某行为时,**说「未确认」并去读卡内 schema.ts / 变量更新规则 / 事件脚本**,不要编。

移植到 pi 时,MVU 的「代码兜底层」正好对应 pi 的 reducer/engine——这是程度提升（把兜底变成唯一真相），不是「MVU 没有、pi 才有」。

**权威原文（按需 fetch 核实事实，别凭记忆概括 MVU）：**

- 框架 API / 事件 / `stat_data` 存储 / `parseMessage`：`https://github.com/StageDog/tavern_helper_template/raw/refs/heads/main/.cursor/rules/mvu变量框架.mdc`
- schema 契约（zod 4、幂等增量解析、transform 软约束）/ 世界书条目结构（`[initvar]`、`变量列表`、`[mvu_update]变量更新规则/变量输出格式`）：`https://github.com/StageDog/tavern_helper_template/raw/refs/heads/main/.cursor/rules/mvu角色卡.mdc`

守则:这是 ST **作者向**文档,**只用于核实 MVU 行为事实**,不是移植指令。其中 pnpm / pinia (`defineMvuDataStore`/`store.ts`) / 文件夹结构 / `registerMvuSchema` 等 ST 写法**别移植**(违背「提语义丢外壳」)。许可为 AFPL,只引用链接、不复制原文进本仓库。

## 审计流程

1. 建索引：列出所有世界书条目的 index、enabled、comment、keys、长度、前几行。
2. 逐条分类，含 disabled。
3. 只对需要的条目读取全文。
4. 抽取 mutable concept、mechanic、visibility fact、worldbook disposition。
5. 输出 `data/card-ir.json`，再从 IR 生成 Runtime Plan。

大卡不要 dump 全文进 context。

索引命令：

```bash
python3 scripts/list_entries.py card.json > index.md
```

读取单条：

```bash
python3 scripts/get_entry.py card.json <index>
```

## 条目分类

| 类型 | 信号 | IR / runtime 去向 |
|---|---|---|
| 系统规则/术语 | 常驻设定、规则说明 | settingFacts / `data/world.json` |
| 地区/场景 | 城市、区域、地点 | settingFacts / `data/locations.json` / lookup |
| NPC/角色模板 | `<character_card>`、角色名 | persona / `data/characters.json` / subagent |
| 章节剧情 | 第 X 卷、章节、事件模板 | quest mechanic / `data/chapters.json` / lookup |
| 初始状态 | `[initvar]`、YAML/JSON 初始值 | mutableConcept initial values |
| 更新规则 | `[mvu_update]`、变量变化 | mechanics + event pack candidates |
| 骰子/公式 | `{{roll}}`、DC、伤害、经济 | mechanic + reducer / CodeAct API |
| 路线/分支 | route、结局、alternate greeting 对应 | setup 选项 + quest/route data |
| disabled | 可选模块、DLC、渐进解锁、草稿 | 审后决定，不能默认丢 |
| ST 补丁 | COT、UpdateVariable、JSON Patch 格式、`__结束__` | 提取语义后丢外壳 |

## 状态来源顺序

1. TH Zod schema：字段、类型、约束。注意软约束（clamp、上限、淘汰旧键）多写在 `z.transform` 里，是 MVU 自带的约束层，不是「无约束」。
2. `[initvar]`：初始值主来源。但 schema 的 `.prefault(...)` 也会播种默认值，两者并存时以 initvar 显式值为准。
3. `[mvu_update]`：何时变化、变化规则。数值字段在 MVU 里多用 `delta` 增量更新（±N，相对值），不是绝对赋值——这正是它们要落成领域事件而非裸字段的根因。
4. regex / 状态栏：字段、展示和触发提示。
5. 没有前几者时，从自然语言规则反推。

用户创建字段通常不在 InitVar：姓名、性别、外貌、背景、开局选择。它们来自 `first_mes`、user 模板、start skill，也要进入 setup、actor state 或 fixed profile。

## 读 `[mvu_update]变量更新规则`

该条目是 yaml，每个变量带 `type` / `range` / `category` / `check[]`。这是机制金矿，逐项提取，别当普通字段：

- `check[]`：每条是「何时改、改多少、单次幅度上限」的自然语言规则 → 映射成 mechanic 的触发条件和 reducer 内的幅度约束（如「单次 ±不超过 10」「仅角色知情时才变」）。
- `range` / `category`：值域和分档 → 落成 reducer 校验或 schema clamp，不是展示文案。
- 名字以 `_` 开头的字段是只读 → 不生成更新通路。
- 抓到的规则进 IR 的 mechanic，再选 event pack；`check` 不能原样塞进 GM prompt 当输出格式。

## Mutable concept 映射

不要把变量名直接搬进 state。先命名领域概念，再选 event pack：

| ST 变量/状态栏 | Mutable concept | Event pack |
|---|---|---|
| 好感、信任、黑化、关系阶段 | relationship state | relationship |
| 金币、工资、债务、物价 | purse / transaction | economy |
| HP、SAN、伤口、异常 | condition / combat status | condition / combat |
| 背包、装备、关键物 | inventory item | inventory |
| 时间、地点、当前事件 | turn / scene beat | scene-turn |
| 任务、章节、路线 | quest progress | quest |
| 隐藏身份、凶手、秘密真相 | secret slot | secret |
| NPC 计划、阵营动作 | offscreen event | faction/offscreen |

每个 mutable concept 必须记录：初始值、触发规则、合法改变通路、可见性层级。

事件候选不只来自变量/状态栏：一次性不可逆拐点（初吻/背叛/跨线）与玩家不该看见的隐藏真相（怀疑、背叛决定、好感真值）即使无对应 MVU 字段，也映射成 one-way / secret / hidden 事件。MVU 是显示机制，表达不了隐藏真相。

## 轻量 vs 标准

方案分档主表见 `references/decision-tree.md`。本文只补三条：

- 条目只有 ST 输出格式：丢弃补丁，只保留语义。
- 已走 standard 时，相关状态规则尽量统一进 event packs，不要一部分 prompt 规则、一部分 engine。
- domain event 不限于 MVU：没有任何 MVU 的卡，若有不可逆拐点或隐藏真相，事件来源是开场一次性分支、`creator_notes` 秘密、阵营视角，而非变量表；是否进 evented 看「承重 + 可靠查询」，不看有没有 MVU。

## Data 映射

- 角色多：`data/characters.json`，GM prompt 只放一句话摘要。
- 地点多：`data/locations.json` + location index。
- 章节多：`data/chapters.json` + chapter lookup。
- DLC/路线：独立数据文件 + setup/state 开关。

大数据进 lookup，不进 prompt。

## State / event 映射

原则：

- `INITIAL_STATE` 预声明所有 canonical root。
- `engine/events.ts` 定义允许改变世界的领域事件。
- `engine/reducers.ts` 是状态变化唯一实现。
- MVU 的 JSON Patch 算子是 `replace`/`delta`/`insert`/`remove`/`move`（无 `add`，数值增量用 `delta`，新建路径用 `insert`）。`replace` 目标必须已存在；不要指望 GM 选对 insert/delta/replace。
- 顶层 root 白名单。
- 有规则的字段走领域事件/组合 API，禁止裸 patch。
- 派生值不落盘。

## ST 补丁处理

| 内容 | 处理 |
|---|---|
| 强化思考链/COT | 丢推理步骤；若夹带公式先提取 |
| JSON Patch/UpdateVariable 输出格式 | 丢；改成工具/CodeAct 提交领域事件 |
| EJS/条件模板 | 提取触发条件和内容，丢模板代码 |
| HTML 状态栏 | 提取字段，丢 UI |
| 角色强制输出格式 | 丢；GM 自行判断 |
| `__结束__` | 丢 |

## 常见坑

- disabled 不等于废弃。
- alternate greetings 往往是路线，不是可忽略开场。
- InitVar 不含用户创建字段。
- 大量章节不进 prompt。
- 大量角色不进 prompt。
- ST 宏不能原样出现在产物里。
- 好感、金钱、HP 等不是普通字段；它们必须有领域事件。
- hidden-canonical 不能因为在原卡 prompt 里出现就进入 public memory。
