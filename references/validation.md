# 产出校验

## 残留检测

跑 SKILL.md §六「第一层：grep 残留扫描」的两条 grep——一条扫 ST 补丁残留（`UpdateVariable` / `JSON Patch` / `{{getvar:}}` 等），一条扫 ST 宏字面量（`{{user}}` / `{{char}}` / `{{random}}` / `{{roll}}` 等）。

> 命中范围仅限 ST 补丁与宏。游戏字段如 `生命值`、`魔法值`、`好感度`、`回溯次数` 等是合法的运行时状态，不在残留检测范围内。ST 宏的逐项剥离规则见 `setup.md` §「改写时必须剥离的 ST 宏」。

## 人工检查清单

本清单查**产出正确性**（"产的内容对吗？"）；**迁移完整性**（"该产的都产了吗？"）见 SKILL.md §五完工自检清单——两份都得跑。

- [ ] `agents/gm.md` 核心规则 ≤5 条
- [ ] 如走多 agent，每个隔离 NPC 有独立 `agents/npc_*.md` 且 `tools:` 为空
- [ ] engine 模块覆盖 MVU 计算规则
- [ ] state schema 与 MVU 变量定义一致
- [ ] 角色数据按需拆分到 `data/characters.json`（≥5 个角色时）
- [ ] `first_mes` 的 HTML/状态面板已剥离，纯叙事（或合成叙事）内联到开局 skill
- [ ] 开局 skill 已生成（`skills/<name>/SKILL.md`），且正确反映 user 卡/设置需求
- [ ] 需要 user 卡时 `data/user.json` 已生成（含已知字段，缺失字段标注 `"TODO"`）
- [ ] `[initvar]` 已被读取并转化为 `INITIAL_STATE`（如有）
- [ ] `tavern_helper.scripts` 中 Zod 脚本已被提取（如有）
- [ ] `tavern_helper.scripts` 中游戏系统脚本已被处理（如有）
- [ ] `regex_scripts` 中的游戏数据已被提取（如有）
- [ ] 章节剧情模板未全量注入 prompt（如有）

---

# 下场实测

grep 和人工清单只能验证"文件是否存在、是否残留 ST 痕迹"，回答不了核心问题：**GM 真的会按开局 skill 逐项收集角色信息吗？工具调用链路通不通？state 是否正确写入？**

答案是：**你（pi agent）下场玩。** 在 bash 里跑 pi CLI 启动 GM，逐轮读 GM 输出、按一个具体玩家人设生成回应、再发送下一条——像真人那样判断 GM 措辞/数值/跳问，而不是和预设 checklist 逐条对标。

## 怎么做

### 1. 开局

```bash
cd 项目目录
pi --session-dir ./sessions -e ./extension.ts -p "开始游戏"
```

用 `-p`（print mode）发送第一条消息，`--session-dir` 保证会话留在项目里。

### 2. 逐轮继续

```bash
pi --session-dir ./sessions -e ./extension.ts --continue "你的回应"
```

每轮：读完 GM 的终端输出 → 想好回应 → 用 `--continue` 发送。像真人一样——问什么答什么，想探索就探索，想打架就拔刀。让 GM 措辞变化时也能跟上，而不是按固定 checklist 逐条对标。

### 3. 想一个玩家角色

开局前想好姓名、背景、目标——能覆盖开局 skill 清单里的每一项。不需要完美，但要像真人：有偏好、会犹豫、偶尔冲动。

### 4. 边玩边观察

玩的过程中注意：
- 开局是否**一轮内列完所有缺失项**并附默认值——逐项追问是 bug
- 开场叙事是否含时间/地点/具体情境（"新的一天开始"算空洞）
- 价格/地点/NPC 的描述是否前后一致——不一致说明读取工具没被调
- 战斗中是否有判定过程——一刀秒杀没掷骰是跳过了 combat_attack
- 至少玩到自由交互 3-5 轮再收工

### 5. 检查 state 和工具调用

玩完后，核实 state 是否真的被写入（不是 GM 嘴上说"已记录"）：

```bash
# 看关键字段（字段路径按本卡 state schema 替换 — 下面示例假设 state 顶层有「主角」「关系列表」）
python3 -c "
import json
s = json.load(open('state/state.json'))
print(json.dumps(s, indent=2, ensure_ascii=False)[:2000])
"

# 统计工具调用次数（pi 把每个会话写为 sessions/<id>.jsonl，ls -t | head -1 取最新一个）
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"combat_attack"'
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"get_price"'
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"lookup_location"'
```

如果战斗叙事很精彩但 `combat_attack` 调用次数为 0——说明 GM 在即兴创作，工具根本没被调。需要强化工具 description（详见 `references/platform-adapters.md` §「工具 description 工程」）。

### 6. 时间、token 成本与玩家 agent 的优势

一次完整测试跑 15-30 轮大概需要 20-40 分钟，消耗几十万 token——这是目前最可靠的同时验证叙事质量、工具链路、状态一致性的方法。grep 和人工清单只能查出文件缺失和 ST 残留，查不出"GM 有没有真的掷骰"。

**玩家 agent 的 token 成本可以忽略**：GM 输出的 token 真人测试也得花（一样要让 GM 跑完）；玩家 agent 额外只多花自己回应那几百到几千 token，相对完整验证的收益微不足道。

