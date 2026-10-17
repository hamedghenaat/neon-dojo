# NEON DOJO

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fast, colorful 2D fighting game with animated, multi-color chibi knights that runs entirely inside the terminal. It uses Python's standard `curses` module, so there are no packages to install.

## Run

```bash
python3 neon_dojo.py
```

Use a terminal window at least **72 columns × 23 rows**. A Unicode-capable terminal with a dark background gives the best result.

On the first launch, NEON DOJO checks the Python runtime, terminal graphics, Unicode support, and UDP networking. It shows each check with a progress bar and records successful setup in the user cache. Later launches verify the same requirements silently and open the menu immediately.

If something is unavailable, the setup screen prints the command or configuration needed to fix it. On Windows it automatically installs `windows-curses` with pip when required and streams the installation log. The setup result is stored at `~/.cache/neon-dojo/setup.json` on Linux/macOS or the matching user cache location selected by `XDG_CACHE_HOME`.

## Controls

| Key | Action |
|---|---|
| `←` / `→` or `A` / `D` | Move |
| `↑` or `W` | Jump |
| `Z` | Punch |
| `X` | Kick |
| `C` | Arc Burst (costs 35 ARC) |
| `Space` | Block |
| `P` or `Esc` | Pause / resume |
| `Q` | Quit |

Defeat your opponent in a best-of-three match. Land hits to charge the ARC meter, then use Arc Burst for heavy damage.

## Game modes

- **Single Player** — fight the CPU-controlled Onyx.
- **Add Server** — host a two-player match as Volt. The game shows the address you can share.
- **Join Server** — play as Onyx. The game waits and automatically discovers an available server on the same local network.

For a local multiplayer match, run the game on both computers. One player chooses **Add Server**, then the other chooses **Join Server**. No configuration is normally needed.

For play over the internet, the host must allow/forward TCP port `48765`. The joining player selects **Join Server**, presses `I`, and enters the host's public address, such as:

```text
203.0.113.10:48765
```

Automatic discovery uses UDP port `48766` and works on a LAN. Gameplay uses TCP port `48765` for reliable delivery.

On an asymmetric or routed network, the joining computer may be reachable even when it cannot initiate a connection to the host. In that case:

1. The remote player selects **Join Server** and waits.
2. The host selects **Add Server**, presses `I`, and enters the waiting player's reachable address.
3. The host establishes the connection in the working direction while keeping the host/player roles unchanged.

For the `hamedvm` route, enter `2.1.1.70:48765` on the host's **Add Server** screen after the VM is waiting on **Join Server**.

## Notes

- Linux and macOS include `curses` with Python.
- Windows users can install `windows-curses` with `py -m pip install windows-curses`, then run `py neon_dojo.py`.
- If a firewall asks for permission, allow Python to use private networks so LAN discovery can work.

## License

NEON DOJO is available under the [MIT License](LICENSE).
