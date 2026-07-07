# pi 集成契约

tavern2agent 是 pi-native。不要承诺跨平台。换 host 意味着重做 hook、tool schema、session state、subagent。

本文只写稳定契约；具体 API 以当前 pi 文档/类型为准。

## pi 负责什么

| 事项 | 契约 |
|---|---|
| 启动 | 项目根必须有 `start.sh` |
| prompt 注入 | extension 在 agent 启动前注入 GM prompt/动态提醒 |
| 工具 | 通过 pi tool API 注册；契约与实现在各工具文件，`tools/registry.ts` 只是清单 |
| skill 发现 | 项目 `skills/` 需要显式注册资源路径 |
| 存档 | pi session custom entry 是 state 真相源 |
| subagent | 走 pi-subagents；定义放项目 `.pi/agents/` |
| 项目依赖 | 写进 `.pi/settings.json`，不要要求玩家全局安装 |

## 启动脚本

迁移时从本仓库 `scripts/start.sh` 复制到项目根并保留可执行权限。

要求：

- 隔离项目级 pi 配置，避免污染用户全局环境。
- 自动处理项目依赖。
- 支持继续会话、指定模型、开发模式。
- 发布物不要包含 `.pi/agent/`、`.pi/npm/`、`sessions/`、`state/`。

不要在文档里复制一份 start.sh 逻辑；模板文件是唯一来源。

## extension.ts 边界

`extension.ts` 只做注册：

1. 注册项目 `skills/` 路径。
2. 通过 prompt orchestrator 注入 GM prompt / 动态上下文。
3. 调 `registerAllTools(pi)`。
4. 注册必要 session/state hooks。

不要在 `extension.ts` 内联工具实现。否则工具层无法测试和复用。

常见约束：

- 顶层 import，少用动态 import。
- 初始化放 hook，不依赖 top-level await。
- 路径用 extension 文件所在目录推导，不靠 cwd 猜。
- 环境变量集中读取，别散在工具里。

## Prompt 分层

不要把身份、世界书、工具说明、硬规则全塞 system。复杂 RP 项目应使用 prompt orchestrator + preset manifest 管理 prompt composition；详见 `references/prompt-composition.md`。编排器只渲染 Runtime Plan 和 state projection，不维护领域正确性。

推荐基础顺序：

```txt
pre-history：世界索引、输入协议、社交/文风/渲染滤镜
conversation history：原始对话历史，保持连续
pre-response：状态简报、工具策略、硬规则、本轮 driver
final-contract：短输出闸门
```

原则：

- 硬规则靠近生成；最终输出合同必须短而硬。
- 参考信息低优先级，别抢玩家输入注意力。
- 世界正文进 data + lookup，不进 prompt。
- prompt manifest 和 `.md` 模块应按轮读取，方便调参；稳定 system 身份层可启动时固定。
- 不要把最后一条 user 单独拆出来；完整 conversation history 应保持连续。
- role/位置按目标模型在下场测试中调整；不要预设某个模型专用规则。

## 工具参数

工具参数用 pi 支持的 schema 方式声明。原则：

- 面向 LLM 的高频工具：schema 只挡基本形状，避免复杂 `Type.Union` / enum literal 展开成不可恢复的 `anyOf` 错误；允许值写进 description，并在工具入口 assert/normalize。
- 工具入口显式做 `unknown → typed input` 窄化；错误用领域语言，列出允许值和下一步。
- engine/state schema 继续严格，canonical state 不为 LLM payload 放宽。
- 字段少而明确。
- 参数名只用 ASCII。部分 provider API 对非 ASCII 参数名直接报错；中文语义写进 description。
- enum 可用于低频 debug、内部 schema 或 state schema；不要把它当成 LLM-facing serde。
- description 写业务含义，不写废话。
- 不为旧参数长期保兼容；旧 state 交给 migration。
- 常规玩法工具提交 domain event，不暴露万能 `update_state`。

## 工具返回

返回必须让模型能直接读。稳定约定：

- `content` 放权威文本/JSON 摘要。
- `details` 放 TUI、日志、hook 用的结构化数据。
- 不要只把事实放 `details`。
- 错误要可读，并告诉 GM 下一步怎么做。

工具内部可返回结构化对象，但注册层要统一包装成 pi 可消费的 tool result。不要让每个工具各写一套格式。

### TUI 折叠渲染

LLM 需要完整 `content`，人类 TUI 不该被大块工具输出淹没。任何会返回多行正文的读取/快照工具（GM brief、lookup、memory list、session/audit 摘要）都应由 registry 统一附加 `renderResult`：

- 折叠态（ctrl-O 收起）：首条非空行 + 有效行数。
- 展开态（ctrl-O 展开）：完整 `content`，优先 Markdown 渲染。
- `details` 仍只放 TUI/日志/hook 结构化数据；不要把模型必须读的事实只放 `details`。
- 摘要提取做成纯函数并测试；Component 渲染胶水不必逐像素测试。
- 优先在 `tools/registry.ts` 单点附加共享 renderer，避免 30+ 工具逐个复制 `renderResult`。

这条来自实测：工具输出对 LLM 友好不等于对人友好；没有 `renderResult` 时 pi fallback 会把 GM brief / lookup 等整段摊开，ctrl-O 看不到有用摘要。

## 工具 description

description 是模型是否调用工具的主入口，但不是操作手册。每个关键工具收成紧凑三段：

```txt
一句话用途：这个工具改变/读取什么领域事实。

使用边界：何时用；相邻工具怎么分工；工具失败后下一步。

禁区：只列真会误用的行为，例如凭记忆编造、绕过工具写具体数值/事实、把 debug 工具当常规玩法。
```

不要写「必须调用：」/「严禁：」长清单标题；checklist 体例是 reasoning-bait，会诱导模型先复述规约再行动。读取类工具仍要明确边界：地点、NPC、价格、任务、战斗判定等 canonical facts 必须来自 lookup/领域工具。

## 机械层 / 叙事层

GM prompt 可用这个框架：

```txt
机械层：事实、数值、判定、状态变化，来自工具。
叙事层：把机械层结果写成场景。
未经工具确认的机械层内容不存在。工具确认的是 domain event / reducer 结果，不是 narrator 自称已更新状态。
```

纪律只有一条：不调工具，这个事实就不存在。

## Compaction 接管

长跑叙事 runtime 不要依赖默认 LLM compaction：它会丢领域事实、不确定、有成本。用 `session_before_compact` hook 接管手动 `/compact` 和自动 compaction，不要另设自定义命令。领域模型付清后（事实在 state、prose 在渲染器自管窗口），compaction 可退化成确定性截断索引，零 LLM 成本，见 `references/two-pass-rendering.md`。接管时**复用 pi 已在 `preparation` 算好的 `firstKeptEntryId` / `tokensBefore`，只替换 `summary` 字段**——不要自己重算保留边界，否则与 pi 的预算判断打架。会话 ≤ keepRecent+reserve 时 `prepareCompaction` 返回 undefined（“session too small”），接管逻辑要容这种空跑。

## 项目文件

```txt
.pi/settings.json       项目包声明
.pi/agents/*.md         子代理定义
agents/preset.json       prompt composition manifest
agents/gm-*.md           GM prompt 模块
skills/start-game/      开局 skill
tools/registry.ts       工具注册清单；契约与实现在各工具文件
extension.ts            pi 注册入口
start.sh                启动入口
```

