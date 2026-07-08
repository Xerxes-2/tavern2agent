# 认识论审计 2026-07

对本 skill 全部教义做一次「想当然 vs 实战经验」的出身鉴定与承重核对。
方法：溯源考古（git 血统）+ 证物核对（实战仓）+ 第一性重推（兜底）。
本文档是证据档案；SKILL.md 与 references 正文只反映裁决结果，不背审计元数据。

## 1. 方法与证据边界

- **溯源考古**：对每条硬约束的特征短语 `git log -S` 追出生提交，分类为
  脚手架期（2026-05-10~13，先于一切实战）、建设期（05 月，与 dest-poet/idol/bub-test-witch 并行）、
  v2 宪法（06-10 c570589，+802 行一次性定义）、回流期（明确标注实战经验波的提交）。
- **证物仓**：fate-sandbox（472c，主证物）、fate（387c）、dest-poet（174c）、idol（77c）、
  jirai（12c）、lonestar（6c）。fate-sandbox 留存 97 个 session jsonl（182MB，2026-05-26 ~ 06-22）。
- **证据边界（重要）**：
  - fate-sandbox session 存档止于 **06-22**；第四波回流（07-07「长跑项目」）所据的后续对局
    不在本证据库。凡引用第四波的条目，出身可考，承重数据缺席。
  - 所有承重数据来自单一旗舰仓；轻量档证据见 §4 缺口。
  - 本轮未做实证复测（新卡跑全流程），留作后续验证。

## 2. 根命题承重率（主秤数据）

范式：卡 → IR → evented runtime（domain event + reducer + engine）。

fate-sandbox 97 sessions 实测：

| 指标 | 数值 | 读法 |
|---|---|---|
| `commit_turn` 调用 | 606 | 事件形态是主干写入路径 |
| 领域事件总发射 | 1316（scene 972 / actor-condition 103 / scene-beat 77 / servant-form 74 / economy 31 / memory 30…） | 事件目录非纸面 |
| 全部工具调用 | ≈6800 | 31 个注册工具中 top-20 高频 |
| reducer/校验拒绝 | 783 次（≈11.5% 调用被拦） | 全部为领域语言拒绝（「非法 elapsedMinutes」「setup-protagonist 只能写入 actor.id=protagonist」）；prompt-only 下这些是无声的状态腐败 |
| session custom entry 写入 | 3107 | state 真相源纪律被字面执行 |
| 空转长尾 | update_hook 3 / run_parallel_line 4 / harvest_backstage_candidate 1 / resolve_backstage_line 1 / manage_faction_clock 5 | 集中在 backstage/平行线面，见 §4 |

**主秤结论：机制显著承重，非工程师自嗨。** 反事实（没这套机制玩起来会不会照样好）
机器量不出，由玩家证言副秤补（裁决记录见 §5）。

## 3. 认识论地图

出身代号：【脚】脚手架期｜【建】建设期｜【宪】v2 宪法 c570589｜【流N】第 N 波回流。
裁决：✅ 维持红线｜✅⁻ 维持但证物薄弱（标注）｜✍ 改写（已于本轮落地）。

### State 与 engine

| 条目 | 出身 | 证物 | 裁决 |
|---|---|---|---|
| 计算进 engine / prompt 极简 | 【脚】05-13 | 后续一切证物压倒性执行；resolve_check 62 次等 | ✅（原则先于实战，被用役追认） |
| 可查询性/承重判据（分档信号） | 【流】06-29 98bcfe7 | 推翻初版「有无 MVU」判据的二代产物 | ✅ |
| 单一写入 runner | 【流1】06-11 d154654 (fsn) | fate-sandbox `commitTurn(draft, input)` 字面执行 | ✅ |
| session custom entry 真相源 | 【建】05-23（替换 file-rewind 方案的墓碑） | 3107 条 custom entry | ✅ |
| Static<> 派生 / 禁手写平行类型 | 【流4】07-07 | state-schema.ts 实装 | ✅ |
| schemaVersion + 确定性 migration | 【建】05-22 (dest-poet 期) | state-migration.ts + migrate_state 调用 7 次 | ✅ |
| 万能 setter 禁令 / patch 纪律 | 【宪】06-10 | patch_state 84 次(05下) → 0(06 起)，被事件形态取代的演化史 | ✅ |
| Prompt 不是防线 / state-backed ledger | 【流2】06-12 (fate-sandbox) | backstage-obligation 机器实装+测试 | ✅ |

### 工具面

