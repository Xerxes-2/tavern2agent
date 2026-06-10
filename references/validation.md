# 校验

目标：确认产物完整、无 ST 残留、IR/Runtime Plan 完整，GM 真的会提交领域事件并写 state。

## 残留扫描

```bash
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求" \
  agents/ engine/ data/ skills/ 2>/dev/null && echo "↑ 有残留" || echo "✓"

grep -rnE '\{\{(user|char|random|roll|pick|getvar|setvar)' \
  agents/ skills/ data/ 2>/dev/null && echo "↑ 有 ST 宏残留" || echo "✓"

grep -rnE 'update_state|patch_state|直接修改状态|JSON Patch' \
  agents/ tools/ engine/ skills/ 2>/dev/null && echo "↑ 检查是否是 debug-only" || echo "✓"
```

游戏字段如生命值、好感度、回溯次数不是残留；把它们当作可裸 patch 字段才是问题。

## 人工清单

- [ ] `data/card-ir.json` 存在，所有 mutable concept、visibility fact、worldbook disposition 有去向。
- [ ] `data/runtime-plan.json` 存在，event pack、state root、fact source、tool surface、subagent role、prompt module、validation plan 清楚。
- [ ] `agents/preset.json` 存在，slot 顺序清楚，source 只指向 `agents/*.md` 或已知 runtime source。
- [ ] `agents/gm-*.md` 按职责拆分；没有把世界书、工具说明、硬规则、输出合同塞成一坨。
- [ ] 开局 skill 存在，setup 字段齐，默认值齐。
- [ ] `first_mes` 已剥离 HTML/状态栏/ST 宏。
- [ ] `alternate_greetings` / `group_only_greetings` 有去向。
- [ ] 所有世界书条目含 disabled 有去向。
- [ ] `[initvar]` 转成 mutable concept + `INITIAL_STATE`，不是直接搬成 LLM 可 patch 字段。
- [ ] TH scripts / regex scripts 已审计。
- [ ] 章节/大型设定未全量塞 prompt。
- [ ] 主角设定若存在，已进入世界书 / start skill / actor state / memory / 可选 prompt module；不默认生成 `data/user.json`。
- [ ] 多 agent 场景有 project-scope subagent，显式 tools/extensions，不拿 `code_act`，不继承完整项目上下文/技能目录。
- [ ] evented 方案有 `engine/events.ts`、`engine/reducers.ts`、protected paths、session-backed state。
- [ ] 标准方案若使用 CodeAct，其 API 提交领域事件，不暴露 raw state setter。
- [ ] 常规玩法没有万能 `update_state` / 裸 `patch_state`。
- [ ] 现实题材 external research 与本地 canonical data 边界清楚；虚构世界默认禁 web。

## 下场实测

最小流程：

```bash
cd 项目目录
./start.sh -p "开始游戏"
./start.sh --continue -p "你的回应"
```

你作为测试玩家 Agent 跑至少 20-30 轮。流程：开局 → setup 回复 → 自由交互 → 主动覆盖主要系统。evented 方案至少触发 3 类核心机制，如 scene-turn、relationship、secret、economy、combat、quest、lookup、时间跳跃。

你可以明说自己在测试，请 GM 配合快速进入指定场景、允许时间跳跃、触发商店/战斗/任务等系统；这是测试协议，不是正式游玩体验。

观察：

- 开局是否一轮列完缺失项。
- 开场是否有具体时间、地点、情境。
- GM 是否跳过 lookup 直接编预设事实。
- 状态是否真的写入。
- evented 方案是否调用领域事件工具或 `code_act` domain API，且用组合/场景 API，不只裸 patch。
- 叙事里不裸露 `+200 好感` 这类数值指令。
- 长跑后前后设定、价格、地点、NPC 记忆是否一致。
- 多系统连续触发后 state 是否仍符合 schema。
- hidden-canonical 是否没有串进 public memory。
- external research 是否只作为只读证据，没有覆盖卡片 canonical facts。
- subagent 返回是否是候选/审计，且由 GM 转成领域事件。

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
grep -cE '"name":"(commit_turn|record_relationship_shift|reveal_secret|spend_money|apply_condition|record_offscreen_event)' "$latest"
```

如有领域工具，按实际名称查：`combat_attack`、`get_price`、`lookup_location` 等。不要只查 `patch_state`；常规玩法依赖 patch 视为失败。

## 诊断

| 现象 | 结论 |
|---|---|
| 第一轮没 setup | 开局 skill 未加载/未触发 |
| setup 逐项追问 | start-game 规则错 |
| setup 漏字段 | 缺失信息审计漏了 |
| 用户接受默认值仍追问 | 默认值机制错 |
| state 不变 | 领域事件未调用、reducer 未落地或未持久化 |
| 预设事实前后不一 | lookup 未调用 |
| 战斗有叙事无判定 | engine/code_act 未调用 |
| hidden truth 进 public memory | visibility policy / secret pack 失败 |
| web 资料改写原卡设定 | fact source policy 失败 |
| subagent 直接写 state | subagent tool/extension 边界失败 |
| 工具存在但模型不用 | description 缺「必须调用/严禁编造」，或 tool surface 太浅/太像字段 setter |

报告问题时给 turn、GM 原话、预期行为。
