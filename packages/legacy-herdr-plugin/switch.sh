#!/usr/bin/env bash
# ============================================================================
# ⚠️ 已失效的归档代码 —— 不要使用，不要修改。
#
# 这是 herdr 插件方案的遗留实现，2026-10-06 被「直接改 herdr 原生配置」取代。
# 详见同目录 README.md。将来若需要，请重新实现，不要复活此处代码。
# ============================================================================
# 音效包管理：设置 / 查看当前音色包。
#
# 用法（由 herdr 传入，无需手工参数）：
#   herdr plugin action invoke mario-sound.list-sounds
#   herdr plugin action invoke mario-sound.use-mario
#
# 当前包名记在 HERDR_PLUGIN_STATE_DIR/pack，notify.sh 每次触发时读取。

set -u

root=${HERDR_PLUGIN_ROOT:-$(cd -- "$(dirname -- "$0")" && pwd)}
state=${HERDR_PLUGIN_STATE_DIR:-"$root/.state"}
packs=()
for dir in "$root"/sounds/*/; do
  [ -d "$dir" ] && packs+=("$(basename "$dir")")
done

current=""
[ -f "$state/pack" ] && current=$(tr -d '[:space:]' < "$state/pack")

action=${HERDR_PLUGIN_ACTION_ID:-list-sounds}
if [ "$action" = "list-sounds" ]; then
  echo "Available sound packs (current: ${current:-mario}):"
  for p in "${packs[@]}"; do
    [ "$p" = "$current" ] && mark=" *" || mark=""
    echo "  $p$mark"
  done
  echo
  echo "Switch: herdr plugin action invoke mario-sound.use-<pack>"
  exit 0
fi

pack=${action#use-}
if [ ! -d "$root/sounds/$pack" ]; then
  echo "Unknown sound pack: $pack (available: ${packs[*]})" >&2
  exit 1
fi
mkdir -p "$state"
printf '%s\n' "$pack" > "$state/pack"
echo "Switched sound pack: $pack"