| 条目 | 出身 | 证物 | 裁决 |
|---|---|---|---|
| 契约与实现同文件 | 【流1】06-11 (fsn) | registry.ts 为纯 import 清单 | ✅ |
| 工具清单整局稳定（禁运行时 toolset） | 【流1】06-11（推翻 05-22「动态 toolset」教义的墓碑） | switch_toolset 17→0；换代期「Tool update_scene not found」×14 | ✅ |
| 入口收敛（命令面板 xor one-commit-per-turn） | 【流4】07-07 | 双入口并存痛史：05下~06中 update_* 与 commit_turn 长期共存后收敛 | ✅ |
| description 瘦身 / 反 reasoning-bait | 【流3】06-18 (fsn) | 回流出身 | ✅ |
| renderResult 折叠/展开 | 【建】05-16 | tool-render.ts 实装 | ✅ |
| tool schema 不当 serde | 【流4】07-07 | normalizer 文件群 + 「Validation failed」83 次 | ✅ |

### Prompt 面

| 条目 | 出身 | 证物 | 裁决 |
|---|---|---|---|
| 注入栈整局静态 + 测试钉死模块数 | 【流3】06-18 (fsn) | preset.test.ts:33 assert modules.length | ✅ |
| orchestrator 只渲染不碰 canonical state | 【宪】06-10 | prompt-assembly 分层实装 | ✅ |
| 措辞纪律（去脚手架措辞/去主语） | 【流3】06-18 (fsn) | 回流出身 | ✅ |
| ST 宏/COT/JSON Patch/HTML 状态栏剥离 | 【脚】05-10 | 第一性显然（pi 无 ST 宏运行时）；update_status→patch_state→事件的三代演化 | ✅ |

### 事实源与 subagent

| 条目 | 出身 | 证物 | 裁决 |
|---|---|---|---|
| 多 agent 只解决认知隔离 | 【脚】05-10 Init | subagent 163 次 + faction_director 8 次；06-10 seams 澄清重写过一次 | ✅（原则先于实战，第一性站得住：上下文隔离是 subagent 唯一不可替代收益） |
| subagent 不写 state / harvest 模式 | 【建】06-10 6c38afb | harvest-backstage 机器实装 | ✅ |
| 密闭导演 detached spawn 接缝 | 【流4】07-07 | run_parallel_line 4 + parallel_line 2 + resolve_backstage_line 1——**低频**；所据长跑对局在证据边界外 | ✅⁻（出身可考，承重数据缺席，玩家证言补充见 §5） |
| 现实题材 web/fetch 事实源 | 【建】06-10 | web_search 17 次 | ✅ |

### 架构与流程

| 条目 | 出身 | 证物 | 裁决 |
|---|---|---|---|
| domain event 中心（根命题执行面） | 【宪】06-10 | §2 承重率 | ✅ |
| IR 先行（card-ir.json → Runtime Plan → 代码） | 【宪】06-10 | v2 后项目 jirai/lonestar 均产出 card-ir.json + runtime-plan.json；**无对照组**（v2 前项目无 IR 也完工） | ✅（执行确认，收益未对照） |
| event pack 目录 | 【宪】06-10 | combat 32 / economy 99 / secret 90 / memory 129 实际使用 | ✅ |
| 三档分档 | 【宪】06-10（05-18 一代被推翻后的二代） | evented 两档充分验证；**prompt-only 档零实战样本**（最轻的 lonestar 也是 7792 行 TS） | ✍ 玩家证言 Q-c 裁决废除 prompt-only 档：纯设定卡改为「不转换、建议玩原卡」退出闸门，分档变两档（已改 decision-tree/SKILL/evented-runtime/codeact/two-pass/README） |
| 两段式结算/渲染 | 【流2】06-12 (fate-sandbox 起源) | engine/render + prompt-assembly 实装 | ✅ |
| CodeAct 载体 | 【建】05-26 | lonestar 实装（4 文件）、idol 有痕迹——弱样本但非空想 | ✅⁻ |
| TS 严格基线 | 【建】05-27 | fate-sandbox strict + noUncheckedIndexedAccess + 248 测试文件 + knip | ✅ |
| 下场实测闸门 | 【脚】05-13 | 97 个真实对局 session；「20-30 轮」数字系启发式，但绑定了覆盖判据（至少触发 3 类核心机制），非裸数字 | ✅（数字标注为启发式） |

### 已被自我纠错机制处决的教义（墓碑登记）

审计确认这些**曾经的「实战经验」**后来被更多实战推翻——回流出身不是免死金牌：

