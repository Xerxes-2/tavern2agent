# 设计原则

## 0. 引擎用 TS，探索脚本用 Python

引擎模块用 TypeScript——它是运行时逻辑，需要被 extension / MCP server import，零开销调用。
探索脚本（解包 PNG、浏览世界书条目）是一次性工具，用 Python 写更轻便。

```
engine/*.ts  →  TS（运行时，被 import）
scripts/*.py →  Python（一次性，CLI 调用）
```

## 1. agent 是程序本身

不要在 prompt 里写「你必须检查变量」「你必须输出更新指令」。agent 会自己调用工具、自己推理。你只需提供**工具**和**最小规则**。

agent 的核心能力是 **loop + meta**：查询状态 → 判断 → 掷骰 → 计算 → 更新 → 再判断 → 调 narrator。每一步都是真实工具调用，不是 LLM 脑补。不满意可以自我纠正、重新来。不要把逻辑写入 prompt——写成工具让 agent 自己调度。

## 2. 所有计算进引擎模块

骰子、伤害公式、属性修正、好感度区间——这些进 `engine/*.ts`。LLM 不应该做算术。

## 3. 状态必须事务化

使用事件溯源（Event Sourcing）：每次变更是一条不可变事件。支持回退到任意历史回合、支持死亡回溯（截断事件流到存档点 + 注入死亡事件）。

## 4. prompt 极简

```
# 世界名 — 角色设定

你是 xxx 世界的叙事者。核心原则：
- 视角/文风约束（2-3条）
- 关键规则（不超过5条）
- 可用工具提示
```

## 5. 砍掉一切「因为你无法自己判断所以我要告诉你」的东西

包括但不限于：强化思考链、MVU 更新规则、JSON Patch 格式、变量修改格式、`__结束__` 标记、角色强制输出格式、合理性审查独立模块。agent 不需要这些。

## 6. 叙事与调试分离

纯叙事写入 `narrator.log`，与 agent 工具调用记录分开；用户 `tail -f` 即得独立剧情窗口。具体钩子实现见 `multi-agent-architecture.md` 与 `platform-adapters.md`。

## 7. 数据文件按类型拆分，按需注入

不要把所有世界信息塞进 GM prompt。组织原则：
- `data/world.json` — 世界设定（地理、势力、种族、**系统规则**），每次注入。纯地理/势力卡 ≤5KB；大量常驻系统条目的卡自然膨胀到 20-30KB——规模由条目审计结果决定，不硬压体积
- `data/characters.json` — 角色数据（性格、背景、说话特点），仅在 GM 查 `re0_npc_detail` 时按需读取
- GM prompt 中的角色列表 — 只列角色名 + 一句话摘要（≤20 字/角色）
- 章节剧情模板 — 提取到 `data/chapters.json`，注册章节查询工具让 GM 按需加载当前章节；不要预注入 prompt
- `first_mes` 为前端 HTML 说明书时 — 合成文学性开场叙事，不要留空 `narrator.log`
- 开场白：生成 `skills/开局.md`，agent 首轮 call 它。详见 `references/setup.md`。
