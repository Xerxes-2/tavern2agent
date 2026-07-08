# 两段式回合：结算导演 + 洁净渲染

重叙事卡（长跑、隐藏信息、强 prose 要求）推荐把每回合拆成两段：

```txt
settlement pass  agent 循环：工具调用、规则裁决、知密推理
                 → 以 submit_direction_packet 提交结构化 direction packet 收尾
render pass      裸 stream() 调用（不是 agent）：packet → 玩家可见 prose
```

packet 是两段之间唯一通道，过防火墙（按 secrets 路径整包拒绝泄密）。渲染器只看 packet + 自己之前的 prose（存成 custom message，如 `xxx-prose`）；结算上下文反向过滤掉这些 custom message，prose 永不回流进裁决。

## 为什么拆

单段「agent 回合末尾顺便写 prose」三个病灶，审计中全部实证：

- prose 质量与工具纪律在同一次生成里互相挤压。
- 秘密在工作记忆里，热情叙述时真名/真相直接漏出。
- engine 拒绝提交时，失败直接暴露给玩家。

拆开后：结算侧被 engine 硬拒就幕后重试，玩家只看到最终 prose——**硬拒从此没有 UX 成本**，这是引擎台账敢硬闸的前提（见 `evented-runtime.md` 引擎台账节）。两侧可独立换模型：实测组合是工具纪律强的模型做结算 + prose 强的模型做渲染，用环境变量（如 `XXX_RENDER_MODEL`）选择。

## packet 合同

渲染器只能看见 packet；结算器漏写的内容玩家永远看不到。合同口径：**宁可多一条，不可少一条**。不要让渲染器偷看 state 来兜底——那会把秘密防火墙打穿。

packet 至少含：playerAction、resolvedChanges（所有落地的状态变化）、NPC 主动动作指导、场景指示、eventWeight（节拍权重，映射到具体字数下限，见 `prompt-composition.md`）。

多角色场景要给重要 NPC 一个 player-safe stance block，例如 `npcStances[] = { actorId, stance, wants, move, refusesToSay }`：

- `stance` / `wants` 给渲染器理解语气和当前欲望。
- `move` 是 binding：该 NPC 本轮为了推进 `wants` 主动说出/做出的一个具体行为、要求、肢体动作或插话。重要 NPC 缺 `move` 是 packet bug；renderer 会自然把他写成背景板。
- `move` 必须是可公开演出的表层动作，不写隐藏目的；隐藏动机留在 state/secrets，最多通过 `wants` 的 player-safe 表述和一个身体细节让 renderer 间接表现。
- `refusesToSay` 只描述该角色回避的话题类别，不写秘密本体；整包仍过 secret firewall。
- 渲染提示要声明 `move` 不得降级成「观望/小心走/沉默/被动反应」，而要写成 NPC 自己的 initiative，并用该角色 voice signature 演出来。

packet 里面向玩家的建议字段（如 suggestedActions 的 submitText）要用**无主语动作短语**：它会变成真正的玩家消息，固定主语（我/你）会和玩家角色身份或视角错配。

## Pass A 文本防火墙

结算侧（Pass A）只应产生工具调用和 direction packet；任何 assistant text 都不是玩家正文。要在两个位置清理泄漏：

- `message_end` / session entry 落盘时：工具调用 assistant message 若混入 text part，删 text、保留 thinking/tool call。
- prompt/context 注入时：已持久化的 Pass A 泄漏也要过滤，不能因为历史里已有就回灌给模型或玩家。

玩家可见 prose 只来自 Pass B 的 custom message（如 `xxx-prose`）。这条必须有测试：纯文本 assistant message（真正 meta 回复）不删；tool-call assistant 的 text 泄漏才删。设计期就接一个逐 pass API 输入导出开关（见 `validation.md` 的「可观测性开关」）：`passA-*` 应见 text 已剥离、`passB` 是唯一 prose 来源，长轮里只靠它就能逐轮肉眼确认防火墙没破。

