# herdr-sound-plugin

Give [Herdr](https://herdr.dev) game-style notification sounds, with **6 switchable sound packs**:

| Agent event | Sound | Meaning |
|---|---|---|
| Task **completed** (`done`) | bright ascending | All good |
| Task **needs attention** (`blocked`) | dark descending | Human intervention required |

> 🌐 [中文说明 / Chinese README →](README.zh-CN.md)

**Packs:** `mario` (default) · `zelda` · `sonic` · `tetris` · `pacman` · `ff`

All sounds are **original chiptunes synthesized with the Python standard library** (square waves) — no samples from any game. No copyright risk, and you can regenerate or add your own freely.

## Why a plugin instead of `[ui.sound]`

Herdr's built-in `[ui.sound]` config has two hard limits:

1. It only has `done` and `request` buckets — **there is no "failure" sound**, so you cannot distinguish success from error.
2. Sound playback happens in the **local client process**. If the Herdr server runs on a remote machine and your client isn't on that machine, you hear nothing.

This plugin uses Herdr's **event hooks** instead: a process on the **server side** plays the sound directly, so it works regardless of whether a client is attached, and it can read the real `agent_status` to tell success from failure.

## Install

The plugin ships with everything it needs — no build step.

```bash
git clone git@github.com:ezstack-dev/herdr-sound-plugin.git
herdr plugin link "$PWD/herdr-sound-plugin"
herdr plugin list
```

`herdr plugin link` points Herdr at a directory in place — no build, no copying. Run it once per machine that has the Herdr **server**.

Once the repository is public you can also install it in one command:

```bash
herdr plugin install ezstack-dev/herdr-sound-plugin
```

> **The plugin runs on the Herdr server, so the sound plays on the server's machine.**
> If your server is remote (connected via `herdr --remote`), install it on the machine running the server — not on the client you're looking at.

### ⚠️ Then turn off the built-in sound

Otherwise you get **double playback**: Herdr's own `[ui.sound]` plays on the **client** while this plugin plays on the **server**, and neither knows about the other.

Edit `~/.config/herdr/config.toml` and replace the whole `[ui.sound]` section with:

```toml
[ui.sound]
enabled = false
```

Then apply it:

```bash
herdr server reload-config
```

(Alternatively, mute only the pi agent with `[ui.sound.agents] pi = "off"`.)

## Switch sound packs

Each pack is a plugin action. Switch with:

```bash
herdr plugin action list --plugin mario-sound        # see all packs
herdr plugin action invoke mario-sound.use-zelda     # switch to zelda
```

The choice is written to the plugin's state dir and is read **on every event**, so it takes effect immediately — no Herdr restart.

Bind a key for fast switching in `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+l"
type = "plugin_action"
command = "mario-sound.list-sounds"
```

## Verify

The reliable way is the bundled end-to-end harness — it creates a probe workspace, cycles through the packs, and confirms which file actually played:

```bash
task e2e                    # every pack
task e2e -- --packs mario tetris
```

Output looks like:

```
✓ mario    status=done     hits= 25  expected sounds/mario/done.mp3
✓ tetris   status=done     hits= 26  expected sounds/tetris/done.mp3
```

Or just run any agent task to completion and check the log:

```bash
herdr plugin log list --plugin mario-sound
# every trigger records one entry with status=succeeded
```

> ⚠️ `herdr pane report-agent` does emit `pane.agent_status_changed`, with two caveats:
> it is **ignored on a pane that already runs an agent** (only a bare shell pane can be
> forced to `blocked`), and re-reporting the **same** state emits nothing — a state must
> actually *change*. So reset to `idle` before re-forcing `blocked`. `done` cannot be faked
> at all (`--state` only accepts `idle|working|blocked|unknown`); run `task e2e` instead.

## How it works

```
herdr server
  └─ pane.agent_status_changed event
       └─ notify.sh   (cwd = plugin dir; reads HERDR_PLUGIN_EVENT_JSON)
            ├─ done    → afplay sounds/<pack>/done.mp3
            ├─ blocked → afplay sounds/<pack>/blocked.mp3
            └─ anything else → exit silently

switch action
  └─ switch.sh  → writes <state_dir>/pack
```

`working` / `idle` / `unknown` never make a sound, so you won't be pinged when work merely starts. If the state file is missing or names an unknown pack, playback falls back to `mario` rather than going silent.

### Files

| File | Purpose |
|---|---|
| `herdr-plugin.toml` | Plugin manifest — event subscription + one action per pack |
| `notify.sh` | Event hook — branches on `agent_status`, plays the matching mp3 |
| `switch.sh` | Action handler — records the chosen pack |
| `sounds/<pack>/done.mp3` | Completion sounds (6 packs) |
| `sounds/<pack>/blocked.mp3` | Attention sounds (6 packs) |
| `src/herdr_sound_plugin/` | Generator + debug tooling (see below) |
| `tests/` | Unit tests for synthesis, packs, manifest, and shell behavior |
| `Taskfile.yml` | All dev tasks (`task --list-all`) |

## Development

Requires [`uv`](https://docs.astral.sh/uv/) and [`task`](https://taskfile.dev).

```bash
task sync          # install dependencies
task test          # run the test suite
task check         # pre-commit gate: tests + manifest + sounds-in-sync
```

### Regenerating / adding sounds

Sound packs are defined as note scores in `src/herdr_sound_plugin/packs.py`:

```python
"mario": {
    "done": [("B5", 0.09), ("E6", 0.30)],
    "blocked": [("E5", 0.12), ("C5", 0.13), ("G4", 0.42)],
},
```

Add or edit a pack, then:

```bash
task sounds        # regenerate every mp3 into ./sounds
task list          # list packs with note counts and durations
task notes PACK=mario
```

`task check-sounds` (part of `task check`) fails if the committed mp3s don't match the generator, so the scores in `packs.py` remain the single source of truth — never hand-edit the mp3s.

Adding a pack means two edits: a score in `packs.py`, and an `[[actions]]` entry in `herdr-plugin.toml`. A test asserts the two stay in sync.

### Debug tooling

| Command | What it does |
|---|---|
| `task capture -- --seconds 20` | Samples `afplay` and reports which files actually played |
| `task e2e` | Spins up a probe workspace/agent, switches through packs, verifies real playback |
| `task logs` | Recent plugin execution log |
| `task relink` | Unlink + link (needed after editing the manifest) |
| `uv run python -m herdr_sound_plugin.herdr status w1:p1` | Query a pane's agent status |

`task capture` exists because the hook plays sounds asynchronously (`nohup afplay &`), so a plain `ps | grep afplay` usually misses it — and `grep` matches its own command line. The sampler uses `pgrep -x afplay` and reads full argv per pid.

## Platform support & limitations

- **macOS only** as shipped — playback uses `/usr/bin/afplay`. For Linux, change the `afplay` line in `notify.sh` to `paplay`/`aplay` (one line).
- `blocked` only covers "needs attention" reports (e.g. from pi-subagents). **Herdr has no runtime-failure state** — an agent that errors out usually still ends in `done` and will play the completion sound. That's a limitation of Herdr's state model, not of this plugin.
- Requires Herdr `>= 0.9.3` (the version that introduced the plugin event API).
- `command` in the manifest is an **argv array, not a shell string**, and is resolved **relative to the plugin directory with no PATH lookup** — hence `["bash", "notify.sh"]` rather than `["notify.sh"]`.

## License

[Apache-2.0](LICENSE)
