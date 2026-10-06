"""命令行入口：`herdr-sound`（别名 `hsp`）。

做的事只有一件 —— 把 herdr 的提示音换成你选的音色包：

    herdr-sound list                  看有哪些包
    herdr-sound use mario             换成 mario
    herdr-sound status                看当前用的哪个
    herdr-sound doctor                体检：配置路径、herdr 版本、音效是否到位
    herdr-sound restore               恢复 herdr 默认（关掉音效）

切换 = 把音效 copy 到 `~/.config/herdr/sounds/<包>/`，再把 `config.toml` 的
`[ui.sound]` 的 `done_path` / `request_path` 指过去。不装插件、不常驻进程。
"""

from __future__ import annotations

import pathlib
import sys

import typer

from . import __version__
from . import config as cfg
from . import herdr, install, packs

app = typer.Typer(
    name="herdr-sound",
    help="切换 herdr 的 Agent 提示音（游戏风格音色包）。",
    no_args_is_help=True,
    add_completion=False,
)

PACK_HELP = "音色包名称；省略则打印列表"


def _packs_table() -> str:
    """渲染音色包清单，标出当前用的那个。"""
    current = install.current_pack()
    lines = []
    for name in packs.labels():
        mark = "*" if name == current else " "
        total = sum(d for kind in packs.KINDS for _, d in packs.notes_of(name, kind))
        lines.append(f" {mark} {name:<8} {total:5.2f}s")
    if current is None:
        lines.append("   (no pack active)")
    return "\n".join(lines)


@app.command("list")
def list_packs() -> None:
    """列出全部音色包，`*` 标出当前生效的。"""
    typer.echo(_packs_table())


@app.command()
def use(
    pack: str = typer.Argument(..., help="音色包名称，见 `herdr-sound list`"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="只输出错误"),
) -> None:
    """切换到指定音色包（copy 音效 + 改写 herdr 配置）。"""
    if pack not in packs.PACKS:
        typer.secho(f"未知音色包：{pack}（可用：{' '.join(packs.labels())}）",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    result = install.use(pack)
    message = herdr.reload_config()
    if not quiet:
        for kind, path in result["files"].items():
            typer.echo(f"  {kind:<8} -> {path}")
        typer.secho(f"已切换音色包：{pack}", fg=typer.colors.GREEN)
        typer.echo(f"  config: {result['config']}")
        typer.echo(f"  {message}")


@app.command()
def status() -> None:
    """显示当前生效的音色包与配置位置。"""
    config_file = cfg.config_path()
    section = cfg.get_sound()
    pack = install.current_pack(section)
    typer.echo(f"config:   {config_file}")
    typer.echo(f"sounds:   {cfg.sound_dir()}")
    typer.echo(f"enabled:  {section.get('enabled', '(unset)')}")

    if pack is None:
        typer.secho("音色包:   无（herdr 用内置音效或已关闭）", fg=typer.colors.YELLOW)
        return

    typer.secho(f"音色包:   {pack}", fg=typer.colors.GREEN)
    typer.echo(f"done:     {section.get('done_path')}")
    typer.echo(f"request:  {section.get('request_path')}")
    missing = [k for k in packs.KINDS
               if not (cfg.sound_dir() / pack / f"{k}.mp3").exists()]
    if missing:
        typer.secho(f"警告：音效文件缺失 {missing}，请重跑 `herdr-sound use {pack}`",
                    fg=typer.colors.YELLOW, err=True)


@app.command()
def doctor() -> None:
    """体检：herdr 可执行文件、配置、音效文件是否都就位。"""
    ok = True
    try:
        binary = herdr.resolve_binary()
        typer.secho(f"[ok] herdr: {binary}", fg=typer.colors.GREEN)
    except FileNotFoundError as exc:
        typer.secho(f"[!!] {exc}", fg=typer.colors.RED, err=True)
        ok = False

    config_file = cfg.config_path()
    if config_file.exists():
        typer.secho(f"[ok] config: {config_file}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"[!!] config 不存在：{config_file}", fg=typer.colors.RED, err=True)
        ok = False

    available = install.installed_packs()
    typer.echo(f"[..] 已安装的音色包：{available or '无'}")

    pack = install.current_pack()
    if pack and pack in available:
        typer.secho(f"[ok] 当前音色包 {pack} 的音效文件齐全", fg=typer.colors.GREEN)
    elif pack:
        typer.secho(f"[!!] 当前音色包 {pack} 的音效文件缺失", fg=typer.colors.RED, err=True)
        ok = False

    raise typer.Exit(0 if ok else 1)


@app.command()
def restore(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
) -> None:
    """恢复 herdr 默认：关闭音效并删掉本工具 copy 的音效文件。"""
    if not yes:
        typer.confirm("将关闭 herdr 音效并删除已 copy 的音色包，继续？", abort=True)
    removed = install.uninstall()
    message = herdr.reload_config()
    for path in removed:
        typer.echo(f"  已删除 {path}")
    typer.secho("已恢复 herdr 默认（音效关闭）", fg=typer.colors.GREEN)
    typer.echo(f"  {message}")


@app.command()
def version() -> None:
    """打印版本号。"""
    typer.echo(__version__)


def main(argv: "list[str] | None" = None) -> int:
    """供 `__main__` 与测试调用；typer 自己会走 `app()`。"""
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
