# Card Semantic IR

Card Semantic IR 是 SillyTavern 卡进入 v2 runtime 的唯一中间表示。它描述作者想做的游戏，不描述 ST 怎么打补丁。

## 目标

IR 必须回答三件事：

1. 这张卡有哪些稳定事实？
2. 哪些东西会变化，变化规则是什么？
3. 哪些事实对玩家、主角、场景 NPC、GM/幕后分别可见？

不要在 IR 里保留 HTML 状态栏、JSON Patch 文本、COT 标签、`__结束__`、ST 宏调用语法。提取其背后的字段、规则、触发条件和可见性。

## 推荐结构

```ts
type CardSemanticIr = {
  version: 1;
  source: SourceCardSummary;
  persona: PersonaSpec[];
  settingFacts: SettingFact[];
  playerSetup: SetupRequirement[];
  openings: OpeningSpec[];
  mechanics: MechanicSpec[];
  mutableConcepts: MutableConcept[];
  visibilityFacts: VisibilityFact[];
  memoryRules: MemoryRule[];
  worldbookEntries: WorldbookDisposition[];
  scriptFindings: ScriptFinding[];
  style: StyleSpec;
  discardedStRuntimePatches: DiscardedPatch[];
};
```

实际生成可用 JSON，不要求完全照抄类型名；但这些语义块必须存在或有「不适用」说明。

## 关键块

### mutableConcepts

把状态栏字段和 MVU 变量转成领域概念：

```txt
好感度         → relationship.trust / affection
金钱           → economy.purse
HP/伤势        → condition / combat
任务阶段       → quest.progress
时间/地点       → scene-turn
秘密身份       → secret
NPC 后台行动    → faction/offscreen
```

每个 mutable concept 必须给出：

- 初始值来源：initvar / opening / setup / inferred。
- 变化触发：玩家行动、场景结算、时间推进、战斗、脚本。
- 合法改变通路：event pack。
- 是否 public、protagonist-known、player-only、hidden-canonical。

### mechanics

记录公式、阈值、骰子、经济、战斗、计时、路线分支等。不要把公式留在 prompt prose 里。

```txt
原文：每次送礼好感+5，超过60解锁邀约。
IR：relationship mechanic: gift → affection +5; threshold 60 → unlock date invitation.
```

### visibilityFacts

ST 卡常把 GM 真相、玩家设定、角色已知事实混在同一段。IR 必须拆开：

```txt
hidden-canonical: A 是凶手。
player-only: 玩家创建角色时知道自己是穿越者。
protagonist-known: 主角知道自己的穿越经历。
scene-public: 学校公告说今晚停电。
```

### worldbookEntries

世界书条目不要只标「保留/丢弃」。每条给 disposition：

```txt
data            稳定事实或大表
mechanic        规则/公式
event-pack      变更为领域事件
setup           开局选项
progressive     运行中 lookup / reveal
prompt-style    文风或输入解释
discarded       ST 补丁或重复内容
```

含 disabled 条目也必须审计。

## 抽取流程

1. 解包并生成条目索引。
2. 先抽 mutable concept 和 visibility fact，再整理 prompt 文风。
3. 审计 initvar / MVU / TH script / regex script，补 mechanic。
4. 为每条世界书记录 disposition。
5. 输出 `data/card-ir.json`。
6. 从 IR 生成 Runtime Plan；不要直接从原卡文本生成代码。

## 反模式

- `statusFields: Record<string, string>`：只是把状态栏搬家。
- `rawPromptSections` 直接拼进 GM prompt：没有语义层。
- `secretNotes` 混入 public context：泄密。
- `mechanicsText` 交给模型自行遵守：prompt 当防线。
- disabled 世界书不审计：漏 DLC、路线、草稿规则。

## IR 验收

本清单是 IR 阶段闸门，在输出 `data/card-ir.json` 时跑；完工闸门见 `references/validation.md`。

- [ ] 所有 alternate greetings / group greetings 有去向。
- [ ] 所有世界书条目含 disabled 有 disposition。
- [ ] 所有 initvar 字段映射到 mutable concept 或丢弃理由。
- [ ] 每个 mutable concept 有合法 event pack。
- [ ] hidden-canonical 不进入 public facts。
- [ ] ST 宏和输出补丁只留下语义，不留下语法。