| 亡者 | 生 | 卒 | 死因 |
|---|---|---|---|
| 动态 toolset（always/setup/combat/social/debug 切换） | 05-22「复杂卡工程化实战经验」 | 06-11 d154654 | fsn 实战：切换毁 prompt cache + 模型调用已删工具 |
| 「有无 MVU」分档判据 | 05-10 Init | 06-29 98bcfe7 | 无 MVU 的不可逆拐点照样需要 evented；满屏 MVU 多为氛围 |
| file-rewind state | 05 月初 | 05-23 7a5151a | session-backed 真相源取代 |
| update_status / 裸 patch_state 主干 | 05-16 | 06 上旬 | 事件形态取代，patch 降为受保护逃生舱 |

## 4. 缺口清单（非证伪，是证据缺席）

1. ~~prompt-only 档零样本~~ —— 已由玩家证言 Q-c 裁决：非选样偏置，而是该档位本身无价值，已废除并改为退出闸门（缺口关闭）。
2. **密闭导演/平行线低频**：backstage 深水区机器使用次数个位数，且第四波所据对局在证据边界外。
3. **CodeAct 单样本**：typed tools vs CodeAct 的取舍论证（tool-abstraction.md 439 行中的相关章节）
   建立在 1 个 CodeAct 项目上。
4. **IR 先行无对照**：执行了，但没有「不做 IR 直接写」的失败对照，收益论证是推理不是观测。
5. **单一旗舰仓偏置**：承重率全部来自 fate-sandbox（重档）；轻档（jirai/lonestar）session 未纳入本轮扫描。

## 5. 玩家证言（副秤裁决记录）

（闸一时由维护者作答，记录于此）

- Q-a 反事实体验：同题材下 evented 版 vs ST 原卡/prompt-only，体验差距是否真实且值得工程成本？
  - 答：**差距主要在特定卡型**——秘密/机制重卡差距明显，普通卡差距小。根成立但适用边界收窄，与 Q-c 裁决互验。
- Q-b 783 次 reducer 拒绝在玩家侧的体感：保护一致性，还是打断节奏？
  - 答：**基本无感，纯保护**——拒绝发生在工具层，GM 自行重试修正，机制纯收益。
- Q-c prompt-only 档零样本：是没遇到轻卡，还是轻卡也被拉成了 evented？
  - 答：**直接废除该档位**——纯设定卡转了没什么收益，改为不转换退出闸门。
- Q-d backstage/密闭导演/平行线机器：低频是「用得少但关键时刻值回票价」还是「造了没怎么玩」？
  - 答：**需要更多验证；现阶段问题是 GM 不太会用，用了的话效果不错**——定性为 affordance 问题而非机制问题；下轮验证项：改善 GM 侧的可发现性（prompt 模块提示/工具 description 引导）后再测承重。

## 6. 事实类内容（本轮未核，标记待查）

以下为对外部事实的描述，审法是对照官方文档而非查出身，不在本轮预算：

- `references/mvu-mapping.md`「MVU 实情」节（正文自带「拿不准就 fetch 官方原文」自我防御）
- `scripts/extract_card.py` 对 v1/v2/v3 卡格式的归一化行为
- `references/pi-integration.md` 中对 pi API 形状的描述（pi 版本演进可能使其过时）

## 7. 冷体检附录（2026-07-08）

- 死链：0（SKILL.md 引用、references 交叉引用全通）
- 孤儿 reference：0
- 路由表与文件系统一致
- 杂项：`/home/ubuntu/tavern2agent` 是本仓陈旧克隆（落后 2 提交），建议删除或拉平以防误编辑

## 8. 总结论

**根命题成立，但适用边界收窄**：主秤——事件机制在 6800 次工具调用中高频承重，11.5% 的调用被领域校验拦截（玩家侧无感，纯保护）；副秤——体验差距集中在秘密边界/机制承重卡型，普通卡收益小。
据此本轮废除 prompt-only 档，纯设定卡改为不转换退出闸门；范式定位从「什么卡都能转」收窄为「专治有承重转换与秘密边界的卡」。

**存量「想当然」远比预期少**：git 考古显示自我纠错机制（经验回流波）已系统性处决了
早期误判（§3 墓碑登记四座）。现存教义中约八成有回流出身或直接证物；
脚手架期存活至今的三条（计算进 engine、认知隔离、下场实测）均通过第一性重推且被用役追认。
真正的想当然残留不在「已写下的纪律」，而在「从未被实战踩过的档位与接缝」（§4）。

**对下一轮的建议**：优先用实战填 §4 缺口（找一张真正的轻卡走 prompt-only 档），
而不是继续打磨已验证教义的措辞。
