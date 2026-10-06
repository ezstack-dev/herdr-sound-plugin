"""读写 herdr 的 config.toml，只碰 `[ui.sound]` 段。

herdr 自身没有 `config set` 子命令（`herdr config` 只有 `check` 与 `reset-keys`），
所以只能自己改 TOML。这里用 tomlkit 而不是标准库 tomllib：tomllib 只能读，
写回去会把用户的注释和排版全部抹掉。

`[ui.sound]` 的键（取自 `herdr --default-config`）：
    enabled      是否播放
    path         所有通知共用一个文件时的兜底
    done_path    任务完成
    request_path 需要人工介入
    [ui.sound.agents]  按 agent 开关（default / on / off）

音效路径写成相对 `config.toml` 所在目录的相对路径（herdr 就是这么解析的），
这样换机器、换用户名都不用改。
"""

from __future__ import annotations

import os
import pathlib

import tomlkit

SECTION = ("ui", "sound")


def config_path() -> pathlib.Path:
    """定位 herdr 的 config.toml。

    顺序：`HERDR_CONFIG_PATH` 环境变量 > `$XDG_CONFIG_HOME/herdr` > `~/.config/herdr`。
    """
    env = os.environ.get("HERDR_CONFIG_PATH")
    if env:
        return pathlib.Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = pathlib.Path(xdg).expanduser() if xdg else pathlib.Path.home() / ".config"
    return base / "herdr" / "config.toml"


def sound_dir(config: "pathlib.Path | None" = None) -> pathlib.Path:
    """音效文件目录：`<config.toml 所在目录>/sounds`（herdr 的约定）。"""
    return (config or config_path()).parent / "sounds"


def read(config: "pathlib.Path | None" = None) -> dict:
    """读整份配置。文件不存在时返回空表（herdr 会用内置默认值）。"""
    path = config or config_path()
    if not path.exists():
        return {}
    return dict(tomlkit.parse(path.read_text(encoding="utf-8")))


def sound_section(doc, create: bool = False):
    """取 `[ui.sound]` 表；`create=True` 时不存在则就地创建。"""
    node = doc
    for key in SECTION:
        child = node.get(key)
        if child is None:
            if not create:
                return None
            child = tomlkit.table()
            node[key] = child
        node = child
    return node


def get_sound(config: "pathlib.Path | None" = None) -> dict:
    """读 `[ui.sound]` 段；没有该段时返回空 dict。"""
    return dict(sound_section(read(config)) or {})


def set_paths(done: str, request: str, enabled: bool = True,
              config: "pathlib.Path | None" = None) -> pathlib.Path:
    """写入 `done_path` / `request_path` / `enabled`，其余内容原样保留。

    返回被修改的配置文件路径。
    """
    path = config or config_path()
    doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    section = sound_section(doc, create=True)
    section["enabled"] = enabled
    section["done_path"] = done
    section["request_path"] = request
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return path


def unset(config: "pathlib.Path | None" = None) -> pathlib.Path:
    """把本工具写入的键清掉，恢复成 herdr 的默认行为（只留 `enabled = false`）。"""
    path = config or config_path()
    if not path.exists():
        return path
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    section = sound_section(doc)
    if section is not None:
        for key in ("done_path", "request_path", "path"):
            section.pop(key, None)
        section["enabled"] = False
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return path
