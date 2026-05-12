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

# SDK 交互测试（推荐）

人工检查清单只能验证"文件是否存在、是否残留 ST 痕迹"，无法回答核心问题：**GM 真的会按开局 skill 逐项收集角色信息吗？工具调用链路通不通？state 是否正确写入？**

答案只有一个办法：**真的进去玩一遍。**

## 核心原则：让 agent 替你玩

测试一个角色卡的最佳方式不是写死板脚本，也不是人肉手动点——而是**派另一个 agent 以玩家身份去玩**。

agent 作为玩家天然具备死板脚本没有的能力：
- **读** GM 的每一轮输出，理解当前情境
- **想** 作为玩家角色该如何回应（符合人设、推动剧情）
- **变** GM 措辞变化、问法不同时自动适应，不依赖正则
- **判断** GM 的行为是否合理（问了两个问题？跳过了某项？数值写错了？）

死板脚本盲打回答串、正则匹配不到就崩溃、`--print` 逐轮手动——都不需要。

## 实操：pi agent 下场玩

在卡片项目目录下，对 pi 说：

> 你作为玩家帮我测试一下这张卡，你 spawn 另一个 pi agent 作为 GM，你作为玩家和它交互

pi agent 会：
1. 用 SDK 创建 session，加载 extension
2. 订阅 GM 的流式输出，实时阅读
3. 以玩家身份逐轮回应——每轮都先读完 GM 问什么，再决定答什么
4. 角色创建完成后继续自由交互，验证游戏循环

这个过程等同于"真人玩家 + pi -e extension.ts"，但 agent 阅读更仔细、回应更一致、事后还能跑断言。

## SDK 骨架

agent 下场玩的时候，底层用的就是这个骨架。如果你需要可复现的 CI 测试，把它抽成脚本：

```typescript
// test_agent_play.ts
import {
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

const resourceLoader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  additionalExtensionPaths: ["./extension.ts"],
});
await resourceLoader.reload();

const { session } = await createAgentSession({
  resourceLoader,
  sessionManager: SessionManager.inMemory(),
});

// 等 GM 说完 → 返回本轮全部输出
function ask(text: string): Promise<string> {
  return new Promise((resolve) => {
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
    session.prompt(text);
  });
}

// agent 作为玩家，读 GM 输出后决定下一轮说什么
// 这里的"决定"由 agent 自己做——正则、状态机、硬编码回应表都不需要

let gmOutput = await ask("开始游戏");
// agent 读完 gmOutput，判断 GM 在问姓名 → 回答
let playerResponse = "佐藤花音";
gmOutput = await ask(playerResponse);
// agent 读完 gmOutput，判断 GM 在问性别 → 回答
playerResponse = "女";
gmOutput = await ask(playerResponse);
// ... agent 持续读→想→答，直到开场叙事完成
```

## 断言（可选）

交互完成后跑断言，验证 state 和工具调用链：

```typescript
import { deepGet } from "./engine/state.js";

const name = deepGet("个人信息.姓名");
console.assert(name === "佐藤花音",
  `姓名应为 佐藤花音，实际: ${name}`);

const date = deepGet("世界状态.日期");
console.assert(typeof date === "string" && date.length > 0,
  "日期不应为空");
```

## agent 玩 vs 其他方式

| | 人工玩 (`pi -e`) | 正则脚本 | agent 玩 |
|---|:---:|:---:|:---:|
| 读 GM 输出并理解 | 人脑 | 正则匹配 | ✓ agent 理解 |
| GM 措辞变化时适应 | ✓ | ✗ 崩溃 | ✓ 自动适应 |
| 一致性（不跳项、不重复） | 看人 | ✓ | ✓ |
| 可复现 | ✗ | ✓ | ✓ |
| 能判断 GM 行为是否合理 | ✓ | ✗ | ✓ |
| 能自由交互（非开局阶段） | ✓ | ✗ | ✓ |
| 零代码 | ✓ | ✗ | ✓（口头指令） |

**推荐流程**：口头指令让 pi agent 下场玩 → 发现问题就修 → 修完再让 agent 玩一遍。不需要正则、不需要状态机、不需要硬编码回应表。
