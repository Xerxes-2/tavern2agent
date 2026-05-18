#!/usr/bin/env bash
# 启动脚本 —— 在转换产出的项目目录中运行
# 自动检测 pi、加载 extension.ts 并进入游戏，支持透传参数（如 --model）
set -euo pipefail

if ! command -v pi &>/dev/null; then
  echo "错误: pi 未安装，请先安装 pi coding agent" >&2
  echo "安装指引: https://github.com/earendil-works/pi-coding-agent" >&2
  exit 1
fi

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$(readlink -f "$0")")"

echo "启动《$(basename "$PWD")》..."
# 会话存档放在项目内，方便打包带走
mkdir -p ./sessions

# pi-rewind-hook 等回退扩展依赖 git 仓库——确保已 init（state/ 不要 .gitignore）
if [ ! -d .git ]; then
  git init -q
  echo "✓ 已初始化 git 仓库（回退扩展所需）"
fi

# -ne (--no-extensions): 禁用全局/项目自动发现的扩展，只加载本项目的 extension.ts
# -ns (--no-skills):    禁用全局/项目自动发现的技能，只加载 extension 注册的 skills/
# 如果你需要额外扩展或技能，去掉对应 flag 或在命令行显式加 -e/-skill 参数
exec pi \
  -e ./extension.ts \
  --session-dir ./sessions \
  -ne -ns \
  "$@"
