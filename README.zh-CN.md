# herdr-sound-plugin

给 [Herdr](https://herdr.dev) 加上游戏风格的提示音，内置 **6 组可切换的音色包**：

| Agent 事件 | 音效 | 含义 |
|---|---|---|
| 任务**完成**（`done`） | 明亮上行 | 一切正常 |
| 任务**需要介入**（`blocked`） | 低沉下行 | 需要人工处理 |

> 🌐 [English README →](README.md)

**音色包：** `mario`（默认）· `zelda` · `sonic` · `tetris` · `pacman` · `ff`

所有音效都是**用 Python 标准库现场合成的原创 8-bit 风格片段**（方波），不含任何游戏原作的采样。既无版权风险，也方便你重新生成或自行替换。

## 为什么用插件而不是 `[ui.sound]`

Herdr 内置的 `[ui.sound]` 配置有两个硬限制：

1. 只有 `done` 和 `request` 两个桶——**没有「失败」音**，无法区分成功与异常。
2. 声音在**本地 client 进程**里播放。如果 Herdr server 跑在远端、而 client 不在那台机器上，你就什么都听不到。

本插件改用 Herdr 的**事件钩子**：由 **server 侧**的进程直接播放，因此无论有没有 client 附着都能响，并且能读到真实的 `agent_status` 来区分成功与异常。

## 安装

插件自带全部产物，不需要构建。

```bash
git clone git@github.com:ezstack-dev/herdr-sound-plugin.git
herdr plugin link "$PWD/herdr-sound-plugin"
herdr plugin list
```

`herdr plugin link` 是就地指向该目录，不构建、不复制。请在**跑 Herdr server 的那台机器**上执行一次。

仓库转为公开后，也可以用一条命令安装：

```bash
herdr plugin install ezstack-dev/herdr-sound-plugin
```

> **插件跑在 Herdr server 上，所以声音是在 server 所在的机器上响的。**
> 如果你的 server 在远端（通过 `herdr --remote` 连接），请装在**跑 server 的那台机器**上，而不是你眼前的 client。

### ⚠️ 装完必须关掉内置声音

否则会**双声**：Herdr 内置的 `[ui.sound]` 在 **client** 侧响，本插件在 **server** 侧响，两者互不知情。

编辑 `~/.config/herdr/config.toml`，把整个 `[ui.sound]` 段替换为：

```toml
[ui.sound]
enabled = false
```

然后生效：

```bash
herdr server reload-config
```

（也可以只静音 pi agent：`[ui.sound.agents] pi = "off"`。）

## 切换音色包

每个音色包对应一个插件 action：

```bash
herdr plugin action list --plugin mario-sound        # 查看全部音色包
herdr plugin action invoke mario-sound.use-zelda     # 切到 Zelda 音色
```

选择结果写入插件的 state 目录，**每次事件触发时都会重新读取**，因此立即生效，无需重启 Herdr。

可以在 `~/.config/herdr/config.toml` 里绑定快捷键：

```toml
[[keys.command]]
key = "prefix+l"
type = "plugin_action"
command = "mario-sound.list-sounds"
```

## 验证

最可靠的方式是用自带的端到端验证脚本：它会新建一个试验 workspace，逐包切换，并核对到底播了哪个文件：

```bash
task e2e                    # 全部音色包
task e2e -- --packs mario tetris
```

输出形如：

```
✓ mario    status=done     hits= 25  expected sounds/mario/done.mp3
✓ tetris   status=done     hits= 26  expected sounds/tetris/done.mp3
```

也可以就跑一个真实的 agent 任务到结束，然后看日志：

```bash
herdr plugin log list --plugin mario-sound
# 每次触发都会记一条 status=succeeded
```

> ⚠️ `herdr pane report-agent ... --state blocked` **不会**触发本钩子——它只是设置一个状态快照，
> 而不是发出状态*变化*，所以对一个没有真 agent 的 pane 直接 report-agent 不产生任何插件事件。
> 要验证钩子请用 `task e2e`。

## 工作原理

```
herdr server
  └─ pane.agent_status_changed 事件
       └─ notify.sh   （cwd = 插件目录；读 HERDR_PLUGIN_EVENT_JSON）
            ├─ done    → afplay sounds/<pack>/done.mp3
            ├─ blocked → afplay sounds/<pack>/blocked.mp3
            └─ 其他状态 → 静默退出

切换 action
  └─ switch.sh  → 写入 <state_dir>/pack
```

`working` / `idle` / `unknown` 都不发声，所以任务刚开始时不会吵你。状态文件缺失或包名不存在时会回退到 `mario`，而不是干脆不响。

### 文件说明

| 文件 | 作用 |
|---|---|
| `herdr-plugin.toml` | 插件清单——事件订阅 + 每个音色包一个 action |
| `notify.sh` | 事件钩子——按 `agent_status` 分支，播放对应 mp3 |
| `switch.sh` | action 处理器——记录当前选中的音色包 |
| `sounds/<pack>/done.mp3` | 完成音（6 组） |
| `sounds/<pack>/blocked.mp3` | 异常音（6 组） |
| `src/herdr_sound_plugin/` | 生成器与调试工具（见下） |
| `tests/` | 合成、音色包、清单、shell 行为的单元测试 |
| `Taskfile.yml` | 全部开发任务（`task --list-all`） |

## 开发

需要 [`uv`](https://docs.astral.sh/uv/) 和 [`task`](https://taskfile.dev)。

```bash
task sync          # 安装依赖
task test          # 跑单元测试
task check         # 提交前门禁：测试 + 清单一致性 + 音效同步检查
```

### 重新生成 / 新增音效

音色包在 `src/herdr_sound_plugin/packs.py` 里以「谱子」形式定义：

```python
"mario": {
    "done": [("B5", 0.09), ("E6", 0.30)],
    "blocked": [("E5", 0.12), ("C5", 0.13), ("G4", 0.42)],
},
```

改完谱子后：

```bash
task sounds        # 重新生成全部 mp3 到 ./sounds
task list          # 列出音色包、音数、总时长
task notes PACK=mario
```

`task check-sounds`（包含在 `task check` 里）会在「已提交的 mp3 与生成器输出不一致」时失败，因此 `packs.py` 里的谱子始终是唯一事实来源——**不要手改 mp3**。

新增一个音色包要改两处：`packs.py` 里加谱子、`herdr-plugin.toml` 里加 `[[actions]]`。有测试专门守住这两者的一致性。

### 调试工具

| 命令 | 作用 |
|---|---|
| `task capture -- --seconds 20` | 采样 `afplay`，报告实际播放了哪些文件 |
| `task e2e` | 起一个试验 workspace/agent，逐个切包并核对真实播放 |
| `task logs` | 查看插件最近的执行日志 |
| `task relink` | unlink + link（改过清单后需要） |
| `uv run python -m herdr_sound_plugin.herdr status w1:p1` | 查某个 pane 的 agent 状态 |

`task capture` 的存在是有原因的：钩子是异步播放的（`nohup afplay &`），进程一闪而过，直接 `ps | grep afplay` 基本抓不到——而且 `grep` 还会匹配到它自己的命令行。采样器用 `pgrep -x afplay` 精确取 pid，再逐个读完整 argv。

## 平台支持与已知边界

- **目前仅支持 macOS**——播放走 `/usr/bin/afplay`。Linux 上把 `notify.sh` 里的 `afplay` 换成 `paplay`/`aplay` 即可（一行）。
- `blocked` 只覆盖「需要人工介入」的上报（例如 pi-subagents 发出）。**Herdr 没有运行期失败状态**——agent 报错后通常仍以 `done` 收尾，会播完成音。这是 Herdr 状态模型的限制，不是本插件的问题。
- 需要 Herdr `>= 0.9.3`（引入插件事件 API 的版本）。
- 清单里的 `command` 是 **argv 数组而非 shell 字符串**，且**相对插件目录解析、不搜 PATH**——所以必须写 `["bash", "notify.sh"]` 而不是 `["notify.sh"]`。

## 许可

[Apache-2.0](LICENSE)
