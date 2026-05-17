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

答案是：**以玩家身份进入游戏，亲身走完交互链路。** 像真人一样读 GM 输出、按人设回应、对 GM 的措辞/数值/跳问当场判断——而不是写脚本断言。

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

每轮：读完 GM 的终端输出 → 想好回应 → 用 `--continue` 发送。像真人一样——问什么答什么，想探索就探索，想打架就拔刀。**不要用预设脚本，不要逐条对标 checklist。** 把自己当玩家。

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
# 看关键字段
python3 -c "
import json
s = json.load(open('state/state.json'))
print('HP:', s['主角']['生命值'], '/', s['主角']['生命值上限'])
print('XP:', s['主角']['累计经验值'])
print('背包:', list(s['主角']['背包'].keys()) if s['主角']['背包'] else '空')
print('关系:', list(s['关系列表'].keys()) if s['关系列表'] else '空')
"

# 统计工具调用次数
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"combat_attack"'
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"get_price"'
ls -t sessions/*.jsonl | head -1 | xargs grep -c '"name":"lookup_location"'
```

如果战斗叙事很精彩但 `combat_attack` 调用次数为 0——说明 GM 在即兴创作，工具根本没被调。需要强化工具 description（参见 §「工具 description 工程」）。

### 6. 时间和 token 成本

一个人认真跑完 15-30 轮大概需要 20-40 分钟，消耗几十万 token。**值得。** 这是唯一能同时验证叙事质量、工具链路和状态一致性的方法。grep 和人工清单只能查出文件缺失和 ST 残留，查不出"GM 有没有真的掷骰"。


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
