# 工具与工作流推荐

迁移产物只是骨架，怎么舒服地跑起来取决于你的工作流。下面是一些值得装/试的工具，标注「已实测」是项目维护者亲测在用，「听说」是看上去契合但未亲测。

---

## 已实测

### SSH + zellij —— 远程持久化

跑游戏的最佳姿势是把 pi 放在云服务器上，本地 SSH 进去用 [zellij](https://zellij.dev/) 持久化 session。好处：

- 关电脑、断网、换设备都不丢上下文，回来 `zellij attach` 继续玩
- 多窗格：一个跑 `./start.sh`、一个 `viddy` 看 state、一个 vim 改 prompt
- 跨设备同步——手机 SSH 客户端也能临时回一两轮

替代品：tmux、screen。zellij 优势是默认快捷键友好、原生 layout 配置。

### viddy + jq —— 实时观察 state.json

[viddy](https://github.com/sachaos/viddy)（现代版 `watch`）+ jq 看 state 变化是验证 engine 真的在写入的最直观方法：

```bash
viddy -n 1 jq -C . state/state.json            # 每秒刷新整个 state（-C 强制 jq 输出颜色）
viddy -d jq -C .主角.生命值 state/state.json   # 只盯 HP，diff 高亮变化
```

**`-C` 必加**——jq 检测到管道会默认关闭颜色，不加这个 viddy 里就是一片白。`-d` 会高亮变化的字段，相当于免费的 "GM 真的改了吗" 验证。比 `tail -f` 看日志直观。

下场调试新 engine 模块时强烈推荐左半屏跑游戏、右半屏跑 viddy，一眼看出"agent 嘴上说扣血但 state 没动"的 bug。

### rpiv-ask-user-question —— 结构化交互

```bash
pi install npm:@juicesharp/rpiv-ask-user-question
```

[扩展仓库](https://github.com/juicesharp/rpiv-ask-user-question)。给 agent 加一个 `ask_user_question` 工具，弹出 tab 化对话框：单选/多选、Submit 前预览、"Other" 自由输入。

对跑团特别有用的场景：

- 开局 setup（性别/职业/难度选择）—— agent 不用一行一行问，一次弹出来选完
- 路线分支抉择 —— 多个选项 + 每个选项的预览描述
- 重大决策 —— 玩家不用打字，多选一个回车就行

把 `gm.md` 末尾加一行「重大选择请用 ask_user_question 工具呈现选项」，agent 自己就会用。

### pi-web-access —— 外部信息查询

```bash
pi install npm:pi-web-access
```

[扩展仓库](https://github.com/nicobailon/pi-web-access)。给 agent 加 web 搜索、URL 抓取、GitHub clone、PDF 提取、YouTube 转录等工具。

跑团用场景：

- GM 即兴需要查现实世界知识（"宋代官制是怎样的""量子隧穿原理"）—— 比让模型自己脑补准确得多
- 玩家说"我搜一下这个 NPC 的资料"—— agent 真的能查
- 迁移阶段也有用：让 agent 查角色卡里提到的某个真实文化背景

**注意**：跑虚构世界卡（自创设定）时，要在 `gm.md` 里说清"非现实题材禁止 web 查询，避免污染设定"，否则 agent 会把真实世界知识塞进虚构世界。

---

## 听说（未亲测）

### PiClaw —— Web 前端壳

[GitHub](https://github.com/rcarmo/piclaw)。把 pi 包成自托管 web 工作台（聊天 + 编辑器 + 终端 + 文件浏览器 + MCP），可 Docker 部署。

对跑团来说理论上更接近 SillyTavern 那种「聊天框 + 状态面板」的体验，门槛比 CLI 低。**但跟迁移产物正交**——装不装只影响 UI 层，不影响卡本身。如果想给非技术朋友演示卡的话可以试试。

---

## 不强求但顺手的小习惯

- **每张卡开独立 git repo**——不要塞进同一个 monorepo。pi-rewind-hook 的 `refs/pi-rewind/store` 是 repo 级，多卡共仓会让 snapshot 历史互相污染
- **`./start.sh -p "..."` 一行测**——`-p` 是 print mode，发一条消息看 agent 回应就退，适合改完 prompt 快速回归
- **prompt 改动用 git tag 标志**——`git tag prompt-v2` 之类，回退时 `git checkout prompt-v1 -- agents/gm.md` 比翻 reflog 快
- **engine 改动配单元测试**——`engine/dice.ts` 这种纯函数模块直接 `npx tsx --test engine/dice.test.ts` 跑，比下场玩 5 轮才发现公式错快
