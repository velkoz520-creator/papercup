#!/usr/bin/env bash
# publish-public.sh — 把私有主仓的当前 main 快照发布到公开仓库
# 用法：cd 主仓任意位置 → bash scripts/publish-public.sh "快照说明（可选）"
#
# 设计（天天拍板 2026-09-06）：
#   私有主仓 = 完整历史 + 日常开发（papercup-private）
#   公开仓库 = 永远只有"当前版本快照"单个提交——git 历史不公开，
#   扫库脚本（gitleaks/trufflehog）无历史可扫，未来误提交也无法泄漏。
#   每次发布 = 用新快照覆盖公开仓的 main（force push，公开仓无历史包袱）。

set -euo pipefail

MSG="${1:-snapshot update $(date +%Y-%m-%d)}"
PUB_URL="https://github.com/velkoz520-creator/papercup.git"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ROOT="$(git rev-parse --show-toplevel)"
TOKEN="$(printf 'protocol=https\nhost=github.com\n' | git credential fill 2>/dev/null | grep '^password=' | cut -d= -f2)"
[ -n "$TOKEN" ] || { echo "✗ 取不到 git 凭证"; exit 1; }

# 1) 导出当前 main 的干净快照（.gitignore 保护的文件天然不在内）
# 注意：git -C 指定仓库目录；直接把 Windows 路径当 tree-ish 传给 git archive 会炸
git -C "$ROOT" archive HEAD | tar -x -C "$TMP"

# 发布隔离（09-09 立规矩：intimate 相关不进公开面）
rm -f "$TMP/packages/web-client/toy-test.html"
rm -f "$TMP/packages/realtime-core/device.py"
rm -f "$TMP/packages/realtime-core/test_device_markers.py"
rm -f "$TMP/docs/DEVICE-CONTROL.md"

# UI 资产隔离（09-16 天天拍板：美术不进公开面——真资产换占位图，声明随附）
rm -rf "$TMP/packages/web-client/assets"
cp -r "$ROOT/scripts/placeholder-assets" "$TMP/packages/web-client/assets"
cp "$ROOT/scripts/ASSETS-NOTICE" "$TMP/ASSETS-NOTICE"

# 2) 在快照里做 orphan 提交（无任何历史）
cd "$TMP"
git init -q
git add -A
git commit -q -m "papercup · PaiVoice Jester Edition — $MSG"
git branch -M main
git remote add origin "$PUB_URL"

# 3) 覆盖发布
git push --quiet --force origin main
echo "✓ 已发布快照到 $PUB_URL（单提交，无历史）"
