# DeepSeek V4 特化指南

DeepSeek V4 的消息权重分配与 Claude/GPT 有根本性差异：**user message 的服从度远超 system message**。此外 V4 的 `reasoning_content`（思维链）存在已知的语言锚定缺失缺陷。迁移到 V4 时需要针对性的提示词编排和数据清理。

## 核心差异

| | Claude / GPT | DeepSeek V4 |
|---|---|---|
| system message 效力 | 强 | **弱**（尤其对创作/角色扮演类任务） |
| user message 效力 | 正常 | **强**（应承载所有核心规则） |
| 思维链语言控制 | system prompt 可控制 | **不可控**（已知缺陷，官方已确认） |
| 思维链切换触发 | 罕见 | **tool call 返回英文 → 一轮切换 → 实测复现率 99.4% 不可逆自锁**（GitHub issue #1255 的统计批次，见文末参考） |

## 三刀流

迁移到 DeepSeek V4 时需要同时做三件事：

```
┌─────────────────────────────────────────────────┐
│ ① system prompt 极简                             │
│    只放角色身份（1-2句），不放规则                  │
├─────────────────────────────────────────────────┤
│ ② 规则搬到 user message 流，按重要性分层注入        │
│    上下文（世界观/角色/工具）→ 用户消息上方           │
│    铁则（硬性规则/叙事规范）→ 用户消息下方            │
│    → 铁则离生成最近，注意力权重最高                  │
├─────────────────────────────────────────────────┤
│ ③ 全链路中文化                                    │
│    data/ JSON 键名、工具返回值、routes 数据          │
│    → 消灭英文 token 注入，不给思维链切换触发条件      │
└─────────────────────────────────────────────────┘
```

### ① system prompt 极简

```markdown
# agents/gm-system.md（新增，替代原 gm.md 的 system 角色）
你是「○○」世界的叙事者（GM）。你是冷峻克制的第三人称叙事者。
```

就两句话。不要放世界观、规则、角色列表、叙事风格——这些全搬到②。

> ⚠️ **system prompt 是追加而非替换**：返回 `{ systemPrompt: event.systemPrompt + "\n" + gmSystemPrompt }`，不要丢掉 pi 内置的 `event.systemPrompt`（含工具调用格式、上下文管理等核心指令）。如果替换掉它，模型将失去 function calling 所需的角色定义。

### ② 规则注入 user message 流（分层注入）

不是把所有规则无差别地塞到用户消息上方。要按**重要性分层**：上下文级放上方，铁则级放下方。

**原理**：DS V4 对消息流中越靠近模型输出的内容，注意力权重越高。用户消息下方（用户输入 → 模型生成）是整条链中注意力最高的区域。

```
...历史消息...
[CONTEXT_USER_MESSAGE]   ← 上下文（世界观/角色/工具）—— 低注意力区
[用户的最新消息]           ← 用户输入
[RULES_USER_MESSAGE]     ← 铁则（必须遵守的硬规则）—— 离生成最近，注意力最高
→ 模型开始生成
```

在 pi 的 `extension.ts` 中通过 `context` 钩子实现：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const gmSystemPrompt = readFileSync(join(__dirname, "agents", "gm-system.md"), "utf-8");
const gmContext = readFileSync(join(__dirname, "agents", "gm-context.md"), "utf-8");
const gmRules = readFileSync(join(__dirname, "agents", "gm.md"), "utf-8");

// 上下文消息：世界观/角色/工具等参考信息，放在最后一条用户消息上方
const CONTEXT_USER_MESSAGE = {
  role: "user" as const,
  content: [{ type: "text" as const, text: `[以下为世界观与参考信息]\n\n${gmContext}` }],
  timestamp: 0,
};

// 铁则消息：必须遵守的硬性规则，放在最后一条用户消息下方（离模型生成最近，注意力最高）
const RULES_USER_MESSAGE = {
  role: "user" as const,
  content: [{
    type: "text" as const,
    text: `[以下是你必须严格遵守的叙事铁则——视为最高优先级指令]\n\n${gmRules}\n\n---\n以上铁则已加载完毕。请注意：\n1. 上述所有规则（GM铁则、核心规则、叙事风格）均为硬性约束。\n2. 你的思考过程和最终输出都请优先使用中文。`,
  }],
  timestamp: 0,
};

