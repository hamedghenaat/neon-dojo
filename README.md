# NEON DOJO

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fast, colorful 2D fighting game with animated, multi-color chibi knights that runs entirely inside the terminal. It uses Python's standard `curses` module, so there are no packages to install.

Gameplay and scene rendering live in `neon_dojo.py`. Original character pixel art and the half-block terminal renderer live in `sprites.py` (see [art references](ART_REFERENCES.md)). Interface discovery, Tailscale routes, TCP/UDP transport, protocol messages, and state synchronization live in `networking.py`.

## Run

### Compare the three editions

Run any of these files directly from your terminal:

| Command | Display | Character artwork |
|---|---|---|
| `python3 neon_dojo_pygame.py` | Resizable pygame-ce window | PNG sheets exported from editable Aseprite sources |
| `python3 neon_dojo_pyxel.py` | Pyxel retro game window | The same Aseprite PNG sheets, mapped to the engine palette |
| `python3 neon_dojo_terminal.py` | Your terminal, at least 72×23 cells | PNG sheets converted to colored half-block characters |

All three include single player, Add Server, Join Server, player settings, combat,
round finishers, and the castle wedding story. The graphical editions share the
same controller and 400×240 scene so you can compare the rendering engines.
Both graphical versions require a desktop display; the terminal edition works
in a terminal or SSH session. Controls are listed below.

Each launcher checks its Python dependencies before loading the game. When
something is missing or too old, it creates `.venv-variants` beside the scripts,
installs the required packages with progress and pip logs, and automatically
restarts itself. Later launches silently reuse the installed packages. There is
no need to activate the environment or run pip manually. Installation needs
internet access and a writable project directory. If setup fails, the launcher
prints a recovery command; it does not install into system Python. On Linux,
creating the environment may require the OS package `python3-venv`.

The bundled `assets/*.aseprite` files are editable source documents. **Aseprite
is an optional artwork editor, not a runtime dependency**: you do not need to
buy or install it to play. The launchers use the bundled PNG/JSON exports.
See [the asset workflow](assets/README.md) for editing and exporting from
Aseprite. Rebuild the original artwork with `build_sprite_assets.py`; doing so
replaces the bundled sources and exports with the original code-authored art.

To preview another PNG in your terminal:

```bash
python3 png_to_terminal.py path/to/character.png --width 24
```

For finite rendering checks, each edition supports `--smoke-test`. The pygame
edition uses SDL's dummy driver for that check; Pyxel's check still opens a
graphical window. The terminal check validates PNG rendering without starting
interactive curses. Use `--help` for screenshot and scene options where supported.

### Original terminal edition

```bash
python3 neon_dojo.py
```

Use a terminal window at least **72 columns × 23 rows**. A Unicode-capable terminal with a dark background gives the best result.

On the first launch, NEON DOJO checks the Python runtime, terminal graphics, Unicode support, and TCP/UDP networking. It shows each check with a progress bar and records successful setup in the user cache. Later launches verify the same requirements silently and open the menu immediately.

If something is unavailable, the setup screen prints the command or configuration needed to fix it. On Windows it automatically installs `windows-curses` with pip when required and streams the installation log. The setup result is stored at `~/.cache/neon-dojo/setup.json` on Linux/macOS or the matching user cache location selected by `XDG_CACHE_HOME`.

## Controls

| Key | Action |
|---|---|
| `←` / `→` or `A` / `D` | Move |
| `↑` or `W` | Jump |
| `↓` or `S` | Crouch / sit down |
| `Z` | Punch |
| `X` | Kick |
| `C` | Arc Burst (costs 35 ARC) |
| `Space` | Block |
| `P` or `Esc` | Pause / resume |
| `Q` | Quit |

Defeat your opponent in a best-of-three match. Land hits to charge the ARC meter, then use Arc Burst for heavy damage.

## Story

Two knights duel in a jungle clearing beneath Tangled's castle. Tangled watches from a high window, lets down her golden hair, and calls encouragement during the fight. Her portrait uses animated terminal pixel art with golden hair, a white face, green eyes, a purple dress, and pink royal embroidery. Knights have shaded steel armor, team-colored tunics and shields, and distinct movement, attack, and story poses. Two pixel rows share each terminal cell to keep characters proportionate. A 256-color terminal gives the richest colors; eight-color and monochrome terminals also work.

Every decisive round ends with a short, stylized **Royal Finish**: the winning knight approaches, strikes through a flash of sparks, and leaves the defeated knight's armor on the field. The sequence is theatrical and contains no gore. After the final victory, the champion crosses the clearing, climbs Tangled's hair into the castle, and joins her for the wedding finale.

Open **Settings** from the main menu to use your operating-system username or save a custom fighter name. The choice is remembered in `~/.config/neon-dojo/settings.json` (or the matching `XDG_CONFIG_HOME` path), and multiplayer opponents see the name you selected.

## Game modes

- **Single Player** — fight the CPU-controlled Onyx with your selected fighter name.
- **Add Server** — host a two-player match. The game shows the address you can share.
- **Join Server** — join with your selected fighter name. The game waits and automatically discovers an available server on the same local network.

For a local multiplayer match, run the game on both computers. One player chooses **Add Server**, then the other chooses **Join Server**. Discovery starts automatically.

For a routed or WAN match, the host must allow/forward TCP port `48765`. Automatic discovery checks every active IPv4 interface, sends directed LAN broadcasts, probes known online Tailscale peers and their advertised `/24` or smaller subnet routes, and scans this project's `100.64.0.*` tailnet range with UDP. You can still press `I` on **Join Server** and enter the reachable host address manually, such as:

```text
203.0.113.10:48765
```

Discovery uses UDP port `48765`; gameplay uses TCP port `48765`. TCP and UDP can share the same port number. LAN broadcasts do not cross routers, so routed discovery uses unicast probes.

When `hamedvm` runs **Add Server**, the joining player should enter:

```text
2.1.1.70:48765
```

This routed TCP path has been verified. If automatic discovery cannot traverse a network's routing or firewall rules, press `I` on the **Join Server** screen to enter the address.

On an asymmetric or routed network, the joining computer may be reachable even when it cannot initiate a connection to the host. In that case:

1. The remote player selects **Join Server** and waits.
2. The host selects **Add Server**, presses `I`, and enters the waiting player's reachable address.
3. The host establishes the connection in the working direction while keeping the host/player roles unchanged.

For the reverse `hamedvm` route, enter `2.1.1.70:48765` on the host's **Add Server** screen after the VM is waiting on **Join Server**.

## Notes

- Linux and macOS include `curses` with Python.
- Windows users can install `windows-curses` with `py -m pip install windows-curses`, then run `py neon_dojo.py`.
- If a firewall asks for permission, allow Python to use private networks so LAN discovery can work.

## License

NEON DOJO is available under the [MIT License](LICENSE).