## 玩家选择 UI 生命周期

如果 packet 生成 suggestedActions / choice widget：

- UI 展示文本必须和真正提交的 user message 一致，不能只显示摘要而提交隐藏长串。
- turn_start 清空旧 widget，防止下一轮沿用 stale choices。
- reroll 时从新 prose / 新 packet 重新持久化 suggestedActions；隐藏 leaf、审计 entry、custom prose entry 不能让 reroll target 失效。
- suggestedActions 属于玩家界面提示，不是叙事正文；不要塞进 endWindow 或 prose。

## 长轮上下文：差异化精简 + 恒定前缀

两段式不只是拆职责，也是长轮上下文管理的骨架。一条总原则：**每个 LLM 调用只看其职责所需，且每个调用的前缀逐回合恒定**。两个 pass 的上下文需求是不对称的，各精简到自己的活：

- **结算 pass** 要 canonical 事实（已在 state，不必塞进历史）+ 近期裁决脉络 → 接管压缩，退化成状态派生的确定性索引（下「接管压缩」）。
- **渲染 pass** 要 prose 连续性 → append-only 历史 + 桶滞回（下「渲染器历史」）。

两者共享三条纪律：差异化精简（不把全量上下文给每个 pass）、前缀缓存稳定（绝不按当轮输入变前缀，见 `engineering-discipline.md`）、能确定性的地方不调 LLM。两个 pass 的历史还可共用同一份回合重建（从 session 分支重建 `TurnRecord[]`），避免两套口径。

**为什么能做到「不调 LLM」：packet 本身就是天生摘要。** 它在结算 pass——LLM 刚把整回合推理完、吐出结构化裁决的那个 context 峰值时刻——被产出，本是给渲染当导演指令，但它已蒸馏了 playerAction + resolvedChanges + 场景指令，天然就是该回合的持久摘要。于是下游全是它的确定性复用：渲染导演、压缩索引行、渲染历史 digest 层，同一份产物喂三个消费者，全程不存在第二次摘要，也就无从漂移。换句话：摘要只在「context 最饱满、意图最明确」的一刻发生一次，落进 packet；之后一切都是机械读取。这也反过来括出 packet 设计的一条隐含要求：packet 字段要足以独立重建该回合的裁决脉络，不能依赖 prose 才说得清。

## 渲染器历史：缓存友好分层

渲染 prompt 不要做「单条 user 字符串 + 滑动窗口 + 相对回合编号」——每回合首字节都变，provider prefix cache 永不命中。正确形态是 append-only 对话：

```txt
[digest 层 (user)]                  16-32 个旧回合，每回合一行，
                                    从该回合 packet 机械提取，零 LLM 成本，
                                    绝对回合编号，行内容永不重渲染
[逐回合 user(玩家输入)/assistant(定稿 prose) 对]
                                    全量层 6-12 回合；旧 prose 放 assistant 位，
                                    模型当成自己的声音
[final user(本回合输入 + packet)]
```

全量层边界用高低水位滞回（一次跳 6 回合，而不是每回合滑 1），prefix 每 ~6 回合才失效一次；再加字符预算提前降级超重旧回合。lint 重试用 base messages + assistant(draft) + user(violations) 的形态，复用首次调用的 prefix。缓存前缀稳定性既要单测钉死（同一水位桶内 `floor(n)` 恒定、桶内逐字节相等），也要能用逐 pass API 导出在 live 里核对——比对同桶内相邻回合 `passB` 的前缀是否逐字节一致。

## 工程细节

- prose 投递要等 agent idle 再写入，否则 custom message 触发自循环。
- 渲染是裸 stream，可以做伪流式预览改善等待体验。
- 审计脚本从 prose custom message 读渲染面，从 packet 读结算面，两面分开 lint。
- 先做 spike 验证 packet 接缝不损 prose 质感，拿到 GO 再正式接线。

## 压制渲染侧原生思维链（主要为削耗时）

