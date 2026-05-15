# DeepSeek V4 特化指南

DeepSeek V4 的消息权重分配与 Claude/GPT 有根本性差异：**user message 的服从度远超 system message**。此外 V4 的 `reasoning_content`（思维链）存在已知的语言锚定缺失缺陷。迁移到 V4 时需要针对性的提示词编排和数据清理。

## 核心差异

| | Claude / GPT | DeepSeek V4 |
|---|---|---|
| system message 效力 | 强 | **弱**（尤其对创作/角色扮演类任务） |
| user message 效力 | 正常 | **强**（应承载所有核心规则） |
| 思维链语言控制 | system prompt 可控制 | **不可控**（已知缺陷，官方已确认） |
| 思维链切换触发 | 罕见 | **tool call 返回英文 → 一轮切换 → 99.4% 不可逆自锁** |

## 三刀流

迁移到 DeepSeek V4 时需要同时做三件事：

```
┌─────────────────────────────────────────────────┐
│ ① system prompt 极简                             │
│    只放角色身份（1-2句），不放规则                  │
├─────────────────────────────────────────────────┤
│ ② 规则搬到 user message 流                        │
│    注入到最后一条 user message 紧前面               │
│    → 注意力最高区域 + user role = 最强效力          │
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

### ② 规则注入 user message 流

在 pi 的 `extension.ts` 中通过 `context` 钩子实现：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const gmSystemPrompt = readFileSync(join(__dirname, "agents", "gm-system.md"), "utf-8");
const gmRules = readFileSync(join(__dirname, "agents", "gm.md"), "utf-8");

const RULES_USER_MESSAGE = {
  role: "user" as const,
  content: [{
    type: "text" as const,
    text: `[以下是你必须严格遵守的叙事规则——视为最高优先级指令]

${gmRules}

---
以上规则已加载完毕。请注意：
1. 上述所有规则（叙事风格、核心规则、角色设定、世界观等）均为硬性约束。
2. 你的思考过程和最终输出都请优先使用中文。`,
  }],
  timestamp: 0,
};

export default function extension(pi: ExtensionAPI) {
  // system prompt：只放极简身份
  pi.on("before_agent_start", async (event) => {
    return { systemPrompt: event.systemPrompt + "\n" + gmSystemPrompt };
  });

  // 每轮在最后一条 user message 紧前面注入规则（注意力最高区域）
  // context 钩子每次给 deep copy，修改不写入会话记录
  pi.on("context", async (event) => {
    const messages = [...event.messages];
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if ((messages[i] as any).role === "user") { lastUserIdx = i; break; }
    }
    if (lastUserIdx >= 0) {
      messages.splice(lastUserIdx, 0, RULES_USER_MESSAGE as any);
    }
    return { messages };
  });

  registerAllTools(pi);
}
```

**要点**：
- `context` 钩子每次给 deep copy，修改只影响当轮 API 请求，不污染会话历史（`.jsonl`）
- 注入位置：最后一条 user message **紧前面**，不是 context 开头——这样规则始终在注意力最高区域
- 每轮都注入（约 4KB），DeepSeek V4 的 1M 上下文 + cache hit 机制使 token 成本可忽略

### ③ 全链路中文化

这是解决思维链切换到英文的关键。污染链条是：

```
Tool 调用 → 返回英文内容（JSON 键名/代码）
→ 英文 token 占比越过阈值
→ 下一轮 reasoning_content 切英文
→ 英文 reasoning 被 API 强制回传（否则报错）
→ 自锁循环，99.4% 不可逆
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
// update_status 参数：全中文
parameters: Type.Object({
  stat: Type.Optional(Type.String({ description: "属性: 好感|魔力|堕落|情欲" })),
  stats: Type.Optional(Type.Record(Type.String(), Type.Number(), {
    description: "初始属性: { 好感, 魔力, 堕落, 情欲 }"
  })),
  presence: Type.Optional(Type.Record(Type.String(), Type.Unknown(), {
    description: "在场状态: { 内心想法, 当前动作, 状态, 已变身 }"
  })),
}),
```

#### 引擎层保持英文，工具层做单向映射

数据文件和引擎内部可以用英文键名（TypeScript 属性名），只需要在工具层做一次单向映射：

```typescript
// tools/registry.ts —— 单向映射，LLM 不可见
const TO_ENG = {
  好感: "Favor", 魔力: "Magic", 堕落: "Corruption", 情欲: "Lust",
  内心想法: "Thought", 当前动作: "Action", 状态: "State", 已变身: "isTransformed",
} as const;

// 使用时：
const eng = TO_ENG[params.stat as string] || params.stat;
updateCharacterStat(name, eng, delta);
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
