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

packet 至少含：playerAction、resolvedChanges（所有落地的状态变化）、场景指示、eventWeight（节拍权重，映射到具体字数下限，见 `prompt-composition.md`）。

packet 里面向玩家的建议字段（如 suggestedActions 的 submitText）要用**无主语动作短语**：它会变成真正的玩家消息，固定主语（我/你）会和玩家角色身份或视角错配。

## Pass A 文本防火墙

结算侧（Pass A）只应产生工具调用和 direction packet；任何 assistant text 都不是玩家正文。要在两个位置清理泄漏：

- `message_end` / session entry 落盘时：工具调用 assistant message 若混入 text part，删 text、保留 thinking/tool call。
- prompt/context 注入时：已持久化的 Pass A 泄漏也要过滤，不能因为历史里已有就回灌给模型或玩家。

玩家可见 prose 只来自 Pass B 的 custom message（如 `xxx-prose`）。这条必须有测试：纯文本 assistant message（真正 meta 回复）不删；tool-call assistant 的 text 泄漏才删。

## 玩家选择 UI 生命周期

如果 packet 生成 suggestedActions / choice widget：

- UI 展示文本必须和真正提交的 user message 一致，不能只显示摘要而提交隐藏长串。
- turn_start 清空旧 widget，防止下一轮沿用 stale choices。
- reroll 时从新 prose / 新 packet 重新持久化 suggestedActions；隐藏 leaf、审计 entry、custom prose entry 不能让 reroll target 失效。
- suggestedActions 属于玩家界面提示，不是叙事正文；不要塞进 endWindow 或 prose。

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

全量层边界用高低水位滞回（一次跳 6 回合，而不是每回合滑 1），prefix 每 ~6 回合才失效一次；再加字符预算提前降级超重旧回合。lint 重试用 base messages + assistant(draft) + user(violations) 的形态，复用首次调用的 prefix。

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

## compaction 顺带解决

领域模型付清后（事实在 state、prose 连续性在渲染器自管窗口），旧结算回合没有不可替代信息。compaction 可以退化成确定性截断：每回合从 packet 机械提取一行（玩家输入摘录 + playerAction + resolvedChanges），与上次摘要的索引行折叠，封顶 N 行并显式声明丢弃指向 state。无 LLM、无 prompt 策略文件、即时、零成本、不会漂移。摘要头部钉死合同：这是索引，state 才是真相。

通过 `session_before_compact` hook 接管手动 `/compact` 和自动 compaction，不要另设自定义命令。

## 什么时候不拆

短跑卡、prompt-only、无秘密边界、对 prose 质量无硬要求——单段足够，省一次模型调用。拆分的成本是每渲染回合多一次调用 + packet 完整性硬依赖。