Pass B 是纯 prose 生成，不需要长推理；但 thinking 模型在渲染回合会花大量时间生成原生思维链，拖慢首字节、括高成本。可直接借 SillyTavern「咩咩预设 ver 3.3.6」的「卡掉原生思维链」手法，让渲染跳过思考直接出正文：

- **prefill 闭合标签**：在模型回复槽前注入一个 assistant prefill（闭合的 `</think>` 类标签），模型以为思考已结束、直接跳进正文，省掉整段 CoT 生成时间。注入点放在渲染调用的唯一咽喉（覆盖首写 / lint 重试 / reroll），不动 base messages 构造，避免 reroll 的尾部 user 消息埋掉 prefill。

顺带收一个副作用：**防思维链泄漏**。OpenRouter / 第三方 Gemini relay / OpenAI-兼容代理会把思维摘要拍平进文本流，绕过 pi-ai 的 `isThinkingPart()` 路由，未被压住的链会泄进 Pass B prose；prefill 同时压住了这种泄漏。再加一道后处理 strip 兑付残留：

- **后处理 strip**：删掉任意位置的闭合 `<think>/<thinking>/<thought>` 块，以及代理回显 prefill 时的首部残留。未闭合的开标签不抖——strip 它会把悬空的链内容暴露成 prose；交由 underlength/坏味 lint 拦下空稿触发重写。

范围只限 Pass B（渲染 + lint 重试 + reroll）；Pass A 结算需要推理纪律，原生思维链是资产不动。这与「瘦身 prompt / 避免 checklist reasoning-bait」同一主题：都是在该快的环节刪减不必要的推理耗时。

## 接管压缩：结算 pass 的确定性索引

领域模型付清后（事实在 state、prose 连续性在渲染器自管窗口），旧结算回合没有不可替代信息。compaction 可以退化成确定性裁断索引，且**与渲染历史共用同一份回合重建**：一个纯函数从 session 分支重建 `TurnRecord[]`（玩家输入 + packet + prose），结算压缩与渲染历史都吃它，不要两套口径。压缩做**两层**而非单行：最近 N 轮保留**完整裁决脉络**（源 = 玩家输入 + packet 的 playerAction/resolvedChanges，与渲染 pass 选史对称；细节如 endWindow、binding NPC move、短 prose 摘录挂在该轮索引行下方），更早的回合各压成一行索引，整体封顶 M 行并显式声明丢弃指向 state。无 LLM、无 prompt 策略文件、即时、零成本、不漂移。摘要头部钉死合同：这是索引，state 才是真相。

两层格式要**自退化**：细节行用与索引行不同的行首前缀（如索引行 `- ` 开头、细节行不以 `- ` 开头），于是旧摘要被下一次 compaction 折叠时，只有索引行被机械识别保留，细节行自动降级消失——不需要任何「二次压缩」专门逻辑，前一份摘要（previousSummary）的折叠处理顺带完成梯度递降。用测试钉死「折叠后细节行不存活」。

通过 `session_before_compact` hook 接管手动 `/compact` 和自动 compaction，不要另设自定义命令。

设计期顺手接一个强制压缩演练开关（见 `validation.md` 的「可观测性开关」），把这条路径变成零成本可观测，而不是等长轮 soak 才偶遇：开关开时调低压缩预算 + 在**回合开始**（`before_agent_start`）触发 `ctx.compact()`，pi 在自身 loop 内同步跑完、headless `-p` 也落盘；压缩产物落 debug 目录便于核对（确定性索引头部钉死「state 才是真相」、近若干轮保留完整裁决脉络）。两个坑：预算要写进 launcher 经 `PI_CODING_AGENT_DIR` 重定向后 pi 真正读的那个 `settings.json`；`ctx.compact()` 是 fire-and-forget，回合末触发会赛跑 `-p` 退出而不持久化。

## 什么时候不拆

短跑卡、无秘密边界、对 prose 质量无硬要求——单段足够，省一次模型调用。拆分的成本是每渲染回合多一次调用 + packet 完整性硬依赖。
