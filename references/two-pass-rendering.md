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

## compaction 顺带解决

领域模型付清后（事实在 state、prose 连续性在渲染器自管窗口），旧结算回合没有不可替代信息。compaction 可以退化成确定性截断：每回合从 packet 机械提取一行（玩家输入摘录 + playerAction + resolvedChanges），与上次摘要的索引行折叠，封顶 N 行并显式声明丢弃指向 state。无 LLM、无 prompt 策略文件、即时、零成本、不会漂移。摘要头部钉死合同：这是索引，state 才是真相。

通过 `session_before_compact` hook 接管手动 `/compact` 和自动 compaction，不要另设自定义命令。

## 什么时候不拆

短跑卡、prompt-only、无秘密边界、对 prose 质量无硬要求——单段足够，省一次模型调用。拆分的成本是每渲染回合多一次调用 + packet 完整性硬依赖。
