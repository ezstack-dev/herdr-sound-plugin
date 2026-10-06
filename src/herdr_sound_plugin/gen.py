"""生成音色包 mp3 文件。

用法（推荐走 Taskfile）：
    uv run python -m herdr_sound_plugin.gen            # 生成到 ./sounds
    uv run python -m herdr_sound_plugin.gen out        # 生成到 ./out
    uv run python -m herdr_sound_plugin.gen --list     # 只列出音色包
"""

from __future__ import annotations

import pathlib
import sys

from . import packs, synth


def generate(out_dir: pathlib.Path, only: "list[str] | None" = None) -> "list[pathlib.Path]":
    """把全部（或 `only` 指定的）音色包渲染成 `<out>/<pack>/<kind>.mp3`。"""
    written = []
    for pack in packs.labels():
        if only and pack not in only:
            continue
        pack_dir = out_dir / pack
        pack_dir.mkdir(parents=True, exist_ok=True)
        for kind in packs.KINDS:
            pcm = synth.render(packs.notes_of(pack, kind))
            data = synth.encode_mp3(pcm)
            assert synth.is_mp3(data), f"{pack}/{kind} 编码结果不是 mp3"
            path = pack_dir / f"{kind}.mp3"
            path.write_bytes(data)
            written.append(path)
    return written


def main(argv: "list[str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in ("--list", "-l"):
        for pack in packs.labels():
            total = sum(d for kind in packs.KINDS for _, d in packs.notes_of(pack, kind))
            print(f"{pack:8s} 共 {total:.2f}s  " +
                  " ".join(f"{k}={len(packs.notes_of(pack, k))}音" for k in packs.KINDS))
        return 0

    try:
        import lameenc  # noqa: F401
    except ImportError:
        print("缺少 lameenc。请先 `uv sync`，或用 `uv run --with lameenc ...`。",
              file=sys.stderr)
        return 2

    out_dir = pathlib.Path(args[0] if args else "sounds")
    for path in generate(out_dir):
        data = path.read_bytes()
        print(f"{path}  {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
