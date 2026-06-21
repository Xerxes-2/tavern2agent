# Prompt 预设组织

SillyTavern 预设最值得迁移的是它的 **prompt composition model**：模块可开关、顺序可调、位置明确、最终输出合同靠近生成。pi 项目不要把这些组织关系写死进 TypeScript；应把它们做成可编辑 preset manifest。

在 v2 中，这一层叫 prompt orchestrator：它是 Runtime Plan 的 view/compiler backend。它吃结构化 IR、Runtime Plan、event pack prompt fragment 和 state projection，输出 prompt bundle；它不维护领域正确性，不读写 canonical state，也不兼容旧字段。

## 核心原则

- prompt 是按职责编排的模块图，不要堆成一坨 system。
- TypeScript 只做 preset/orchestrator 解释器：读 Runtime Plan 和 manifest、校验 schema、解析 source、按 slot 注入。
- preset manifest 和 `.md` 模块默认每轮重新读取，避免调参时重启 session；只有稳定 system 身份层可以启动时固定。
- prompt 作者只改 manifest 和 `.md` 模块，不改 engine / reducer。
- 世界事实、大数据和状态仍在 data / lookup / engine；prompt 只管阅读滤镜、工具纪律、叙事渲染和输出合同。
- event pack 可以贡献 tool-policy / render 片段，但不能把领域不变量只写在 prompt 里。
- ST 变量 / prompt_order 的思想可以迁移；ST 宏语法、HTML 状态栏、强制 COT 标签默认不迁移。

## 推荐 slot

```txt
pre-history
  聊天历史之前。作为阅读滤镜：创作宪法、世界索引、输入协议、社交协议、文风、渲染规则。

conversation history
  原始对话历史。不要把最后一条 user 单独抽出来；完整历史应保持连续。

pre-response
  完整历史之后、最终合同之前。本轮运行时上下文：状态简报、工具策略、硬规则、故事 driver。

final-contract
  最后一层短输出闸门：只输出什么、禁止什么、格式/坏味限制、第一行要求。
```

`pre-response` 和 `final-contract` 位置相邻，但职责不同：

```txt
pre-response    给模型处理本轮的工作材料，可以较长。
final-contract  给模型最终输出的短硬门禁，必须简短。
```

## 推荐 manifest

```json
{
  "version": 1,
  "modules": [
    {
      "id": "creative-constitution",
      "enabled": true,
      "slot": "pre-history",
      "priority": 10,
      "header": "creative_constitution",
      "source": "agents/gm-creative-constitution.md"
    },
    {
      "id": "world-context",
      "enabled": true,
      "slot": "pre-history",
      "priority": 20,
      "header": "world_context",
      "source": "agents/gm-context.md"
    },
    {
      "id": "style-blacklist",
      "enabled": true,
      "slot": "pre-history",
      "priority": 45,
      "header": "style_blacklist",
      "source": "agents/gm-style-blacklist.md"
    },
    {
      "id": "tool-policy",
      "enabled": true,
      "slot": "pre-response",
      "priority": 20,
      "header": "tool_policy",
      "source": "agents/gm-tool-policy.md"
    },
    {
      "id": "output-contract",
      "enabled": true,
      "slot": "final-contract",
      "priority": 10,
      "header": "output_contract",
      "source": "agents/gm-output-contract.md"
    }
  ]
}
```

第一版只需要支持：

```txt
enabled: boolean
slot: pre-history | pre-response | final-contract
priority: integer
header: XML-ish tag name
source: agents/*.md | runtime:state-brief | runtime:event-pack:<id>
```

`runtime:event-pack:<id>` 只渲染该 pack 的工具纪律和叙事渲染提示；pack 的正确性仍由 tool normalizer、engine invariant 和 reducer 维护。

可选扩展留到后面：groups、conditions、assistant-prefill、ST preset import、module notes、preview UI。

## 模块拆分建议

从 ST 预设迁移时，优先提炼成这些 pi 模块：

```txt
agents/gm-creative-constitution.md  创作强调、禁止 meta、信息边界、场景推进底线
agents/gm-context.md                世界索引、可查询资料、世界书入口；不要塞工具速查
agents/gm-input-guide.md            用户输入可见性：台词、内心、OOC、自然语言动作
agents/gm-social-guide.md           本音与建前、NPC 行为、关系微动作
agents/gm-style-blacklist.md        坏味 linter：禁交付语、否定反转、作者总结、空泛氛围等
agents/gm-style.md                  文风基调、题材味、段落形态
agents/gm-render.md                 状态/工具结果如何压成身体、队形、关系负担
agents/gm-tool-policy.md            工具调用策略和禁区
agents/gm-story-driver.md           本轮内部 driver：玩家做了什么、NPC 想要什么、状态压到哪里
agents/gm-output-contract.md        最终短合同：只输出正文、禁交付语、禁分割线、坏句式限频
```

不要默认生成 `data/user.json`。酒馆作者通常把主角设定写在世界书、开局、状态栏或首轮对话里。迁移主角设定时优先考虑：

