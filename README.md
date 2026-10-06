# herdr-sound

[![PyPI](https://img.shields.io/pypi/v/herdr-sound.svg)](https://pypi.org/project/herdr-sound/)
[![Python versions](https://img.shields.io/pypi/pyversions/herdr-sound.svg)](https://pypi.org/project/herdr-sound/)
[![License](https://img.shields.io/pypi/l/herdr-sound.svg)](LICENSE)

Give your [Herdr](https://herdr.dev) agents a game-style notification sound.

`herdr-sound` is a tiny CLI that switches Herdr's **native** notification sounds
between chiptune "packs" — one sound when an agent finishes, another when it
needs you. No plugin, no background process: it just copies the audio files next
to your Herdr config and points `[ui.sound]` at them.

```console
$ hsp use zelda
  done     -> ~/.config/herdr/sounds/zelda/done.mp3
  blocked  -> ~/.config/herdr/sounds/zelda/blocked.mp3
已切换音色包：zelda
  config: ~/.config/herdr/config.toml
```

[中文文档 / Chinese README](README.zh-CN.md)

---

## Packs

| Pack | Vibe | done | blocked |
|---|---|---|---|
| `mario` | bright two-note jump / classic falling three-note | 0.39s | 0.67s |
| `zelda` | five-note rising arpeggio ("secret found") / descending resolve | 0.68s | 0.93s |
| `sonic` | fast high double-tap / descending sting with retrigger | 0.44s | 0.82s |
| `tetris` | quick rising sweep / five-note minor descent | 0.39s | 0.84s |
| `pacman` | rapid alternating "waka" / eleven-note chromatic slide | 0.34s | 0.86s |
| `ff` | fanfare arpeggio with a held top note / slow low descent | 0.78s | 0.90s |

Run `herdr-sound list` to see them with exact durations.

> **All audio is original.** Every pack is synthesized from square waves by
> `src/herdr_sound_plugin/gen.py` — the notes and rhythm are original
> compositions in a genre style. **No samples from any game are included**, so
> the whole package is safe to redistribute.

---

## Install

Requires Python 3.10+ and Herdr 0.9.3+.

```bash
# recommended: isolated install with uv
uv tool install herdr-sound

# or plain pip
pip install herdr-sound
```

From source, for the latest unreleased changes:

```bash
uv tool install --from git+https://github.com/ezstack-dev/herdr-sound-plugin herdr-sound
# or, from a local clone
uv tool install .
```

Both `herdr-sound` and the short alias `hsp` are installed.

---

## Platforms

The CLI itself is pure Python and runs anywhere Herdr does — **macOS, Linux and
Windows**. It only reads and writes `config.toml` and copies mp3 files; audio
playback is entirely Herdr's job.

| | Config file | How Herdr plays the mp3 |
|---|---|---|
| **macOS** | `~/.config/herdr/config.toml` | `afplay` (built in, nothing to install) |
| **Linux** | `~/.config/herdr/config.toml` (or `$XDG_CONFIG_HOME/herdr`) | first of `paplay` · `pw-play` · `ffplay` · `mpg123` · `mpv` found in `PATH` |
| **Windows** | `%APPDATA%\herdr\config.toml` | built-in PowerShell + WPF `MediaPlayer` (Windows PowerShell 5.1 ships with Windows — nothing to install) |

On Linux, Herdr only emits sound if one of those five players is installed:
`apt install pulseaudio-utils` (for `paplay`) or `pipewire-audio` (for `pw-play`)
covers almost everyone. With none of them you get Herdr's built-in sound and a
`no audio player available` note — the config is still correct, and `hsp doctor`
will report it as valid.

The sound files themselves are plain MP3s, so they decode on every platform.
On Windows, sound needs Windows PowerShell 5.1 and the WPF assemblies — both are
present on Windows 10/11 desktop, but a GUI-less (Server Core) install may not
have them.

---

## Usage

```bash
hsp list              # list packs, * marks the active one
hsp use mario         # switch to a pack
hsp status            # what is active right now, and where
hsp doctor            # health check: binary, config, sound files
hsp restore           # back to Herdr defaults (disable sound, remove copies)
```

`hsp use <pack>` does three things:

1. copies `done.mp3` / `blocked.mp3` into `<herdr config dir>/sounds/<pack>/`
2. writes the pack into `[ui.sound]` in your `config.toml`
3. runs `herdr server reload-config` so it takes effect without a restart

It edits your config **in place** and preserves comments and formatting, but
backing it up first is still a good habit.

### Which key does what

| Herdr config key | When it fires | Pack file |
|---|---|---|
| `ui.sound.done_path` | an agent finished its turn | `done.mp3` |
| `ui.sound.request_path` | an agent needs attention | `blocked.mp3` |

### Custom config location

`herdr-sound` finds your config the same way Herdr does:
`$HERDR_CONFIG_PATH` first, then the per-platform default from the
[Platforms](#platforms) table above — `%APPDATA%\herdr\config.toml` on Windows,
`$XDG_CONFIG_HOME/herdr/config.toml` or `~/.config/herdr/config.toml` elsewhere.
Set `HERDR_CONFIG_PATH` to operate on a different one:

```bash
HERDR_CONFIG_PATH=/tmp/test/config.toml hsp use pacman
```

---

## Things worth knowing

**Sounds play in the Herdr *client*, not the server.** Herdr resolves
`[ui.sound]` and plays the audio in the attached client process. If you run
Herdr headlessly or only attach through a bridge, the config is still correct —
you just won't hear anything until a real client is attached. `hsp doctor` tells
you the config is valid either way.

**There is no "failed" sound.** Herdr's agent states are
`idle / working / blocked / done / unknown` — there is no `failed`. A crashed or
errored agent usually still ends as `done`, so it gets the *finish* sound. The
`blocked` slot means "needs attention", which is the closest thing Herdr offers
and is what we map the "something's wrong" sound onto.

**`restore` only removes what it installed.** Files under `sounds/<pack>/` for
known packs are deleted; anything else you put in the sounds directory is left
alone.

---

## Development

```bash
task check        # tests + sound-sync check + wheel packaging check
task sounds       # regenerate all mp3s from the note tables in packs.py
task list         # print packs and durations
```

Layout:

```
src/herdr_sound_plugin/
  cli.py        typer app (list / use / status / doctor / restore / version)
  config.py     locate (per-OS) + read + edit herdr's config.toml (tomlkit, keeps comments)
  install.py    copy sounds, compute [ui.sound] paths, uninstall
  herdr.py      thin wrapper: find the herdr binary, reload-config
  packs.py      the note tables — one "score" per pack and purpose
  synth.py      square-wave synthesis -> mp3
  gen.py        writes packs.py scores out to sounds/<pack>/<kind>.mp3
  sounds/       12 committed mp3s, shipped inside the wheel
packages/legacy-herdr-plugin/   ⚠️ dead code from the old plugin approach
```

`packages/legacy-herdr-plugin/` is archived, not used, and excluded from test
collection. See its README if you want the post-mortem.

### Releasing

Pushing a `v*` tag publishes to PyPI. Bump the version in `pyproject.toml`
first — the workflow refuses to publish if the tag and the version disagree.

```bash
# bump "version" in pyproject.toml, then:
git tag v1.0.3 && git push --tags
```

`.github/workflows/release.yml` then runs the tests, builds, publishes via PyPI
trusted publishing (no token stored in the repo), and opens a GitHub Release.

**One-time setup:** add a trusted publisher on PyPI at
https://pypi.org/manage/project/herdr-sound/settings/publishing/ with
`Owner = ezstack-dev`, `Repository = herdr-sound-plugin`,
`Workflow = release.yml`, `Environment = pypi`. Until that exists the publish
step fails with a permissions error.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
