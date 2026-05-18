# 迁移后的卡片迭代

tavern2agent 把卡转出来只是起点。真正能玩、能打磨到位的版本，几乎都靠迁移完成之后的反复下场调整——改 GM prompt、补 engine 模块、改工具 description、加 NPC……本章讲怎么在这个阶段不乱来。

> 这是给**人**看的——迁移产物的维护者。agent 跑 skill 一次就结束，不参与日常迭代。

## 目录结构假设

迁移产物大致长这样：

```
my-card/
├── .git/                    ← 你自己的版本管理
├── agents/gm.md             ← 改 prompt 最频繁
├── engine/*.ts              ← 改公式、补模块
├── tools/registry.ts
├── data/world.json          ← 补设定
├── extension.ts
├── start.sh
└── sessions/                ← pi 写入，可 .gitignore
```

## 推荐工作流

```
开发分支 dev 改代码
    ↓
./start.sh 下场玩
    ↓
不满意 → /fork 回退 → 改代码 → 再玩
满意    → commit 到 dev → merge 到 main
```

**关键纪律**：下场玩**之前** commit 一次。pi-rewind-hook 的 restore 会覆盖 worktree 里的 tracked / 非 ignored 文件，未 commit 的 WIP 会丢。

## git 与 pi-rewind-hook 的关系

两者共用 `.git/` 但**不冲突**：

| 你的 git 操作 | pi-rewind-hook |
|---|---|
| `git log` / `git status` / `git diff` | 看不见 rewind snapshot，完全干净 |
| commit / branch / rebase / stash | 不影响 rewind ledger（ledger 在 pi session 里） |
| `git push` | 默认只推 `refs/heads/*`，rewind 的 `refs/pi-rewind/store` 不上云 |
| `git gc` | 隐藏 ref 让 snapshot 对象保持 reachable，不会被 GC |

rewind 用 `refs/pi-rewind/store` 这个独立 ref 挂 snapshot commit，不动 HEAD、不动 index、不创建分支、不用 stash。

**唯一互动**：你 restore 时，工作树会被改回历史 snapshot——所以见上方「commit 一次再下场」。

## 推荐 .gitignore

```gitignore
# pi 写入的会话日志（每次下场玩都会变）
sessions/

# 跨回退持久的"永久记忆"（仅死亡循环类机制需要）
# pi-rewind-hook 会跳过 ignored 路径，刚好绕过整体回退
meta/
```

**不要**把 `state/` 加进去——游戏状态必须跟着 snapshot 一起回退，否则数值跟剧情对不上。

## 增量改动的高频场景

### 改 GM prompt（agents/gm.md）
最常见。下场玩几轮觉得 GM 跑偏 → 改 prompt → 重启 `./start.sh`。**不需要回退**——prompt 改动只影响后续轮，已经发生的 chat 不会变。

### 改 engine 公式（engine/*.ts）
中频。改完 **必须重启** pi（jiti 缓存 ts 模块）。改公式建议同时回退一段重测，否则 state 里残留的旧公式产物（已扣的 HP、已加的好感度）会污染验证。

### 加工具 / 改工具 description
低频但关键。加完后**主动下场触发一次**——很多模型不读新工具的 description 是因为压根没看到工具列表更新。重启 pi 即可。

### 增删 data 字段
若 `INITIAL_STATE` 改了 schema：老 `state/state.json` 会缺字段，导致 `replace` patch 静默失败。处理：删 `state.json` 重新开局，或写 migration 函数补字段。

## 仓库膨胀的清理

每回合一个 snapshot commit 长期会让 `.git/` 涨大。一两个月清一次：

```bash
git reflog expire --expire=30.days refs/pi-rewind/store
git gc --prune=30.days
```

清完 30 天前的 snapshot 就被回收。当前 session 的 ledger 还认的 snapshot 不会被清——retention 由 reachability 控制。

不想要历史回退能力可以直接：

```bash
git update-ref -d refs/pi-rewind/store
git gc --prune=now
```

清空所有 rewind 历史。pi-rewind-hook 重启后从零开始。

## 重新跑 skill 增量更新

如果你想让 agent 帮你做较大改动（重做 engine、加多 agent 隔离等），可以再跑一次迁移 skill。

**告诉 agent**：「目标目录已经有迁移产物 + 我手改的内容，请增量更新，不要全量覆盖」。

agent 会按 SKILL.md §〇 第 3 条的约束工作：先 diff 出你的手改、保留有意义的人工调整、只改它需要改的地方。

为了让这个过程更顺，自己先：

```bash
git checkout -b skill-rerun     # 开个新分支
git commit -am "wip before rerun"
# 然后让 agent 跑
```

不满意 → `git checkout main`。

## 分支策略建议

- `main` — 稳定可玩版本
- `dev` — 当前在调的版本
- `experiment/<feature>` — 大改之前开新分支（如「加战斗系统」「重写好感度」）
- 模型差异调优：`tune/v4`、`tune/sonnet`——不同目标模型的 prompt 可能要分叉

## 不要做的事

- 跑游戏中途手改 `state/state.json`——agent 还在读，并发写会出现奇怪状态
- 跨分支共享 `sessions/`——pi session 文件名含状态摘要，不同分支的代码读同一 session 会乱
- `git push origin refs/pi-rewind/*` 到公开仓——你的游玩存档没必要上 GitHub
- 删 `refs/pi-rewind/store` 之后期望 pi 里还能 `/fork` 到老节点——清了就是清了，session ledger 会找不到 commit