export default function extension(pi: ExtensionAPI) {
  // system prompt：只放极简身份
  pi.on("before_agent_start", async (event) => {
    return { systemPrompt: event.systemPrompt + "\n" + gmSystemPrompt };
  });

  // 分层注入：上下文在上方，铁则在下方
  // context 钩子每次给 deep copy，修改不写入会话记录
  pi.on("context", async (event) => {
    const messages = [...event.messages];
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if ((messages[i] as any).role === "user") { lastUserIdx = i; break; }
    }
    if (lastUserIdx >= 0) {
      // 上下文 → 用户消息上方
      messages.splice(lastUserIdx, 0, CONTEXT_USER_MESSAGE as any);
      // 铁则 → 用户消息下方（此时用户消息已被推到 lastUserIdx + 1）
      messages.splice(lastUserIdx + 2, 0, RULES_USER_MESSAGE as any);
    }
    return { messages };
  });

  registerAllTools(pi);
}
```

**分层标准**：

| 层级 | 文件 | 内容 | 注入位置 |
|------|------|------|----------|
| 上下文 | `gm-context.md` | 世界观、角色一览、玩家机制、数据文件、工具列表、氛围素材库 | 用户消息**上方** |
| 铁则 | `gm.md` | GM铁则（7条态度准则）、核心规则（含 scribe 强制调用）、叙事风格 P0-P6 | 用户消息**下方** |

**要点**：
- `context` 钩子每次给 deep copy，修改只影响当轮 API 请求，不污染会话历史（`.jsonl`）
- 铁则注入到用户消息下方，这里的 token 距离模型生成最近，注意力权重最高
- 上下文放在上方，不跟铁则抢注意力——避免了「所有规则塞一起导致重要规则被稀释」的问题
- 每轮都注入（约 14KB），DeepSeek V4 的 1M 上下文 + cache hit 机制使 token 成本可忽略

### ③ 全链路中文化

这是解决思维链切换到英文的关键。污染链条是：

```
Tool 调用 → 返回英文内容（JSON 键名/代码）
→ 英文 token 占比越过阈值
→ 下一轮 reasoning_content 切英文
→ 英文 reasoning 被 API 强制回传（否则报错）
→ 自锁循环（GitHub issue #1255 实测复现率 99.4%）
```

**触发源是 tool call 注入的英文内容**，不是 system prompt。要系统性地消灭：

#### data/ JSON 全中文键名

```
改前（characters.json）：
{
  "星原樱": {
    "alias": "巫女大人",
    "appearance": "长发...",
    "speech_style": "声音轻柔...",
    "dark_note": "她的「正义」...",
    "initial_stats": { "Favor": 5, "Magic": 100, "Corruption": 0, "Lust": 0 }
  }
}

改后：
{
  "星原樱": {
    "别名": "巫女大人",
    "外貌": "长发...",
    "说话风格": "声音轻柔...",
    "暗面注记": "她的「正义」...",
    "初始属性": { "好感": 5, "魔力": 100, "堕落": 0, "情欲": 0 }
  }
}
```

**覆盖范围**：`characters.json`、`routes.json`、`world.json`、`user.json`——所有 agent 会 `read` 的数据文件。

#### 工具返回值中文化

```typescript
// get_status 输出：全中文键名
{
  "日期": "3月20日",
  "角色列表": {
    "星原樱": { "好感": 5, "魔力": 100, "堕落": 0, "情欲": 0 }
  },
  "在场角色": {
    "星原樱": { "状态": "平常", "动作": "进门", "已变身": false }
  }
}
```

#### 工具参数 schema 中文化

```typescript
// patch_state 参数：全中文
parameters: Type.Object({
  ops: Type.Array(Type.Object({
    op: Type.Union([Type.Literal("add"), Type.Literal("replace"), Type.Literal("remove")]),
    path: Type.String({ description: "JSON Pointer 路径，如 /角色列表/星原樱/好感" }),
    value: Type.Optional(Type.Unknown({ description: "（add/replace 时必填）要设置的值" })),
  })),
}),
```

#### 引擎层保持英文，工具层做单向映射

数据文件和引擎内部可以用英文键名（TypeScript 属性名），只需要在工具层做一次单向映射：

```typescript
// tools/registry.ts —— 路径映射，LLM 不可见
// LLM 传 path: "/角色列表/星原樱/好感" → 引擎内部用英文键名
const PATH_MAP: Record<string, string> = {
  "好感": "Favor", "魔力": "Magic", "堕落": "Corruption", "情欲": "Lust",
  "内心想法": "Thought", "当前动作": "Action", "状态": "State", "已变身": "isTransformed",
};

