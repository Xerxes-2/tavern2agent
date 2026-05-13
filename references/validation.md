# 产出校验

## 残留检测

```bash
# 一行 grep 扫残留
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留，逐条核对" || echo "✓ 无残留"
```

> grep 命中范围仅限 ST 补丁残留（UpdateVariable、JSON Patch、`{{getvar:}}` 等模板语法）。游戏字段如 `生命值`、`魔法值`、`好感度`、`回溯次数` 等是合法的运行时状态，不在残留检测范围内。

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

# SDK 交互测试

grep 和人工清单只能验证"文件是否存在、是否残留 ST 痕迹"，回答不了核心问题：**GM 真的会按开局 skill 逐项收集角色信息吗？工具调用链路通不通？state 是否正确写入？**

答案是：**你下场去玩。**

## 你的角色

读到这里的你（pi agent）就是测试玩家。用户把卡交给你验证时，你的任务不是 grep、不是审阅文件——是**以玩家身份进入游戏，亲身走完交互链路**。

你作为玩家天然具备死板脚本没有的能力：
- **读**：看 GM 的每一轮输出，理解他问了什么、情境是什么
- **想**：构思一个合理的玩家角色（姓名、背景、目标），按人设回应
- **变**：GM 措辞变化、问法不同时自动适应，不依赖正则或硬编码
- **判**：GM 问了两个问题？跳过某项？数值写错了？你作为玩家能当场察觉

## 你怎么做

### 1. 创建 GM session

用 SDK 加载 extension（即转换产物中的胶水层，默认文件名为 `extension.ts`，放在项目根目录，负责加载 `agents/gm.md` 并注册工具），启动一个 GM agent：

```typescript
import {
  AuthStorage,
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  ModelRegistry,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

// 如果有自定义 models.json 或 auth.json，传入对应路径；否则用默认
const authStorage = AuthStorage.create();
const modelRegistry = ModelRegistry.create(authStorage);

const resourceLoader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  // 胶水层 extension 文件名取决于转换时生成的名字，通常为 extension.ts
  additionalExtensionPaths: ["./extension.ts"],
});
await resourceLoader.reload();

const { session } = await createAgentSession({
  resourceLoader,
  authStorage,
  modelRegistry,
  sessionManager: SessionManager.inMemory(),
});
```

### 2. 订阅 GM 输出，逐轮交互

每轮：等 GM 说完 → 读输出 → 想好回应 → 发送。循环直到开场叙事完成并进入自由交互。

```typescript
function ask(text: string): Promise<string> {
  return new Promise((resolve, reject) => {
    let output = "";
    const unsub = session.subscribe((event) => {
      if (event.type === "message_update"
          && event.assistantMessageEvent.type === "text_delta") {
        output += event.assistantMessageEvent.delta;
        process.stdout.write(event.assistantMessageEvent.delta);
      }
      if (event.type === "agent_end") {
        unsub();
        resolve(output);
      }
    });
    // prompt() 返回 Promise<void>，agent_end 事件在内部 resolve 前触发
    session.prompt(text).catch((err) => {
      unsub();
      reject(err);
    });
  });
}

// 开局
let gmOutput = await ask("开始游戏");

// 逐轮阅读 GM 输出，按 GM 的提问逐项回应
// 你在每一轮中：读完 gmOutput → 判断 GM 在问什么 → 以玩家身份回答
// 直到角色创建完成，GM 交付开场叙事并进入自由交互
```

### 3. 构造一个玩家角色

你需要在开局前想好一个玩家角色（姓名、背景、目标、出道路线等），确保能覆盖开局 skill 清单里的每一项。角色要有基本的合理性——不要刻意刁难 GM，但也不要用完美人设掩盖问题。

### 4. 交互中注意

- 观察 GM 是否**一轮内列完所有缺失项**并附默认值——逐项追问是 bug
- 第一次可直接回「开始」走默认；之后再单独跑一次手动改若干字段，验证 setup 接受局部覆盖
- GM 交付开场叙事时，检查是否包含时间/地点/具体情境（而非空洞的"新的一天开始"）
- 开场完成后，继续 2-3 轮自由交互，验证游戏循环不崩溃

### 5. 跑断言（可选）

交互完成后，检查 state 是否正确写入。注意 `engine/state.ts` 的公开 API 是 `getState()`（轻量方案）或 `getCurrentState()`（完整方案），而非内部的 `deepGet`：

```typescript
// 轻量 / 中等方案
import { getState } from "./engine/state.js";

const state = getState() as Record<string, unknown>;
console.assert((state as any).个人?.姓名 !== "待初始化", "姓名未写入");

// 完整方案（事件溯源）
// import { getCurrentState } from "./engine/state.js";
// const state = getCurrentState();
```

断言路径依据实际 state schema 调整，字段名从 `[initvar]` 和 `[mvu_update]` 条目中提取。

## 常见问题 & 你的判断

| 你观察到 | 结论 |
|---------|------|
| GM 第一轮没提开局 setup，直接开始叙事 | 开局 skill 未加载或未生效 |
| GM 把 setup 拆成多轮逐项追问 | 开局 skill 违反 setup.md 的「一轮内列完」原则 |
| GM 列出的清单漏了某项（如没问背景就结束 setup） | 开局 skill 清单生成时遗漏字段 |
| 用户说「开始」用默认值，GM 却追问细节 | 默认值机制未生效 |
| GM 开场叙事中裸露数值（如"粉丝+200"） | 叙事风格违反 gm.md 规则 |
| 自由交互第 2-3 轮 state 仍为初始值 | 状态更新工具未被调用 |

遇到任何问题，直接向用户报告，指出具体哪一轮、GM 说了什么、预期应该怎样。
