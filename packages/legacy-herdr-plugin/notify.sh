#!/usr/bin/env bash
# ============================================================================
# ⚠️ 已失效的归档代码 —— 不要使用，不要修改。
#
# 这是 herdr 插件方案的遗留实现，2026-10-06 被「直接改 herdr 原生配置」取代。
# 详见同目录 README.md。将来若需要，请重新实现，不要复活此处代码。
# ============================================================================
# 马里奥音效插件的事件钩子：订阅 pane.agent_status_changed，按状态播不同音。
#
#   任务完成 (agent_status=done)      -> sounds/<pack>/done.mp3
#   需要人工介入 (agent_status=blocked) -> sounds/<pack>/blocked.mp3
#   其他状态 (working/idle/unknown)    -> 静默返回
#
# 音色包由 HERDR_PLUGIN_STATE_DIR/pack 决定，用 `herdr plugin action invoke` 切换。
# 插件由 herdr server 侧执行并自行调 afplay，因此不依赖前端 client 是否在线。

set -u

status=$(printf '%s' "${HERDR_PLUGIN_EVENT_JSON:-}" \
  | sed -n 's/.*"agent_status":"\([a-z]*\)".*/\1/p')

case "$status" in
  done)    kind="done"    ;;
  blocked) kind="blocked" ;;
  *)       exit 0         ;;
esac

root=${HERDR_PLUGIN_ROOT:-$(cd -- "$(dirname -- "$0")" && pwd)}

pack=""
[ -n "${HERDR_PLUGIN_STATE_DIR:-}" ] && [ -f "$HERDR_PLUGIN_STATE_DIR/pack" ] \
  && pack=$(tr -d '[:space:]' < "$HERDR_PLUGIN_STATE_DIR/pack")
[ -n "$pack" ] && [ -d "$root/sounds/$pack" ] || pack="mario"   # 状态缺失或包名非法时回退

file="$root/sounds/$pack/$kind.mp3"
[ -f "$file" ] || exit 0

# 后台播放，避免阻塞钩子进程
nohup afplay "$file" >/dev/null 2>&1 &
disown
