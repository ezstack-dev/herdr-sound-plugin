"""herdr-sound：把 herdr 的 Agent 提示音换成游戏风格音色包。

命令行入口见 `cli.py`（`herdr-sound` / `hsp`）：

    herdr-sound list       # 看有哪些包
    herdr-sound use mario  # 换包
    herdr-sound status     # 当前用的哪个

模块分工：
    cli      命令行界面（typer）
    config   读写 `~/.config/herdr/config.toml` 的 `[ui.sound]`
    install  音效文件 copy 到 herdr 侧 + 改配置
    herdr    调 herdr 二进制的薄封装（校验、重载配置）
    packs    音色包谱子定义
    synth    方波合成 + mp3 编码（只有改谱子时才需要）
    gen      把谱子渲染成仓库里的 mp3（开发用）
"""

__version__ = "1.0.0"
