# 校验

本文是完工闸门的唯一权威：残留扫描、人工清单、下场实测全过才算完成。各 reference 的阶段闸门（IR 验收、工具设计校验、prompt smoke tests）在对应阶段跑，不替代本闸门。

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
- [ ] 主角/操控者地位由指针表达，运行时不散落硬编码 id 判断；seed id 若存在只在初始化/迁移常量里出现。
- [ ] public registry key 不泄露 hidden truth；真名、凶手、阵营秘密不出现在 actor/item/location id。
- [ ] 多 agent 场景：in-process subagent 是 project-scope，显式 tools/extensions，不拿 `code_act`，不继承完整项目上下文/技能目录；知密导演子进程带 `--no-tools --no-approve --no-context-files`，session 落 gitignored 目录，有 harvest + pending-harvest 台账。
- [ ] evented 方案有 `engine/events.ts`、`engine/reducers.ts`、protected paths、session-backed state。
- [ ] reducer 测试覆盖关键事件；secret/public/player knowledge 分层有测试或 fixture。
- [ ] 多台账/多领域项目有一条**引擎集成走查**（见「下场实测」前的三层划分）：在工具层把开局→beat→混合领域 commit→战斗/义务闭环→秘密防漏→收口全链路走一遍。
- [ ] 4X/容器型 pack（单位/建筑/项目集合）：环上限等边界 reducer 有测试；若实体类别字段与事件判别字段同名（都叫 `kind` 之类），CodeAct 路径要强制嵌套避免被覆盖。
- [ ] 公式重的系统（制造/经济）：总量等派生量由 reducer 权威计算，不接受 LLM 传入；系数表对照原卡锚点有单测，原卡内部矛盾（表与示例冲突）在代码注释里钉死取舍。
- [ ] prompt orchestrator 只渲染 Runtime Plan 和 state projection，不维护领域正确性。
- [ ] TS 产物通过 typecheck/lint/format（基线见 `references/engineering-discipline.md`）。
- [ ] 标准方案若使用 CodeAct，其 API 提交领域事件，不暴露 raw state setter。
- [ ] typed tool 的参数 schema 暴露 reducer/buildEvent 消费的**每一个**字段；schema 漏字段 = LLM 物理上填不进 = 该字段静默落空（如装备词条 effects 只在 buildEvent 读、不在 schema 声明）。这类缺口直调 reducer 的单测测不到（单测绕过 schema），只有下场实测现形。
- [ ] 常规玩法没有万能 `update_state` / 裸 `patch_state`。
- [ ] 现实题材 external research 与本地 canonical data 边界清楚；虚构世界默认禁 web。
- [ ] 重叙事/长轮项目提供可观测开关：逐 pass API 输入导出 + 强制压缩演练（见「可观测性开关」），便于长轮验证而不必堆满上下文窗口。
- [ ] 两段式项目可逐 pass 导出每次 LLM 输入（结算多次调用分别留痕、渲染调用单独留痕），用于核对 prompt 组装、防火墙、缓存前缀、packet 内容。

## 会话 JSONL 审计

重叙事项目建议附带一个读 session JSONL 的审计脚本：叙事 lint 规则（坏味句式、泄密、长度下限）与运行时 lint 共享同一模块，避免两套口径。两段式项目分别 lint 渲染面（prose custom message）与结算面（direction packet）。允许项目/玩家追加本地 prose lint regex，作为口味层覆盖；内置规则管硬禁区，本地规则管个人文风厌恶。台账化的纪律（obligations、hooks）用对账方式审计，不要通读转录。

## 下场实测

下场实测（交互调真 LLM、多轮）与确定性引擎测试是两个**不可互替**的轴；确定性一轴内部又分两层，共三层各抓不同的 bug：

- 单域测试（构造 event 直调 reducer）抓：公式错、单域状态漂移。
- **引擎集成走查**（确定性、不调 LLM，但走**工具层**这个唯一写入面）：一条测试把迷你战役从开局走到收口——new-game init → NPC/presence → begin-beat → 混合领域 commit（伤势/经济/威胁/多层记忆）→ 战斗交换 + 义务销账 → 后台义务硬阻→解除闭环 → 钩子/时钟 → 秘密不漏进 public/brief → complete-beat。它抓的是跨域回归：台账互相联动时炸、migration/invariant 不协同，而单域测试全绿。
- 下场实测抓：prompt→行为→工具选择→参数填充→两-pass 渲染→压缩。前两层都**绕过了 GM prompt**（集成走查虽经过 tool schema，但输入是人写的合法值），所以抓不到「GM 该调的工具没调、prompt 没喂到、schema 漏字段致 LLM 填不进」。两个典型只能被下场实测抓到的缺口：① 机器就绪但玩法分支规则/花名册没接进 GM prompt（GM 从不发起该玩法）；② typed tool schema 漏了 reducer 消费的字段（LLM 填不进→该字段静默落空，而单测全绿）。

