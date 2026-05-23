# 迁移后的卡片迭代

tavern2agent 把卡转出来只是起点。真正能玩、能打磨到位的版本，几乎都靠迁移完成之后的反复下场调整——改 GM prompt、补 engine 模块、改工具 description、加 NPC……本章讲怎么在这个阶段不乱来。

> 这是给**人**看的——迁移产物的维护者。agent 跑 skill 一次就结束，不参与日常迭代。

## 目录结构假设

迁移产物大致长这样：

```txt
my-card/
├── .git/                    ← 你自己的版本管理（可选但强烈建议）
├── .pi/settings.json         ← 项目级 pi 包，如 pi-subagents / powerline
├── agents/gm.md              ← 改 prompt 最频繁
├── engine/*.ts               ← 改公式、补模块
├── tools/registry.ts
├── data/world.json           ← 补设定
├── extension.ts
├── start.sh
├── sessions/                 ← pi 写入，玩家会话/存档；.gitignore
└── state/                    ← debug export / legacy fallback；.gitignore
```

## 推荐工作流

```txt
开发分支 dev 改代码
    ↓
./start.sh 下场玩
    ↓
不满意 → 停止当前 session / 切回旧 session 节点 / 恢复备份 → 改代码 → 再玩
满意    → commit 到 dev → merge 到 main
```

**关键纪律**：

- 下场玩之前最好 commit 一次，方便区分“代码改动”与“游玩产物”。
- `sessions/` 是玩家会话和状态快照，默认不进 git。
- `state/` 只是 debug export，不是真相源，默认不进 git；不要手动把它 commit。
- 不要把多个不同游戏共享同一个 `sessions/` 目录。

## session-backed state 的维护心智

轻量/标准方案的状态真相源是 **pi session custom entry**，不是 `state/state.json`。

```txt
session branch snapshot  →  in-memory state  →  state/state.json(debug export)
```

因此：

- 切换 session/tree/fork 后，扩展应从当前分支最近的状态快照恢复。
- `state/state.json` 只用来人工查看、debug、或旧文件存档首次导入。
- 如果某个旧分支没有状态快照，宁可报错/提示恢复备份，也不要自动写 `INITIAL_STATE` 污染存档。
- 如果从很老的文件存档恢复，先让迁移工具把它转成当前 schema，再继续游玩。

## 推荐 .gitignore

```gitignore
node_modules/
dist/
sessions/
state/
.pi/agent/
.pi/npm/

# 如果有跨周目永久记忆文件
meta/
```

发布包不要带：`sessions/`、`state/`、`.pi/agent/`、`.pi/npm/`、`node_modules/`。

## 增量改动的高频场景

### 改 GM prompt（agents/gm.md）

最常见。下场玩几轮觉得 GM 跑偏 → 改 prompt → 重启 `./start.sh`。**不需要迁移 state**——prompt 改动只影响后续轮，已经发生的 chat 不会变。

### 改 engine 公式（engine/*.ts）

中频。改完 **必须重启** pi（jiti 缓存 ts 模块）。改公式建议找一个清晰的测试节点重新跑，否则 session 里已写入的旧公式产物（已扣的 HP、已加的好感度）会污染验证。

### 加工具 / 改工具 description

低频但关键。加完后**主动下场触发一次**——很多模型不读新工具的 description 是因为压根没看到工具列表更新。重启 pi 即可。

### 增删 state 字段

如果 `INITIAL_STATE` / schema 改了：

1. bump schemaVersion。
2. 写 deterministic migration。
3. 加 fixture/test。
4. 让玩家通过 debug/setup toolset 调 `migrate_state`，不要靠运行时 fallback 猜字段。

不要为了省事让 runtime 同时读旧字段和新字段；那会让状态结构腐化。

## 重新跑 skill 增量更新

如果你想让 agent 帮你做较大改动（重做 engine、加多 agent 隔离等），可以再跑一次迁移 skill。

**告诉 agent**：「目标目录已经有迁移产物 + 我手改的内容，请增量更新，不要全量覆盖」。

agent 会按 SKILL.md §〇 的约束工作：先 diff 出你的手改、保留有意义的人工调整、只改它需要改的地方。

为了让这个过程更顺，自己先：

```bash
git checkout -b skill-rerun     # 开个新分支
git add -A && git commit -m "wip before rerun"
# 然后让 agent 跑
```

不满意 → `git checkout main`。

## 分支策略建议

- `main` — 稳定可玩版本
- `dev` — 当前在调的版本
- `experiment/<feature>` — 大改之前开新分支（如「加战斗系统」「重写好感度」）
- 模型差异调优：`tune/v4`、`tune/sonnet`——不同目标模型的 prompt 可能要分叉

## 不要做的事

- 跑游戏中途手改 `state/state.json`——它只是 debug export，且 agent 可能还在读写内存状态。
- 把 `state/` 重新加入 git——这会重新制造“文件状态”和“session 状态”两个真相源。
- 跨分支/跨版本长期共享 `sessions/`——代码 schema 变了而 session 仍是旧状态，容易需要 migration。
- 发布 `.pi/agent/auth.json`、`sessions/`、`state/`。