1. 世界书条目 / lookup data。
2. 开局 skill。
3. actor 初始 state。
4. memory 初始事实。
5. 可选 `agents/protagonist-lore.md` 普通 prompt module。

只有用户明确要求结构化主角档案时，才生成静态 profile 文件。

## 风格黑名单独立成模块

不要把坏味禁令散落在 `gm-style.md`、`gm-render.md` 和最终合同里反复讲。模仿 ST 的 `<style_blacklist>`，单独拆成短模块：

```txt
<style_blacklist>
- 禁用否定反转：先否定普通解释，再给高级解释。
- 禁用对照式排比：连续用「并非 / 而是 / 与其说」抬高语气。
- 禁用抽象名词定义：用哲学判断解释恐惧、邪恶、黑暗、命运、存在、希望。
- 禁用作者总结：替角色处境下定义，或把主题直接讲给玩家。
- 禁用交付语：好、好的、状态已经、现在为你写、以下是、那么。
- 禁用外部排版：Markdown 分割线、章节标题、括号旁白标注、评价式吐槽。
- 禁用空泛氛围和伪高潮句。
</style_blacklist>
```

原则：坏句式名称只出现一次，少举坏例，避免 prompt 自己反复激活坏味。替代方向写成可执行动作：感官写外界如何进入身体，情绪写身体/动作/停顿/视线，主题降级成身体/物件/视线三类现场痕迹。

## 输出合同要短而硬

最终合同不是规则说明书。它只管临门一脚：

```txt
- 第一行必须是场景内动作、感官、环境变化或角色台词。
- 禁止以「好」「状态已经」「现在为你写」「以下是」开头。
- 禁止 Markdown 分割线、章节标题、说明性引导语和交付式排版。
- 默认不用否定反转句；必要时最多一次。
- 至少让一个重要 NPC 用动作回应玩家或现场变化。
- 结尾停在具体行动窗口。
```

长规则放 `pre-history` 或 `pre-response`；短合同放 `final-contract`。

## 反坏味优先于追求美学

不要写「更细腻」「更轻小说」这种不可验收要求。把失败样本拆成可命名坏味：

```txt
交付语：好，状态已经建立，现在为你写……
报告句：当前目标、威胁提升、可选行动如下。
否定反转：先否定普通解释，再给高级解释。
作者总结：用旁白给角色处境下定义。
NPC 传感器：NPC 只播报情报，没有位置、动作和代价。
```

对应的迁移动作：

```txt
交付语       → final-contract 禁开头。
报告句       → render protocol 要求工具结果变成可感知后果。
否定反转     → style-blacklist 禁坏味；render/story-driver 提供物理过程或角色动作替代。
作者总结     → story-driver 要求降级成身体 / 物件 / 视线三类现场痕迹。
NPC 传感器   → direction packet 给重要 NPC binding `move` + voice guidance；render 要求位置、动作、上一事件代价。
```

## 长度要求要给具体地板

「重要场景写长一点」不可验收，渲染 prose 会系统性偏短。把节拍权重（如 eventWeight）映射到具体字数下限，写进输出合同，并让审计/lint 能查。

## 叙述禁令补充清单

除风格黑名单外，长跑实测出的叙述坏味：

- 伪菜单结尾：结尾连珠并列问句，变相选项菜单。
- 旁白记账：叙述者复述玩家推理过程或播报状态数值。
- 机械教学：在叙事里教玩家怎么操作系统。
- 报时器：直接报钟表数值；时间压力要叙述出来（光线、疏密、NPC 动作）。

## 模块写作本身也要 stop-slop

stop-slop 不只管输出 prose，也管 prompt 模块本身的文字：

- 删自报家门开场白（「This module defines/explains…」「本模块负责…」）——H1 标题已经命名了模块，开场白是纯噪声，还会被模型当口吻模仿。
- 删「Actively/主动地」这类拐杖副词。
- 模型可见文本（身份声明、tool label、玩家面板）不出现工程脚手架措辞：sandbox/framework/沙盒这类词换成世界内/叙事措辞（fsn：sandbox → directed-narrative engine，并点明「paced, GM-driven story system, not a free-roam world simulation」）。内部包名/目录/tool id/开发文档不动。

## 死模块要删

从未被 manifest 注入的 prompt 模块是负资产：独有检查项并入存活模块后删除文件。定期用 manifest 对账 `agents/*.md`。

## 测试建议

prompt composition 也要有 smoke tests：

- manifest schema valid。
- Runtime Plan 中引用的 event pack prompt fragment 都存在。
- source 文件存在，且只能读 `agents/*.md` 或已知 runtime source。
- 每轮重新读取 manifest / `.md` 模块，prompt 调参不需要重启 session。
- module id 唯一。
- 注入顺序符合 slot + priority。
- conversation history 保持连续，不拆最后一条 user。
- output contract 在最后。
- style blacklist 独立插入，且 prompt 本身没有反复示范禁用坏味。
- output contract 包含交付语 / 分割线禁令。

这类测试不能证明文笔好，但能防止 prompt 组织退化成不可控大坨。
