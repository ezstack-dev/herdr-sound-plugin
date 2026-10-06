# ⚠️ 已失效的归档代码 —— 不要使用，不要在此基础上修改

这里存放的是 **herdr 插件方案** 的完整实现，2026-10-06 被「直接改 herdr 原生配置」的方案取代。

## 为什么失效

原方案让 herdr 在 `pane.agent_status_changed` 事件上执行 `notify.sh`，由脚本自己 `afplay` 播放 mp3。
后来发现 herdr **原生**就支持换提示音（`herdr --default-config` 的 `[ui.sound]` 段）：

```toml
[ui.sound]
done_path = "sounds/done.mp3"      # 任务完成
request_path = "sounds/request.mp3" # 需要人工介入
```

原生方案的三个决定性优势：

1. **不需要脚本**。插件清单 `RawPluginManifest` 只能声明 `[events] on=... command=[...]`，
   插件无法直接指定 mp3，必须执行命令 —— 这层间接是纯开销。
2. **不会被系统静音策略绕过**。声音由 herdr **client** 进程播放（`src/client/notifications.rs`），
   而插件是在 **server** 侧 `afplay` 子进程，两者互不知情 ⇒ **会响两次**。
3. **判错能力并不比原生强**。`agent_status` 只有 `idle/working/blocked/done/unknown`，
   **没有 failed**；agent 报错通常仍收尾为 `done`，脚本照样会响「成功音」。
   当初设计里「blocked = 异常音」的映射站不住。

## 内容清单（全部失效）

| 文件 | 原用途 |
|---|---|
| `herdr-plugin.toml` | 插件清单：注册 6 个 `use-<pack>` action + 状态变更事件钩子 |
| `notify.sh` | 事件钩子脚本：读 `HERDR_PLUGIN_EVENT_JSON` 里的 `agent_status`，`done`→done.mp3、`blocked`→blocked.mp3 |
| `switch.sh` | action 脚本：把包名写进 `$HERDR_PLUGIN_STATE_DIR/pack` |
| `src/herdr_sound_plugin/capture.py` | 采样 `afplay` 进程，为 e2e 取证 |
| `src/herdr_sound_plugin/e2e.py` | 端到端验证：起真 agent、等状态迁移、抓 afplay |
| `tests/test_scripts.py` | 上述 shell 脚本与清单的测试 |

## 当年踩过的坑（有价值，供未来参考）

- 插件清单的 `command` 是 **argv 数组**，**不经 shell**、**不搜 PATH**，以插件目录为 cwd。
  ⇒ `command = ["hook.sh"]` 失败，`command = ["bash", "notify.sh"]` 才成立。
- `herdr pane report-agent --state blocked` 在 **已有 agent 的 pane 上被忽略**，只在空 shell pane 上生效。
- `done` **无法**用 `report-agent` 伪造（`--state` 只收 `idle|working|blocked|unknown`），必须真跑一轮 agent。
- 重复上报**同一**状态不产生状态迁移 ⇒ 无事件 ⇒ 静默。

## 如果将来还要用

**重新写，不要复活这里的东西。** 上述坑意味着这套代码与 herdr 0.9.3 的内部行为强耦合，
herdr 升级后可能静默失效（表现为「有时不响」），维护成本高于重写。

当前方案见仓库根目录 `README.md`，实现在 `src/herdr_sound_plugin/`。
