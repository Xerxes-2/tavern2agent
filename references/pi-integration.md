# pi 集成契约

tavern2agent 是 pi-native。不要承诺跨平台。换 host 不是换胶水，而是重做 hook、tool schema、session state、subagent。

本文只写稳定契约；具体 API 以当前 pi 文档/类型为准。

## pi 负责什么

| 事项 | 契约 |
|---|---|
| 启动 | 项目根必须有 `start.sh` |
| prompt 注入 | extension 在 agent 启动前注入 GM prompt/动态提醒 |
| 工具 | 通过 pi tool API 注册；实现放 `tools/registry.ts` |
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
2. 注入 GM prompt / 动态上下文。
3. 调 `registerAllTools(pi)`。
4. 注册必要 session/state hooks。

不要在 `extension.ts` 内联工具实现。否则工具层无法测试和复用。

常见约束：

- 顶层 import，少用动态 import。
- 初始化放 hook，不依赖 top-level await。
- 路径用 extension 文件所在目录推导，不靠 cwd 猜。
- 环境变量集中读取，别散在工具里。

## Prompt 分层

不要把身份、世界书、工具说明、硬规则全塞 system。

推荐分层：

```txt
稳定身份/契约
参考上下文：世界摘要、数据入口、工具速查
玩家本轮输入
硬规则/本轮提醒：机械纪律、禁令、attention
```

原则：

- 硬规则靠近生成。
- 参考信息低优先级，别抢玩家输入注意力。
- 世界正文进 data + lookup，不进 prompt。
- 动态提醒按轮注入，不写回历史。
- role/位置按目标模型调；模型特化见 `references/models/`。

## 工具参数

工具参数用 pi 支持的 schema 方式声明。原则：

- 字段少而明确。
- enum 优先于自由字符串。
- description 写业务含义，不写废话。
- 不为旧参数长期保兼容；旧 state 交给 migration。

## 工具返回

返回必须让模型能直接读。稳定约定：

- `content` 放权威文本/JSON 摘要。
- `details` 放 TUI、日志、hook 用的结构化数据。
- 不要只把事实放 `details`。
- 错误要可读，并告诉 GM 下一步怎么做。

工具内部可返回结构化对象，但注册层要统一包装成 pi 可消费的 tool result。不要让每个工具各写一套格式。

## 工具 description

description 是模型是否调用工具的主入口。每个关键工具都写三段：

```txt
功能：一句话。

必须调用：
- 具体场景
- 具体场景

严禁：
- 凭记忆编造
- 绕过工具写具体数值/事实

职责：
- 你不是结果创造者；你把工具结果翻译成叙事。
```

读取类工具尤其要强：地点、NPC、价格、任务、战斗判定。否则强叙事模型会自己编。

## 机械层 / 叙事层

GM prompt 可用这个框架：

```txt
机械层：事实、数值、判定、状态变化，来自工具。
叙事层：把机械层结果写成场景。
未经工具确认的机械层内容不存在。
```

重点不是“多调工具”，而是“不调工具就没有这个事实”。

## 项目文件

```txt
.pi/settings.json       项目包声明
.pi/agents/*.md         子代理定义
agents/gm*.md           GM prompt 分层
skills/start-game/      开局 skill
tools/registry.ts       工具注册与实现入口
extension.ts            pi 注册入口
start.sh                启动入口
```

