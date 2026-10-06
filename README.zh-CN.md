# herdr-sound

[![PyPI](https://img.shields.io/pypi/v/herdr-sound.svg)](https://pypi.org/project/herdr-sound/)
[![Python versions](https://img.shields.io/pypi/pyversions/herdr-sound.svg)](https://pypi.org/project/herdr-sound/)
[![License](https://img.shields.io/pypi/l/herdr-sound.svg)](LICENSE)

给你的 [Herdr](https://herdr.dev) Agent 换一套游戏风格提示音。

`herdr-sound` 是个很小的命令行工具，用 Herdr **自带的**音效配置在几套 chiptune
「音色包」之间切换 —— 任务完成一个声、需要你介入另一个声。它不是插件、不起后台
进程：只是把音频文件复制到你的 Herdr 配置目录旁边，再把 `[ui.sound]` 指过去。

```console
$ hsp use zelda
  done     -> ~/.config/herdr/sounds/zelda/done.mp3
  blocked  -> ~/.config/herdr/sounds/zelda/blocked.mp3
已切换音色包：zelda
  config: ~/.config/herdr/config.toml
```

[English README](README.md)

---

## 音色包

| 包名 | 风格 | done | blocked |
|---|---|---|---|
| `mario` | 明亮两音大跳 / 经典三音下坠 | 0.39s | 0.67s |
| `zelda` | 五音上行琶音（「发现秘密」）/ 下行收尾 | 0.68s | 0.93s |
| `sonic` | 高频急促双点 / 下行刺音带重击 | 0.44s | 0.82s |
| `tetris` | 急速上行扫音 / 五音小调下行 | 0.39s | 0.84s |
| `pacman` | 快速交替「waka」/ 十一音半音阶滑落 | 0.34s | 0.86s |
| `ff` | 号角式琶音 + 高音拉长 / 缓慢低音下行 | 0.78s | 0.90s |

`herdr-sound list` 可以看到全部包和精确时长。

> **全部音频均为原创。** 每套包都由 `src/herdr_sound_plugin/gen.py` 用方波现场
> 合成，音程与节奏都是原创片段，只是借用了某种听感套路。**不含任何游戏原作
> 采样**，因此整个包可以自由分发。

---

## 安装

需要 Python 3.10+ 和 Herdr 0.9.3+。

```bash
# 推荐：用 uv 装成独立工具
uv tool install herdr-sound

# 或者直接用 pip
pip install herdr-sound
```

想用尚未发布的最新改动，可从源码装：

```bash
uv tool install --from git+https://github.com/ezstack-dev/herdr-sound-plugin herdr-sound
# 或者，在本地克隆目录里
uv tool install .
```

会同时装上 `herdr-sound` 和简写别名 `hsp`。

---

## 支持平台

CLI 本身是纯 Python，Herdr 能跑的平台上都能跑 —— **macOS、Linux、Windows**。
它只做两件事：读写 `config.toml`、拷贝 mp3。播放完全是 Herdr 自己的活儿。

| | 配置文件 | Herdr 用什么播 mp3 |
|---|---|---|
| **macOS** | `~/.config/herdr/config.toml` | `afplay`（系统自带，无需安装） |
| **Linux** | `~/.config/herdr/config.toml`（或 `$XDG_CONFIG_HOME/herdr`） | `PATH` 里按序找 `paplay` · `pw-play` · `ffplay` · `mpg123` · `mpv`，先找到的用 |
| **Windows** | `%APPDATA%\herdr\config.toml` | 内置 PowerShell + WPF `MediaPlayer`（Windows PowerShell 5.1 随系统自带） |

Linux 上需要先装五个播放器之一才会出声：`apt install pulseaudio-utils`
（提供 `paplay`）或 `pipewire-audio`（提供 `pw-play`）基本能覆盖绝大多数发行版。
一个都没有时 Herdr 会退回内置音并提示 `no audio player available` ——
配置依然是对的，`hsp doctor` 也会判定为有效。

音效文件本身就是普通 mp3，三个平台都能解码。Windows 上播放依赖 Windows
PowerShell 5.1 与 WPF 程序集，Win10/11 桌面版都有，但无 GUI 的 Server Core
可能缺。

---

## 用法

```bash
hsp list              # 列出全部音色包，* 标出当前生效的
hsp use mario         # 切换音色包
hsp status            # 当前生效的包，以及配置位置
hsp doctor            # 体检：可执行文件、配置、音效文件
hsp restore           # 恢复 Herdr 默认（关闭音效、删掉复制进去的文件）
```

`hsp use <pack>` 做三件事：

1. 把 `done.mp3` / `blocked.mp3` 复制到 `<herdr 配置目录>/sounds/<pack>/`
2. 把该包写进 `config.toml` 的 `[ui.sound]`
3. 执行 `herdr server reload-config`，不用重启 herdr 就生效

它会**原地修改**你的配置文件（保留注释与排版），但事先备份一下仍然是个好习惯。

### 哪个键对应哪个声

| Herdr 配置键 | 触发时机 | 包内文件 |
|---|---|---|
| `ui.sound.done_path` | Agent 完成一轮 | `done.mp3` |
| `ui.sound.request_path` | Agent 需要你介入 | `blocked.mp3` |

### 自定义配置路径

`herdr-sound` 找配置的顺序与 Herdr 一致：先看 `$HERDR_CONFIG_PATH`，
然后是上表里对应平台的默认路径 —— Windows 是 `%APPDATA%\herdr\config.toml`，
其他平台是 `$XDG_CONFIG_HOME/herdr/config.toml` 或 `~/.config/herdr/config.toml`。
可以用 `HERDR_CONFIG_PATH` 指向别的文件：

```bash
HERDR_CONFIG_PATH=/tmp/test/config.toml hsp use pacman
```

---

## 需要知道的事

**音效在 Herdr 的 *client* 侧播放，不在 server 侧。** Herdr 由附着上来的
client 进程解析 `[ui.sound]` 并播放。如果你是无界面运行、或者只通过 bridge 附着，
配置依然是对的 —— 只是在真有 client 附着之前听不到声音。无论哪种情况，
`hsp doctor` 都会告诉你配置是否有效。

**没有「失败」音效。** Herdr 的 Agent 状态只有
`idle / working / blocked / done / unknown` —— **没有 `failed`**。崩溃或报错的
Agent 通常仍以 `done` 收尾，因此会响*完成*音。`blocked` 槽位的语义是「需要你
关注」，这是 Herdr 能提供的最接近的东西，我们就把「出事了」的音放在这个槽位。

**`restore` 只删它自己装的东西。** 已知包的 `sounds/<pack>/` 目录会被删除；
你自己放进 sounds 目录的其他文件不动。

---

## 开发

```bash
task check        # 测试 + 音效同步校验 + wheel 打包校验
task sounds       # 按 packs.py 里的谱子重新生成全部 mp3
task list         # 打印包名与时长
```

目录结构：

```
src/herdr_sound_plugin/
  cli.py        typer 命令行（list / use / status / doctor / restore / version）
  config.py     定位（区分操作系统）、读取、修改 herdr 的 config.toml（tomlkit，保留注释）
  install.py    复制音效、计算 [ui.sound] 路径、卸载
  herdr.py      薄封装：找 herdr 可执行文件、reload-config
  packs.py      谱子表 —— 每个包每种用途一份「乐谱」
  synth.py      方波合成 -> mp3
  gen.py        把 packs.py 的谱子写成 sounds/<pack>/<kind>.mp3
  sounds/       12 个已提交的 mp3，随 wheel 一起分发
packages/legacy-herdr-plugin/   ⚠️ 旧插件方案的死代码
```

`packages/legacy-herdr-plugin/` 是归档，不再使用，且已排除出测试收集。
想看当年的复盘请读它自己的 README。

### 发布

推一个 `v*` 的 tag 就会发布到 PyPI。**先改 `pyproject.toml` 里的版本号** ——
tag 与版本号不一致时工作流会拒绝发布。

```bash
# 改 pyproject.toml 的 "version"，然后：
git tag v1.0.1 && git push --tags
```

`.github/workflows/release.yml` 会跑测试、构建、通过 PyPI 可信发布（不往仓库里
存 token）上传，并建一个 GitHub Release。

**一次性设置：** 到 https://pypi.org/manage/project/herdr-sound/settings/publishing/
添加一个 trusted publisher，填 `Owner = ezstack-dev`、`Repository = herdr-sound-plugin`、
`Workflow = release.yml`、`Environment = pypi`。不配这一步，发布步骤会以权限错误失败。

---

## 许可

Apache-2.0，见 [LICENSE](LICENSE)。