**玩家 agent 不是"次于真人"的妥协方案，在关键维度上比真人更强**：

- **信息位置和真人玩家同等**——玩家 agent 看不到 GM 的 system prompt、看不到 `data/`、看不到 engine 内部，只知道自己构造的人设 + GM 在对话里告诉它的。它**字面意义上不知道**正确答案，所以自然在测「GM 该泄漏的信息泄漏了吗 / 该藏的藏住了吗」
- **上下文小 = 注意力不被稀释**——玩家 agent 的 context 只有自己的对话历史（20-30 轮 = short context），不会"忘了五轮前 GM 报过的价格"这种真人玩家容易漏掉的细节。前后一致性、token 级别的措辞偏差，它都能当场抓出来
- **持久力强**——20-40 分钟不疲劳、不分心、不会"算了就这样吧"地放过 GM 的小瑕疵
- **会主动求证**——玩家 agent 是个 coding agent，怀疑 GM 报的数值/描述不对时会**真的去对账**：`cat state/state.json` 核对数值、翻自己对话历史对账（"开局 100 金、买剑 30、现在该 70，GM 说 50 → 报 bug"）、`grep` world.json 验证地点描述没编。真人玩家进入沉浸模式就懒得回查（也不该被要求一边玩一边开 terminal 对账），但 agent 玩家本来就在测试，不存在打断沉浸的成本

真人玩家相对仍有的优势主要是 **adversarial probing**（刻意刁难、找逻辑漏洞）和 **直觉式语感**（"这句话像 AI 写的"那种判断）。前者通过 spot check 实时插话补（「问他这个问题」「试试逻辑漏洞 X」）；后者是体验测试的范畴，不是验证迁移正确性的瓶颈。

### 7. 人类 spot check（推荐）

人类不需要从头盯到尾，两种介入方式可组合：

**实时插话**：用户在 agent 测试运行中随时打断——「这里你太软了，逼一下」「这个 NPC 答得太顺，问点棘手的」——给玩家 agent 一条临时指令调整方向。适合用户已经在终端旁边、有空看几眼的场景。

**事后 spot check**：测试完后读 `sessions/<id>.jsonl` 的关键回合。建议你（agent）在报告完成时附一段「**值得复核的 turn**」清单：

- 开局 setup 那一轮（验证 checklist 完整性 / 默认值机制）
- 第一次战斗 / 第一次掷骰那一轮（验证 engine 工具是否被调）
- 第一次价格 / 地点查询那一轮（验证读取类工具是否被跳过）
- 任何 GM 措辞让你感觉「这里可能有问题」的轮次（你的直觉值得记下来）

每条标 turn 编号 + 一句话理由。这样用户只读 5-10 个关键回合就能复核，而不是从头看到尾。


## 常见问题 & 诊断对照

| 观察到 | 结论 |
|---------|------|
| GM 第一轮没提开局 setup，直接开始叙事 | 开局 skill 未加载或未生效 |
| GM 把 setup 拆成多轮逐项追问 | 开局 skill 违反 setup.md 的「一轮内列完」原则 |
| GM 列出的清单漏了某项（如没问背景就结束 setup） | 开局 skill 清单生成时遗漏字段 |
| 用户说「开始」用默认值，GM 却追问细节 | 默认值机制未生效 |
| GM 开场叙事中裸露数值（如"粉丝+200"） | 叙事风格违反 gm.md 规则 |
| 自由交互第 2-3 轮 state 仍为初始值 | 状态更新工具未被调用 |
| 价格/地点/NPC 描述与 data 文件不一致 | 读取类工具未被调用，GM 在即兴创作 |
| 战斗有叙事无判定 | combat_attack / generate_npc 未被调用 |
| 任务奖励数值与 quest engine 不一致 | generate_quest 未被调用 |
| 即使 system prompt 要求调工具，模型仍跳过 | 工具的 `description` 字段缺少「必须调用场景」和「严禁行为」列表——详见 `references/platform-adapters.md` §「工具 description 工程」 |

## 工具调用遵从测试

读取类工具（`lookup_location`、`get_price`、`combat_attack` 等）是最容易被模型跳过的——强叙事模型倾向于「自己编」而不是「调工具查」。验证时重点检查：

1. **价格是否来自 `get_price`**——GM 说出任何带 G 的数字时，确认 `get_price` 在同一轮被调用
2. **地点描述是否来自 `lookup_location`**——GM 描述新地点时，确认调了 `lookup_location` 而非凭记忆描述
3. **战斗是否有 `generate_npc` + `combat_attack`**——任何攻击或伤害，确认先调了这两个工具
4. **任务是否有 `generate_quest`**——公告板上的委托，确认是工具生成而非即兴编写

测试方法：
- 查看 session JSONL 中每轮 assistant 消息的 `tool_calls` 字段
- 检查 state 中的 XP、金钱、背包变动是否与工具调用结果一致
- 如果工具未被调用但叙事看起来合理，说明模型在即兴创作——需要按 `platform-adapters.md` §「工具 description 工程」强化工具 description

遇到任何问题，直接向用户报告，指出具体哪一轮、GM 说了什么、预期应该怎样。
