# MVU 映射

MVU 条目是卡作者写给 LLM 的系统设计文档。不要整块丢弃；先区分“游戏逻辑”和“ST 补丁”。

## 审计流程

1. 建索引：列出所有世界书条目的 index、enabled、comment、keys、长度、前几行。
2. 逐条分类，含 disabled。
3. 只对需要的条目读取全文。
4. 给每条一个去向：data、state、engine/CodeAct、setup、渐进披露、丢弃。

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

| 类型 | 信号 | 去向 |
|---|---|---|
| 系统规则/术语 | 常驻设定、规则说明 | `data/world.json` |
| 地区/场景 | 城市、区域、地点 | `data/locations.json` / lookup |
| NPC/角色模板 | `<character_card>`、角色名 | `data/characters.json` / subagent |
| 章节剧情 | 第 X 卷、章节、事件模板 | `data/chapters.json` / lookup |
| 初始状态 | `[initvar]`、YAML/JSON 初始值 | `INITIAL_STATE` |
| 更新规则 | `[mvu_update]`、变量变化 | light 规则或 CodeAct API |
| 骰子/公式 | `{{roll}}`、DC、伤害、经济 | CodeAct / engine |
| 路线/分支 | route、结局、alternate greeting 对应 | setup 选项 + route data |
| disabled | 可选模块、DLC、渐进解锁、草稿 | 审后决定，不能默认丢 |
| ST 补丁 | COT、UpdateVariable、JSON Patch 格式、`__结束__` | 提取逻辑后丢外壳 |

## 状态来源顺序

1. TH Zod schema：字段、类型、约束。
2. `[initvar]`：初始值权威来源。
3. `[mvu_update]`：何时变化、变化规则。
4. 没有前两者时，从自然语言规则反推。

用户创建字段通常不在 InitVar：姓名、性别、外貌、背景、开局选择。它们来自 `first_mes`、user 模板、start skill，也要进入 state 或 fixed profile。

## 轻量 vs 标准

| 信号 | 档位 |
|---|---|
| 只有键值状态、±N、flag | light |
| 有骰子、伤害、经济公式、多字段联动、时间压缩 | standard / CodeAct |
| 只有 ST 输出格式 | 丢弃 |

如果已经走 standard，相关状态规则也尽量统一进 CodeAct，不要一部分 prompt 规则、一部分 engine。

## Data 映射

- 角色多：`data/characters.json`，GM prompt 只放一句话摘要。
- 地点多：`data/locations.json` + location index。
- 章节多：`data/chapters.json` + chapter lookup。
- DLC/路线：独立数据文件 + setup/state 开关。

## State 映射

原则：

- `INITIAL_STATE` 预声明所有可编辑路径。
- `replace` 目标必须存在；不要指望 GM 选对 add/replace。
- 顶层 root 白名单。
- 有规则的字段走专用函数/组合 API，禁止裸 patch。
- 派生值不落盘。

## ST 补丁处理

| 内容 | 处理 |
|---|---|
| 强化思考链/COT | 丢推理步骤；若夹带公式先提取 |
| JSON Patch/UpdateVariable 输出格式 | 丢；改成工具/CodeAct 写 state |
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
