# 产出校验

## 残留检测

```bash
# 一行 grep 扫残留
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留，逐条核对" || echo "✓ 无残留"
```

> 以下字段出现在 `engine/state.ts` / `engine/types.ts` 中且**用于本卡游戏逻辑**（非照抄 Re:0 示例），属于合理命中：`魔女残香`、`死亡回溯计数`、`is_changed_chapter`、`好感度`、`生命值`、`魔法值` 等。仅当出现在**非 Re:0 的卡**中时才需核查。

```bash
# Re:0 特有字段核查
grep -rnE "魔女残香|死亡回溯计数|is_changed_chapter" agents/ engine/ data/ 2>/dev/null
```

逐条核对：是本卡 schema 定义的字段 → 保留；是 ts-engine.md 的 Re:0 例子照搬 → 重写。

## 人工检查清单

- [ ] `agents/gm.md` 核心规则 ≤5 条
- [ ] 如有游戏系统则 `agents/narrator.md` 存在且 `tools: []`
- [ ] engine 模块覆盖 MVU 计算规则
- [ ] state schema 与 MVU 变量定义一致
- [ ] 角色数据按需拆分到 `data/characters.json`（≥5 个角色时）
- [ ] `first_mes` 的 HTML/状态面板已剥离，纯叙事（或合成叙事）内联到 `skills/开局.md`
- [ ] `skills/开局.md` 已生成，且正确反映 user 卡/设置需求
- [ ] 需要 user 卡时 `data/user.json` 已生成（含已知字段，缺失字段标注 `"TODO"`）
- [ ] `[initvar]` 已被读取并转化为 `INITIAL_STATE`（如有）
- [ ] `tavern_helper.scripts` 中 Zod 脚本已被提取（如有）
- [ ] `tavern_helper.scripts` 中游戏系统脚本已被处理（如有）
- [ ] `regex_scripts` 中的游戏数据已被提取（如有）
- [ ] 章节剧情模板未全量注入 prompt（如有）

---

# SDK 自动化测试（推荐）

人工检查清单只能验证"文件是否存在、是否残留 ST 痕迹"，无法回答核心问题：**GM 真的会按开局 skill 逐项收集角色信息吗？工具调用链路通不通？state 是否正确写入？**

SDK 测试脚本用一个**程序化玩家**走完整条交互链路，秒级得到答案。

## 原理

`pi -e extension.ts` 启动后，pi CLI 内部做的事可以拆解为三个 SDK API：

```
createAgentSession()   ← 加载 extension/skills/tools，等价于 pi -e
    │
session.subscribe()    ← 捕获 text_delta / tool_execution_end，等价于 TUI 渲染
    │
session.prompt("...")   ← 发送玩家输入，等价于键盘输入
```

测试脚本就是**去掉了 TUI、用硬编码对话序列替代键盘输入的最小化 pi CLI**。

## 最简测试脚本

```typescript
// test_play.ts — 放在项目根目录
import {
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

// 1. 加载 extension
const resourceLoader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  additionalExtensionPaths: ["./extension.ts"],
});
await resourceLoader.reload();

const { session } = await createAgentSession({
  resourceLoader,
  sessionManager: SessionManager.inMemory(), // 测试用，不落盘
});

// 2. 实时看到 GM 输出
session.subscribe((event) => {
  if (event.type === "message_update"
      && event.assistantMessageEvent.type === "text_delta") {
    process.stdout.write(event.assistantMessageEvent.delta);
  }
});

// 3. 逐轮发送玩家输入
async function say(text: string) {
  console.log(`\n📤 玩家 > ${text}\n`);
  await session.prompt(text);
  console.log("\n" + "─".repeat(60) + "\n");
}

await say("开始游戏");
await say("佐藤花音");       // 姓名
await say("女");              // 性别
await say("19");              // 年龄
await say("日本");            // 国籍
await say("东京");            // 所在地
await say("8万");             // 财务状况
await say("地下Live偶像路线"); // 出道路线
// ... 其余开局项
```

运行：`npx tsx test_play.ts`

**前提**：项目根目录已 `npm install`（package.json 依赖 `@earendil-works/pi-coding-agent`），且 `~/.pi/agent/auth.json` 中有可用 API key。

## 进阶：断言式测试

```typescript
import { deepGet } from "./engine/state.js";

// 监听工具调用
const toolCalls: string[] = [];
session.subscribe((event) => {
  if (event.type === "tool_execution_start") {
    toolCalls.push(event.toolName);
  }
});

await say("开始游戏");

// 断言：GM 调用了 idol_update 写入角色状态
assert(toolCalls.includes("idol_update"), "GM 必须调用 idol_update 初始化状态");

// 断言：state 中姓名已正确写入
const name = deepGet("个人信息.姓名");
assert(name === "佐藤花音", `姓名应为 佐藤花音，实际为 ${name}`);

// 断言：初始日期已设置
const date = deepGet("世界状态.日期");
assert(typeof date === "string" && date.length > 0, "日期不应为空");
```

## 可测项目清单

| 测试维度 | 检测方式 | 关键断言 |
|---------|---------|---------|
| **开局 skill 加载** | 第一轮 prompt 观察 GM 是否逐项提问 | GM 响应含「角色创建」或逐项清单 |
| **逐项收集流程** | 连续发送单项回答，观察 GM 是否继续下一项 | 每轮 GM 只问一个问题，不跳项 |
| **idol_update 调用** | 订阅 `tool_execution_start` | `idol_update` 至少被调用一次 |
| **state 写入正确性** | `deepGet()` 检查各路径 | 姓名/性别/年龄/所在地等与输入一致 |
| **开场叙事质量** | 观察 setup 完成后的 GM 输出 | 含时间/地点/情景，不裸露数值 |
| **经济引擎** | 发帖/事件后调用 `idol_post_engagement` 等 | 工具被调用，返回合理数值 |
| **narrator 子代理** | 检查 `narrator.log` 是否生成 | 文件存在且内容非空 |
| **narrator 不调工具** | narrator subagent 的 tool calls | `tools: []`，工具调用列表为空 |
| **状态持久化** | 退出后重新 `getState()` 读取 | state 文件存在且内容与上次一致 |
| **无 ST 残留** | grep 检查 | 无 `UpdateVariable`、`<%_`、`__结束__` 等 |

## 与 grep/人工检查的对比

| | grep 残留检测 | 人工清单 | SDK 自动化测试 |
|---|:---:|:---:|:---:|
| 检测文件存在 | ✓ | ✓ | ✓ |
| 检测 ST 残留字符串 | ✓ | — | ✓（可并入断言） |
| 验证工具调用链路 | — | — | ✓ |
| 验证 GM 行为（逐项提问等） | — | — | ✓ |
| 验证 state 写入正确性 | — | — | ✓ |
| 发现 LLM 幻觉（GM 自行编造状态） | — | — | ✓ |
| 速度 | 秒级 | 分钟级 | 分钟级（含 LLM 调用） |
| 可复现 | ✓ | — | ✓ |

**结论**：grep → SDK 测试 → 人工精查，三层递进。SDK 测试填补了「GM 真的按规则运行了吗」这个最关键的空缺。
