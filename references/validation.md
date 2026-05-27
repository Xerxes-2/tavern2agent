# 校验

目标：确认产物完整、无 ST 残留、GM 真的会调工具和写 state。

## 残留扫描

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求" \
  agents/ engine/ data/ skills/ 2>/dev/null && echo "↑ 有残留" || echo "✓"

grep -rnE '\{\{(user|char|random|roll|pick|getvar|setvar)' \
  agents/ skills/ data/ 2>/dev/null && echo "↑ 有 ST 宏残留" || echo "✓"
```

游戏字段如生命值、好感度、回溯次数不是残留。

## 人工清单

- [ ] `agents/gm.md` 核心规则 ≤5 条。
- [ ] 开局 skill 存在，setup 字段齐，默认值齐。
- [ ] `first_mes` 已剥离 HTML/状态栏/ST 宏。
- [ ] `alternate_greetings` / `group_only_greetings` 有去向。
- [ ] 所有世界书条目含 disabled 有去向。
- [ ] `[initvar]` 转成 `INITIAL_STATE`。
- [ ] TH scripts / regex scripts 已审计。
- [ ] 章节/大型设定未全量塞 prompt。
- [ ] 需要用户卡时有 `data/user.json` 或 setup 字段。
- [ ] 多 agent 场景有独立 subagent，且不拿 `code_act`。
- [ ] 标准方案有 CodeAct API、protected paths、session-backed state。

## 下场实测

最小流程：

```bash
cd 项目目录
./start.sh -p "开始游戏"
./start.sh --continue -p "你的回应"
```

你作为测试玩家 Agent 跑至少 20-30 轮。流程：开局 → setup 回复 → 自由交互 → 主动覆盖主要系统。标准方案至少触发 3 类核心机制，如战斗、经济、掷骰、任务、lookup、时间跳跃。

你可以明说自己在测试，请 GM 配合快速进入指定场景、允许时间跳跃、触发商店/战斗/任务等系统；这是测试协议，不是正式游玩体验。

观察：

- 开局是否一轮列完缺失项。
- 开场是否有具体时间、地点、情境。
- GM 是否跳过 lookup 直接编预设事实。
- 状态是否真的写入。
- 标准方案是否调用 `code_act`，且用组合/场景 API，不只裸 patch。
- 叙事里不裸露 `+200 好感` 这类数值指令。
- 长跑后前后设定、价格、地点、NPC 记忆是否一致。
- 多系统连续触发后 state 是否仍符合 schema。

## 查 state / 工具调用

```bash
python3 - <<'PY'
import json
s=json.load(open('state/state.json'))
print(json.dumps(s,ensure_ascii=False,indent=2)[:2000])
PY

latest=$(ls -t sessions/*.jsonl | head -1)
grep -c '"name":"code_act"' "$latest"
grep -c '"name":"lookup' "$latest"
```

如有领域工具，按实际名称查：`combat_attack`、`get_price`、`lookup_location` 等。

## 诊断

| 现象 | 结论 |
|---|---|
| 第一轮没 setup | 开局 skill 未加载/未触发 |
| setup 逐项追问 | start-game 规则错 |
| setup 漏字段 | 缺失信息审计漏了 |
| 用户接受默认值仍追问 | 默认值机制错 |
| state 不变 | 状态工具未调用或未持久化 |
| 预设事实前后不一 | lookup 未调用 |
| 战斗有叙事无判定 | engine/code_act 未调用 |
| 工具存在但模型不用 | description 缺“必须调用/严禁编造” |

报告问题时给 turn、GM 原话、预期行为。
