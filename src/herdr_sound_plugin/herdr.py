"""调用 herdr 自身的 CLI：读取 config.toml 路径、校验配置、触发重载。

只做「被原生配置接管」这一步还需要的外部调用，不再涉及插件、pane、agent。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

# herdr 的常见安装位置，PATH 里找不到时按序兜底
FALLBACKS = ("~/.local/bin/herdr", "/usr/local/bin/herdr", "/opt/homebrew/bin/herdr")


def resolve_binary() -> str:
    """定位 herdr 可执行文件：`HERDR_BIN_PATH` > PATH > 常见安装位置。"""
    env = os.environ.get("HERDR_BIN_PATH")
    if env and os.path.exists(env):
        return env
    found = shutil.which("herdr")
    if found:
        return found
    for candidate in FALLBACKS:
        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return expanded
    raise FileNotFoundError("找不到 herdr 可执行文件，请设置 HERDR_BIN_PATH")


def call(*args: str, binary: "str | None" = None, timeout: float = 30.0) -> dict:
    """执行 `herdr <args...>` 并解析 JSON 输出。

    herdr 的 CLI 一律返回 `{"id":..., "result":{...}}` 信封，出错时进程非零退出。
    参数统一 str 化，免得调用处把 `--limit 200` 写成 int 让 subprocess 崩掉。
    """
    exe = binary or resolve_binary()
    proc = subprocess.run([exe, *map(str, args)], capture_output=True, text=True,
                          timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"herdr {' '.join(map(str, args))} 失败({proc.returncode}): "
                           f"{proc.stderr.strip() or proc.stdout.strip()}")
    text = proc.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def reload_config() -> "str":
    """让正在跑的 server 重新读 config.toml。

    服务器没在跑时 herdr 会非零退出（配置下次启动时自然生效），
    这里不当成错误，返回一句提示交给调用方展示。
    """
    try:
        result = call("server", "reload-config")
    except RuntimeError as exc:
        return f"herdr server 未在运行，配置将在下次启动时生效（{exc}）"
    status = result.get("result", {}).get("status", "unknown")
    return f"herdr server reload-config: {status}"