// patch_state execute 中：
const state = getState();
const mapped = params.ops.map(op => {
  const segments = op.path.split("/").filter(Boolean);
  return { ...op, path: "/" + segments.map(s => PATH_MAP[s] || s).join("/") };
});
patchState(mapped);
```

**不要做双语兼容**（同时接受中英文键名）。没用——用户不会切回英文，只会增加复杂度。

## 何时应用

| 信号 | 是否应用 |
|------|:---:|
| 目标模型是 DeepSeek V4（Pro 或 Flash） | ✅ 必须 |
| 卡片是角色扮演/叙事类（非纯工具调用） | ✅ 强推 |
| 目标模型是 Claude/GPT | ❌ 不需要（system prompt 效力足够） |
| 目标是 DeepSeek V3 / R1 | ⚠️ 部分适用（user message 偏重同样存在，但 reasoning 语言问题不同） |

## 已知限制

1. **`reasoning_content` 语言仍不完全可控**——DeepSeek 官方已确认这是产品缺陷（issue #1257），system/user prompt 对此层控制力天然弱。全链路中文化是最有效的缓解手段，但不能保证 100% 中文思维链。
2. **pi 内置 system prompt 仍为英文**——工具描述、guidelines 等由 pi 自动注入，无法修改。这是残余英文 token 的最大来源，但目前无法消除。
3. **每轮注入规则 ≈ 4KB token 开销**——DeepSeek V4 的 cache hit 机制可大幅降低实际成本，且 1M 上下文足够容纳。

## 参考

- [GitHub #1255](https://github.com/deepseek-ai/DeepSeek-V3/issues/1255) — reasoning 语言漂移的复现实验与根因分析
- [GitHub #1257](https://github.com/deepseek-ai/DeepSeek-V3/issues/1257) — DeepSeek 官方确认 `reasoning_content` 语言锚定缺失
- [Thinking Mode 官方文档](https://api-docs.deepseek.com/guides/thinking_mode) — tool calling 场景下 `reasoning_content` 回传要求
- 类脑社区 [三明月](https://discord.com/channels/1134557553011998840/1504799207394119893) 的 V4 提示词处理心得（2026-05）

## 社区实战经验（三明月 @ 类脑，2026-05）

以下经验来自社区实践者的大量测试，与上文「三刀流」策略高度一致，作为补充细化。

### 一、系统消息的干扰性

> 除了破限以外，就不要留任何系统消息。DS 的系统消息处理能力似乎很有限，在用户和助手对话之间掺系统消息更是干扰运行。

这与我们的「system prompt 极简」策略一致，但有更激进的推论：
- **不要在 user/assistant 对话流中间插入 system 消息**——会打断 DS 的对话连贯性
- 世界书条目如果在 ST 里是 system 角色，迁移时应**全部转为 user 角色**
- 唯一保留 system 的场景：破限/jailbreak 相关的一句身份声明

### 二、标签（tag/XML）的处理

> 标签内需要用 name、define 等标题对标签内容进行定义，哈基米和小克是会直接读标签名的，但是 DS 似乎容易单纯地把标签当做分割符号。

DS 不会像 Claude 那样自动从 `<tagName>` 解析语义。在 prompt 中使用 XML 风格标签时：
- 不要依赖标签名传达含义——DS 把它当纯分隔符
- 必须在标签**内部**用自然语言显式声明内容是什么（如「以下是世界观设定：」「以下是角色背景：」）
- 或者干脆不用标签，改用 Markdown 标题（`## 世界观`）——DS 对 Markdown 结构的理解明显优于 XML

### 三、文风控制：技巧体系 > 语料堆砌

> 提供可执行的方案效果显著优于直接塞一堆语料给模型借鉴。塞语料时最好配上指出你希望 AI 重点借鉴的写作技巧到底是什么，不然 DS 写出来的东西就是借点词放进它的八股里。

这是 DS V4 提示词工程中最高杠杆的发现。V4 有一套内置的「默认写作模板」（八股），单纯给语料只会让它从语料中借几个词塞进模板。要突破八股，需要提供**可执行的写作技巧体系**：

**有效的文风定义方式**：

| 维度 | 示例 | 说明 |
|------|------|------|
| 优先级排序 | 「最重要的：每句不超过 20 字；其次：比喻 > 白描；再次：少用形容词」 | DS 理解「最」「其次」的优先级语义，比大量并列的「必须/禁止」更不容易冲突 |
| 句长控制 | 「大量使用 5-12 字的短句，偶尔用 20 字以上长句制造节奏变化」 | 用「大量」「偶尔」等频率词，DS 自己会把握比例 |
| 技巧频率 | 「通感修辞每段落出现 1-2 次」「抽象词占比不超过 30%」 | 给出频率范围比「多用/少用」精确 |
| 词汇语调 | 「禁止轻小说吐槽语气」「冷感叙事，情感通过动作和环境表达」 | 用正反例定义语调边界 |

**反模式**（对 DS V4 低效）：
- 给一堆参考文本不标注技巧点 → 借词不借魂
- 大量并列的「必须 X」「禁止 Y」→ 优先级冲突时 DS 随机丢弃
- 抽象形容词（「写得有文学性」「有张力」） → DS 无法翻译成可执行动作

**对 GM prompt 的具体建议**：
- 把「叙事风格」部分从形容词列表改写为优先级排序的技巧指令
- 每条规则附带一个频率词（大量/偶尔/每个场景/禁止）
- 给出具体的反面示例（「不要这样写：xxx」）比抽象禁令有效得多
