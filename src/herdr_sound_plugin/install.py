"""把音色包落到 herdr 侧：copy 音频文件 + 改 config.toml。

为什么是 copy 而不是直接指向包内路径：包安装在 venv 里，venv 重建、`uv tool
upgrade`、换 Python 版本都会让那个绝对路径失效，而 herdr 配置是长期驻留的。
copy 一份到 `~/.config/herdr/sounds/` 之后，配置里写的是相对路径，怎么升级都不受影响。
"""

from __future__ import annotations

import pathlib
import shutil

from . import config as cfg
from . import packs


def bundled_sounds() -> pathlib.Path:
    """包内自带的音效目录（`uv_build` 会把 `src/<包>/` 下所有文件打进 wheel）。"""
    return pathlib.Path(__file__).resolve().parent / "sounds"


def source_file(pack: str, kind: str) -> pathlib.Path:
    """取包内某个音效文件；包名或用途非法时抛 KeyError。"""
    packs.notes_of(pack, kind)  # 校验 pack / kind
    path = bundled_sounds() / pack / f"{kind}.mp3"
    if not path.exists():
        raise FileNotFoundError(f"包内缺少音效文件：{path}")
    return path


def rel_path(pack: str, kind: str) -> str:
    """配置里写的相对路径（相对 config.toml 所在目录）。"""
    return f"sounds/{pack}/{kind}.mp3"


def copy_sounds(pack: str, config: "pathlib.Path | None" = None) -> "dict[str, pathlib.Path]":
    """把某个包的音效 copy 到 herdr 的 sounds 目录，返回 `{kind: 目标路径}`。"""
    root = cfg.sound_dir(config)
    out = {}
    for kind in packs.KINDS:
        target = root / pack / f"{kind}.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file(pack, kind), target)
        out[kind] = target
    return out


def use(pack: str, config: "pathlib.Path | None" = None) -> dict:
    """切换音色包：copy 音效 + 写 `[ui.sound]`。返回落盘结果摘要。"""
    if pack not in packs.PACKS:
        raise KeyError(pack)
    config = config or cfg.config_path()
    copied = copy_sounds(pack, config)
    cfg.set_paths(done=rel_path(pack, "done"),
                  request=rel_path(pack, "blocked"),
                  enabled=True, config=config)
    return {"pack": pack, "config": config, "files": copied,
            "done_path": rel_path(pack, "done"),
            "request_path": rel_path(pack, "blocked")}


def current_pack(sound: "dict | None" = None) -> "str | None":
    """从 `[ui.sound]` 反推当前用的是哪个包；认不出来返回 None。"""
    section = sound if sound is not None else cfg.get_sound()
    if not section.get("enabled"):
        return None
    done = str(section.get("done_path") or "")
    # "sounds/<pack>/done.mp3" → "<pack>"
    parts = pathlib.PurePosixPath(done).parts
    if len(parts) == 3 and parts[0] == "sounds" and parts[1] in packs.PACKS:
        return parts[1]
    return None


def installed_packs(config: "pathlib.Path | None" = None) -> "list[str]":
    """已经 copy 到 herdr 侧的音色包（按其 sounds/ 子目录判断）。"""
    root = cfg.sound_dir(config)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and p.name in packs.PACKS
                  and all((p / f"{k}.mp3").exists() for k in packs.KINDS))


def uninstall(config: "pathlib.Path | None" = None) -> "list[pathlib.Path]":
    """关闭音效并删掉本工具 copy 过去的目录。返回被删掉的目录列表。

    只删 `sounds/<包名>/` 这种本工具自己造出来的目录，不动 herdr 原有的文件。
    """
    config = config or cfg.config_path()
    removed = []
    root = cfg.sound_dir(config)
    for pack in installed_packs(config):
        target = root / pack
        shutil.rmtree(target)
        removed.append(target)
    cfg.unset(config)
    return removed
