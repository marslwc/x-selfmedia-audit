#!/usr/bin/env bash
#
# X Self-Media Audit — 一键安装脚本
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/marslwc/x-selfmedia-audit/main/install.sh | bash
#
# 自定义安装位置:
#   curl -fsSL https://raw.githubusercontent.com/marslwc/x-selfmedia-audit/main/install.sh | SKILLS_DIR=~/my-skills bash
#
# 本地安装（已克隆仓库时）:
#   ./install.sh
#
set -euo pipefail

REPO_URL="https://github.com/marslwc/x-selfmedia-audit.git"
REPO_RAW="https://github.com/marslwc/x-selfmedia-audit/archive/refs/heads/main.tar.gz"
SKILL_NAME="x-selfmedia-audit"

# ---------- 输出样式 ----------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi

info()  { printf '%s\n' "${BLUE}▸${RESET} $*"; }
ok()    { printf '%s\n' "${GREEN}✓${RESET} $*"; }
warn()  { printf '%s\n' "${YELLOW}!${RESET} $*"; }
die()   { printf '%s\n' "${RED}✗ $*${RESET}" >&2; exit 1; }

printf '\n%s\n' "${BOLD}X Self-Media Audit · X 自媒体账号诊断${RESET}"
printf '%s\n\n' "${DIM}一个分析个人 X(Twitter) 账号的 Agent Skill${RESET}"

# ---------- 1. 确定安装目录 ----------
if [ -n "${SKILLS_DIR:-}" ]; then
  TARGET_ROOT="$SKILLS_DIR"
  info "使用指定的技能目录：${BOLD}$TARGET_ROOT${RESET}"
else
  TARGET_ROOT=""
  for candidate in \
    "$HOME/.workbuddy-ai/skills" \
    "$HOME/.claude/skills" \
    "$HOME/.codebuddy/skills"
  do
    if [ -d "$candidate" ]; then
      TARGET_ROOT="$candidate"
      break
    fi
  done

  if [ -z "$TARGET_ROOT" ]; then
    TARGET_ROOT="$HOME/.workbuddy-ai/skills"
    warn "未找到已有的技能目录，将创建：${BOLD}$TARGET_ROOT${RESET}"
  else
    info "检测到技能目录：${BOLD}$TARGET_ROOT${RESET}"
  fi
fi

TARGET_DIR="$TARGET_ROOT/$SKILL_NAME"
mkdir -p "$TARGET_ROOT"

# ---------- 2. 获取文件 ----------
# 仅当脚本确实是磁盘上的文件时才启用本地模式。
# 通过 `curl ... | bash` 管道执行时 BASH_SOURCE 为空，必须走远程克隆。
SELF="${BASH_SOURCE[0]:-}"
if [ -n "$SELF" ] && [ -f "$SELF" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
else
  SCRIPT_DIR=""
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/SKILL.md" ]; then
  # 本地模式：脚本和技能文件在一起
  info "本地安装模式"
  if [ "$SCRIPT_DIR" != "$TARGET_DIR" ]; then
    mkdir -p "$TARGET_DIR"
    cp -R "$SCRIPT_DIR/SKILL.md" "$SCRIPT_DIR/README.md" "$TARGET_DIR/" 2>/dev/null || true
    for d in references scripts assets; do
      [ -d "$SCRIPT_DIR/$d" ] && cp -R "$SCRIPT_DIR/$d" "$TARGET_DIR/"
    done
  fi
  ok "文件已就位"

elif command -v git >/dev/null 2>&1; then
  if [ -d "$TARGET_DIR/.git" ]; then
    info "检测到已有安装，正在更新…"
    git -C "$TARGET_DIR" pull --ff-only --quiet 2>/dev/null \
      && ok "已更新到最新版本" \
      || warn "更新失败（可能有本地修改），保留现有版本"
  else
    info "正在克隆仓库…"
    rm -rf "$TARGET_DIR"
    git clone --depth 1 --quiet "$REPO_URL" "$TARGET_DIR" \
      || die "克隆失败。请检查网络，或手动下载：$REPO_URL"
    ok "克隆完成"
  fi

elif command -v curl >/dev/null 2>&1; then
  info "未找到 git，改用下载压缩包…"
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  curl -fsSL "$REPO_RAW" -o "$TMP_DIR/pkg.tar.gz" \
    || die "下载失败。请手动下载：$REPO_URL"
  tar -xzf "$TMP_DIR/pkg.tar.gz" -C "$TMP_DIR"
  rm -rf "$TARGET_DIR"
  mv "$TMP_DIR/${SKILL_NAME}-main" "$TARGET_DIR"
  ok "下载完成"

else
  die "需要 git 或 curl 其中之一，请先安装。"
fi

# ---------- 3. 校验 ----------
[ -f "$TARGET_DIR/SKILL.md" ] || die "安装不完整：找不到 SKILL.md"

if command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
  PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
  ok "Python 检测到：$PY ($PYVER)"

  # 冒烟测试：脚本能否正常运行
  if "$PY" "$TARGET_DIR/scripts/x_audit.py" --demo >/dev/null 2>&1; then
    ok "体检脚本自检通过"
  else
    warn "体检脚本运行异常，可手动排查：python3 $TARGET_DIR/scripts/x_audit.py --demo"
  fi
  if "$PY" "$TARGET_DIR/scripts/monetization_check.py" --demo >/dev/null 2>&1; then
    ok "变现自检脚本通过"
  else
    warn "变现脚本运行异常，可手动排查：python3 $TARGET_DIR/scripts/monetization_check.py --demo"
  fi
else
  warn "未检测到 python3。技能主体可用，但两个脚本无法运行（建议安装 Python 3.8+）"
fi

# ---------- 4. 完成 ----------
printf '\n%s\n' "${GREEN}${BOLD}安装完成${RESET}"
printf '  位置：%s\n\n' "$TARGET_DIR"

printf '%s\n' "${BOLD}下一步${RESET}"
printf '  1. 重启你的 Agent（或重新加载技能）\n'
printf '  2. 对它说：%s\n' "${BOLD}帮我诊断一下我的 X 账号${RESET}"
printf '  3. 把 handle 和最近 10–20 条帖子的数据发过去\n\n'

printf '%s\n' "${DIM}先看效果（无需任何数据）：${RESET}"
printf '  python3 %s/scripts/x_audit.py --demo\n\n' "$TARGET_DIR"
