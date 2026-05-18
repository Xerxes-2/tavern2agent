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

跟迁移产物**完全正交**——装不装只影响 UI 层，不影响卡本身。所有方案都基于 pi 自己，回退扩展、状态文件照常工作。

### Tau —— pi 原生 web mirror（轻量）

```bash
pi install npm:tau-mirror
```

[GitHub](https://github.com/deflating/tau)。pi 扩展形态，自动跟着 pi 启动/退出，默认 3001 端口起一个浏览器镜像。terminal 和 browser 双向输入——你 zellij 里看输出、手机扫 QR 进同一 session 打字，无缝同步。

特别契合现有 SSH + zellij 工作流：

```
云服务器：pi 起，tau-mirror 自动起 → 3001 端口
你的 PC：zellij attach 看 terminal
你的手机：扫 QR 进浏览器，地铁上回一句
```

支持 voice input、PWA 装到手机、HTTP basic auth。**没用过但看上去最契合跑团的多设备/碎片时间游玩场景**——SillyTavern 用户最怀念的「手机继续聊」这件事 Tau 直接覆盖。

### PiClaw —— 自托管工作台（重型）

[GitHub](https://github.com/rcarmo/piclaw)。**不是** pi 扩展——是把 pi 包进一个独立的 web app（聊天 + 编辑器 + 终端 + 文件浏览器 + MCP + draw.io + VNC……），Docker 部署。

跟 Tau 的关键区别：

|  | Tau | PiClaw |
|---|---|---|
| 形态 | pi 扩展，单进程共生 | 独立 web app，bundle 了 pi |
| 安装 | `pi install` 一行 | Docker / 桌面包装器 |
| 目标 | 给现有 pi session 加 web 视图 | 整套自托管 AI 工作台 |
| 重量 | 轻 | 重 |
| 适合 | 多设备/手机访问 | 给非技术朋友/团队展示 |

如果只想要"手机能继续玩"，装 Tau。如果想把整个项目当一个可分享的 web 服务给别人用，PiClaw。

---

## 不强求但顺手的小习惯

- **每张卡开独立 git repo**——不要塞进同一个 monorepo。pi-rewind-hook 的 `refs/pi-rewind/store` 是 repo 级，多卡共仓会让 snapshot 历史互相污染
- **`./start.sh -p "..."` 一行测**——`-p` 是 print mode，发一条消息看 agent 回应就退，适合改完 prompt 快速回归
- **prompt 改动用 git tag 标志**——`git tag prompt-v2` 之类，回退时 `git checkout prompt-v1 -- agents/gm.md` 比翻 reflog 快
- **engine 改动配单元测试**——`engine/dice.ts` 这种纯函数模块直接 `npx tsx --test engine/dice.test.ts` 跑，比下场玩 5 轮才发现公式错快
