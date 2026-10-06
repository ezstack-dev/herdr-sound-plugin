"""与 herdr 交互的薄封装：读 pane 状态、切音色包、读插件日志。

只在开发/调试时使用（`uv run python -m herdr_sound_plugin.herdr ...`），
插件运行时（notify.sh / switch.sh）是纯 shell，不依赖本模块。

提供的能力：
  - `resolve_binary()`  找 herdr 可执行文件（HERDR_BIN_PATH 优先）
  - `call()`            调一个 herdr 子命令并解析 JSON 输出
  - `pane_status()`     查某个 pane 的 agent 状态
  - `use_pack()`        切换音色包
  - `wait_done()`       轮询等待 pane 进入 done（用于端到端验证）
  - `plugin_logs()`     读插件执行日志

同时也是一个可直接运行的调试脚本：
    uv run python -m herdr_sound_plugin.herdr status w1:p1
    uv run python -m herdr_sound_plugin.herdr pack zelda
    uv run python -m herdr_sound_plugin.herdr probe w1:p1 --pack mario
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

PLUGIN_ID = "mario-sound"  # 插件清单里的 id，改动清单时记得同步


def resolve_binary() -> str:
    """定位 herdr 可执行文件：环境变量 > PATH > 常见安装位置。"""
    env = os.environ.get("HERDR_BIN_PATH")
    if env and os.path.exists(env):
        return env
    found = shutil.which("herdr")
    if found:
        return found
    for candidate in (os.path.expanduser("~/.local/bin/herdr"),
                      "/usr/local/bin/herdr", "/opt/homebrew/bin/herdr"):
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("找不到 herdr 可执行文件，请设置 HERDR_BIN_PATH")


def call(*args: str, binary: "str | None" = None, timeout: float = 30.0) -> dict:
    """执行 `herdr <args...>` 并解析其 JSON 输出。

    herdr 的 CLI 一律返回 `{"id":..., "result":{...}}` 信封；出错时进程非零退出。
    """
    exe = binary or resolve_binary()
    proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"herdr {' '.join(args)} 失败({proc.returncode}): "
                           f"{proc.stderr.strip() or proc.stdout.strip()}")
    text = proc.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def pane_status(pane_id: str, **kw) -> str:
    """查 pane 的 `agent_status`（working/done/blocked/idle/unknown）。"""
    data = call("pane", "list", **kw)
    for pane in data.get("result", {}).get("panes", []):
        if pane.get("pane_id") == pane_id:
            return pane.get("agent_status") or "unknown"
    raise KeyError(f"没有这个 pane: {pane_id}")


def wait_done(pane_id: str, timeout: float = 90.0, interval: float = 1.0) -> "str | None":
    """轮询等待 pane 进入 done。返回最终状态；超时返回 None。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = pane_status(pane_id)
        except (RuntimeError, KeyError):
            status = ""
        if status == "done":
            return status
        time.sleep(interval)
    return None


def use_pack(pack: str, **kw) -> dict:
    """切换音色包（等价于 `herdr plugin action invoke <id>.use-<pack>`）。"""
    return call("plugin", "action", "invoke", f"{PLUGIN_ID}.use-{pack}", **kw)


def plugin_logs(limit: int = 20, **kw) -> "list[dict]":
    """读插件执行日志（最近 `limit` 条）。"""
    data = call("plugin", "log", "list", "--plugin", PLUGIN_ID, **kw)
    return data.get("result", {}).get("logs", [])[-limit:]


def _main(argv: "list[str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd, rest = args[0], args[1:]
    if cmd == "status" and rest:
        print(pane_status(rest[0]))
    elif cmd == "pack" and rest:
        print(json.dumps(use_pack(rest[0]), ensure_ascii=False))
    elif cmd == "logs":
        for entry in plugin_logs(int(rest[0]) if rest else 20):
            print(entry.get("log_id"), entry.get("action_id") or entry.get("event"),
                  entry.get("status"), entry.get("exit_code"))
    elif cmd == "packages":
        data = call("plugin", "action", "list", "--plugin", PLUGIN_ID)
        for action in data.get("result", {}).get("actions", []):
            print(action["action_id"], "|", action.get("title"))
    else:
        print(f"未知命令: {' '.join(args)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