结论：单测全绿 **不等于** 系统能跑。如果某个系统靠 prompt 驱动或靠 tool schema 暴露，它的「能用」只能由下场实测证明。

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
- 状态是否真的写入；写入的**字段是否齐**（如装备/道具的词条、机制描述）——schema 漏字段会表现为“落账了但某子字段空”，需查 tool 调用参数是否含该字段。
- evented 方案是否调用领域事件工具或 `code_act` domain API，且用组合/场景 API，不只裸 patch。
- 叙事里不裸露 `+200 好感` 这类数值指令。
- 长跑后前后设定、价格、地点、NPC 记忆是否一致。
- 多系统连续触发后 state 是否仍符合 schema。
- 4X/容器型 pack：资产登记、项目立项→推进→完成、离屏世界推进都能落账，且在 state projection 有对应段；环型结构（如新闻环）不超上限；离屏事件不围绕玩家转。
- hidden-canonical 是否没有串进 public memory。
- 两段式项目是否没有 Pass A assistant text 泄进玩家正文或后续 prompt；玩家可见 prose 只来自渲染 custom message。
- 多角色场景的 packet 是否给重要 NPC 提供 binding `move` / voice guidance；渲染结果里 NPC 没有退化成背景板、旁观者或纯反应机器。
- suggestedActions / choice widget 是否在 turn_start 清空旧项、reroll 后重建，显示文本与提交文本一致。
- 后续要清除/解决/更新的条目是否可用 id 或 summary 片段再次寻址，错误能列候选。
- external research 是否只作为只读证据，没有覆盖卡片 canonical facts。
- subagent 返回是否是候选/审计，且由 GM 转成领域事件。

## 可观测性开关（dev，建议提供）

长轮验证里两件事最难只靠通读转录确认：① 每次 LLM API 到底看到什么；② 接管压缩/压缩路径是否如设计触发。建议项目提供两个 env 开关，均 env-gated、生产/测试环境自动禁用、只写 gitignore 的 debug 目录。

### 逐 pass API 输入导出

开关开启时，把**当前轮次**每次 LLM 调用的输入落盘成可读 transcript：

- 结算 pass 的每次 agent-loop 调用分别留痕（`passA-1`、`passA-2`…，模型多轮工具调用 = 多个文件）；两段式的渲染调用单独留痕（`passB`）。
- 每个文件含完整 system prompt + 逐条消息（role 标注、工具调用展开为 `→ tool: name` + JSON 参数、custom message 标 customType）。
- 每轮开始清空上一轮的 per-pass 快照（但保留压缩产物，见下）。

用途：核对注入栈是否如预期（模块数、顺序）、Pass-A 文本是否被防火墙剥离、渲染历史的缓存前缀是否逐轮稳定、packet 字段是否完整、hidden-canonical 是否没串进任一 pass。

### 强制压缩演练

压缩通常要堆满上下文窗口才触发，长轮 soak 成本高。开关开启时把压缩预算调到极低 + 在回合开始手动触发一次压缩，零成本演练接管压缩路径并落盘压缩产物（确定性摘要 / LLM 摘要均可观测）。两个实现要点（踩过的坑）：

- **改对配置文件**：若 launcher 用 `PI_CODING_AGENT_DIR` 把配置目录重定向（如 `.pi/agent/`），pi 读的是该目录下的 `settings.json`，不是项目根 `.pi/settings.json`；预算（`compaction.keepRecentTokens` / `reserveTokens`）要写进 pi 真正读的那个文件。预算默认较大（keepRecent 20000 + reserve 16384），小会话会报「session too small」而不压缩。
- **在 loop 内触发才落盘**：`ctx.compact()` 是 fire-and-forget；在 `turn_end` 之类回合末触发，headless `-p` 会赛跑进程退出而不持久化。在**回合开始**（如 `before_agent_start`）触发，pi 在自身 loop 内同步跑完压缩，`-p` 下也能落盘 compaction entry。
- 开关关闭时 launcher 应自动移除低预算，正常游玩不受影响。

验证落点：`onComplete` 回调拿到 `firstKeptEntryId`、session JSONL 出现 `"type":"compaction"` 条目、压缩产物文件内容符合设计（如确定性索引头部钉死「state 才是真相源」、近若干轮保留完整裁决脉络）。

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
| 工具存在但模型不用 | description 没写清用途/使用边界/禁区，或 tool surface 太浅/太像字段 setter |

报告问题时给 turn、GM 原话、预期行为。
