#!/usr/bin/env python3
"""NEON DOJO — a real-time terminal fighting game using only Python stdlib."""

from __future__ import annotations

try:
    import curses
except ImportError:
    curses = None  # type: ignore[assignment]

import getpass
import json
import importlib
import locale
import math
import os
import platform
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from networking import (
    NetworkSession,
    apply_game_data,
    local_server_addresses,
    network_ready,
    normalize_player_name as normalize_character_name,
)


FPS = 30
ROUND_TIME = 60.0
FINISHER_DURATION = 3.8
WEDDING_DURATION = 6.2
MIN_WIDTH = 72
MIN_HEIGHT = 23
SPRITE_WIDTH = 17
MENU_ITEMS = ("SINGLE PLAYER", "ADD SERVER", "JOIN SERVER", "SETTINGS")
SETTINGS_ITEMS = ("USE OS USERNAME", "SET CUSTOM NAME", "BACK")
SETUP_VERSION = 1
MIN_PYTHON = (3, 10)


@dataclass(frozen=True)
class DependencyResult:
    key: str
    label: str
    ready: bool
    detail: str
    command: str = ""


def setup_cache_path() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_root / "neon-dojo" / "setup.json"


def settings_path() -> Path:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "neon-dojo" / "settings.json"


def os_username() -> str:
    try:
        return normalize_character_name(getpass.getuser())
    except (OSError, KeyError):
        return "PLAYER"


@dataclass
class PlayerSettings:
    name_source: str = "os"
    custom_name: str = ""

    @property
    def character_name(self) -> str:
        if self.name_source == "custom" and self.custom_name:
            return normalize_character_name(self.custom_name)
        return os_username()


def load_settings() -> PlayerSettings:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PlayerSettings()
    if not isinstance(data, dict):
        return PlayerSettings()
    source = data.get("name_source")
    custom_name = normalize_character_name(data.get("custom_name", ""), "")
    if source == "custom" and custom_name:
        return PlayerSettings("custom", custom_name)
    return PlayerSettings()


def save_settings(settings: PlayerSettings) -> bool:
    path = settings_path()
    data = {
        "name_source": settings.name_source,
        "custom_name": settings.custom_name,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def dependency_signature() -> dict[str, object]:
    return {
        "setup_version": SETUP_VERSION,
        "python": list(sys.version_info[:3]),
        "executable": sys.executable,
        "platform": platform.system(),
    }


def _unicode_ready() -> tuple[bool, str]:
    encoding = sys.stdout.encoding or locale.getpreferredencoding(False) or "utf-8"
    try:
        "█✦━".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False, f"terminal encoding is {encoding}"
    return True, f"Unicode terminal encoding ({encoding})"


def dependency_checks() -> list[DependencyResult]:
    python_ready = sys.version_info >= MIN_PYTHON
    unicode_ready, unicode_detail = _unicode_ready()
    udp_ready, udp_detail = network_ready()
    system = platform.system()
    if system == "Windows":
        curses_command = f'"{sys.executable}" -m pip install windows-curses'
    elif system == "Linux":
        curses_command = "sudo dnf install python3-curses  # Fedora; Python normally includes curses on Debian/Ubuntu"
    else:
        curses_command = "Install a Python build that includes the standard curses module"
    return [
        DependencyResult(
            "python",
            "Python runtime",
            python_ready,
            f"Python {platform.python_version()}" if python_ready else "Python 3.10 or newer is required",
            "Install Python 3.10+ from https://python.org/downloads/",
        ),
        DependencyResult(
            "curses",
            "Terminal graphics",
            curses is not None,
            "curses module available" if curses is not None else "curses module is missing",
            curses_command,
        ),
        DependencyResult(
            "unicode",
            "Knight graphics",
            unicode_ready,
            unicode_detail,
            "Set your terminal locale to UTF-8, for example: export LANG=C.UTF-8",
        ),
        DependencyResult(
            "network",
            "Multiplayer networking",
            udp_ready,
            udp_detail,
            "Allow Python TCP/UDP access in your firewall, then run the game again",
        ),
    ]


def _setup_cache_matches() -> bool:
    try:
        data = json.loads(setup_cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data == dependency_signature()


def _save_setup_cache() -> None:
    path = setup_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dependency_signature(), indent=2), encoding="utf-8")
    except OSError:
        # A read-only home directory should not prevent the game from running.
        pass


def _draw_setup_progress(done: int, total: int, label: str) -> None:
    width = 30
    filled = round(width * done / total)
    bar_text = "█" * filled + "░" * (width - filled)
    percent = round(100 * done / total)
    line = f"  [{bar_text}] {percent:3d}%  {label}"
    if sys.stdout.isatty():
        print("\r" + line.ljust(78), end="", flush=True)
    else:
        print(line)


def _install_windows_curses() -> bool:
    command = [sys.executable, "-m", "pip", "install", "windows-curses"]
    print(f"\n  Installing: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        print(f"  [ERROR] Could not start installer: {error}")
        return False
    assert process.stdout is not None
    for line in process.stdout:
        print(f"  pip | {line.rstrip()}")
    if process.wait() != 0:
        return False
    try:
        global curses
        curses = importlib.import_module("curses")
    except ImportError:
        return False
    return True


def ensure_dependencies() -> bool:
    """Check every launch, but show the setup screen only when needed."""
    results = dependency_checks()
    if _setup_cache_matches() and all(result.ready for result in results):
        return True

    print("\n  ╔════════════════════════════════════════════════════╗")
    print("  ║       NEON DOJO // FIRST-RUN SYSTEM CHECK         ║")
    print("  ╚════════════════════════════════════════════════════╝\n")
    total = len(results)
    for index, result in enumerate(results, 1):
        _draw_setup_progress(index, total, f"Checking {result.label}")
        if sys.stdout.isatty():
            time.sleep(0.12)
            print()
        marker = "OK" if result.ready else "MISSING"
        print(f"  [{marker:<7}] {result.label}: {result.detail}")

    missing = [result for result in results if not result.ready]
    if any(result.key == "curses" for result in missing) and platform.system() == "Windows":
        if _install_windows_curses():
            print("  [OK     ] Terminal graphics: windows-curses installed")
            results = dependency_checks()
            missing = [result for result in results if not result.ready]

    if missing:
        print("\n  Setup could not finish automatically. Run the command(s) below:")
        for result in missing:
            print(f"\n  {result.label}:\n    {result.command}")
        print("\n  Run python3 neon_dojo.py again after resolving the items above.\n")
        return False

    _save_setup_cache()
    _draw_setup_progress(total, total, "All systems ready")
    print("\n  [READY  ] Launching the arena...", flush=True)
    if sys.stdout.isatty():
        time.sleep(0.45)
    return True


@dataclass(frozen=True)
class Attack:
    name: str
    duration: float
    active_from: float
    active_to: float
    reach: float
    damage: int
    knockback: float
    meter_cost: int = 0


ATTACKS = {
    "punch": Attack("PUNCH", 0.28, 0.08, 0.16, 9.0, 7, 3.5),
    "kick": Attack("KICK", 0.44, 0.14, 0.27, 12.0, 11, 5.0),
    "special": Attack("ARC BURST", 0.72, 0.25, 0.44, 19.0, 18, 8.0, 35),
}


@dataclass
class Fighter:
    name: str
    x: float
    color: int
    facing: int = 1
    health: int = 100
    meter: int = 0
    wins: int = 0
    jump_y: float = 0.0
    velocity_y: float = 0.0
    action: str = "idle"
    action_time: float = 0.0
    action_hit: bool = False
    hitstun: float = 0.0
    block_time: float = 0.0
    flash_time: float = 0.0
    combo: int = 0
    combo_time: float = 0.0

    @property
    def airborne(self) -> bool:
        return self.jump_y > 0.05

    @property
    def blocking(self) -> bool:
        return self.block_time > 0 and not self.airborne and self.hitstun <= 0

    def reset(self, x: float, facing: int) -> None:
        wins = self.wins
        color = self.color
        name = self.name
        self.__dict__.update(Fighter(name, x, color, facing=facing).__dict__)
        self.wins = wins

    def start_attack(self, kind: str) -> bool:
        attack = ATTACKS[kind]
        if self.hitstun > 0 or self.action != "idle" or self.blocking:
            return False
        if attack.meter_cost and self.meter < attack.meter_cost:
            return False
        self.meter -= attack.meter_cost
        self.action = kind
        self.action_time = 0.0
        self.action_hit = False
        return True

    def update(self, dt: float) -> None:
        self.action_time += dt
        self.hitstun = max(0.0, self.hitstun - dt)
        self.block_time = max(0.0, self.block_time - dt)
        self.flash_time = max(0.0, self.flash_time - dt)
        self.combo_time = max(0.0, self.combo_time - dt)
        if self.combo_time <= 0:
            self.combo = 0

        if self.action in ATTACKS and self.action_time >= ATTACKS[self.action].duration:
            self.action = "idle"
            self.action_time = 0.0
        elif self.action == "walk" and self.action_time >= 0.12:
            self.action = "idle"
            self.action_time = 0.0
        elif self.action == "crouch" and self.action_time >= 0.45:
            self.action = "idle"
            self.action_time = 0.0
        elif self.action == "hurt" and self.hitstun <= 0:
            self.action = "idle"

        if self.airborne or self.velocity_y > 0:
            self.jump_y += self.velocity_y * dt
            self.velocity_y -= 42.0 * dt
            if self.jump_y <= 0:
                self.jump_y = 0.0
                self.velocity_y = 0.0
                if self.action == "jump":
                    self.action = "idle"


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    char: str
    color: int


@dataclass
class Game:
    player: Fighter
    enemy: Fighter
    state: str = "title"
    round_number: int = 1
    round_time: float = ROUND_TIME
    state_time: float = 0.0
    banner: str = ""
    particles: list[Particle] = field(default_factory=list)
    shake: float = 0.0
    freeze: float = 0.0
    ai_think: float = 0.0
    message: str = ""
    menu_index: int = 0
    mode: str = "single"
    network_status: str = ""
    server_address: str = ""
    settings: PlayerSettings = field(default_factory=PlayerSettings)
    settings_index: int = 0
    settings_message: str = ""
    round_winner: int = 0
    story_phase: int = 0

    def start_match(self, width: int) -> None:
        self.player.wins = 0
        self.enemy.wins = 0
        self.round_number = 1
        self.state = "intro"
        self.start_round(width)

    def start_round(self, width: int) -> None:
        self.player.reset(max(8, width * 0.22), 1)
        self.enemy.reset(min(width - 16, width * 0.72), -1)
        self.round_time = ROUND_TIME
        self.state = "intro"
        self.state_time = 0.0
        self.banner = f"ROUND {self.round_number}"
        self.particles.clear()
        self.shake = 0.0
        self.freeze = 0.0
        self.round_winner = 0
        self.story_phase = 0

    def update(self, dt: float, width: int) -> None:
        self.state_time += dt
        if self.freeze > 0:
            self.freeze = max(0.0, self.freeze - dt)
            self.update_particles(dt * 0.25)
            return
        self.update_particles(dt)
        self.shake = max(0.0, self.shake - dt)

        if self.state == "intro":
            if self.state_time > 1.0 and self.banner != "FIGHT!":
                self.banner = "FIGHT!"
            if self.state_time > 1.7:
                self.state = "fight"
                self.state_time = 0.0
                self.banner = ""
            return
        if self.state == "finisher":
            self.update_finisher(dt, width)
            return
        if self.state == "wedding":
            self.update_wedding(dt, width)
            return
        if self.state != "fight":
            return

        self.round_time = max(0.0, self.round_time - dt)
        self.player.update(dt)
        self.enemy.update(dt)
        self.keep_in_arena(width)
        self.face_each_other()
        self.resolve_attack(self.player, self.enemy)
        self.resolve_attack(self.enemy, self.player)

        if self.player.health <= 0 or self.enemy.health <= 0 or self.round_time <= 0:
            self.end_round()

    def keep_in_arena(self, width: int) -> None:
        half_sprite = SPRITE_WIDTH // 2
        left, right = float(half_sprite + 1), float(width - half_sprite - 2)
        for fighter in (self.player, self.enemy):
            fighter.x = max(left, min(right, fighter.x))
        gap = self.enemy.x - self.player.x
        if 0 < gap < 6:
            push = (6 - gap) / 2
            self.player.x = max(left, self.player.x - push)
            self.enemy.x = min(right, self.enemy.x + push)

    def face_each_other(self) -> None:
        if self.player.x < self.enemy.x:
            self.player.facing, self.enemy.facing = 1, -1
        else:
            self.player.facing, self.enemy.facing = -1, 1

    def move(self, fighter: Fighter, direction: int, dt: float) -> None:
        if self.state != "fight" or fighter.hitstun > 0 or fighter.blocking or fighter.action == "crouch":
            return
        speed = 30.0 if not fighter.airborne else 22.0
        fighter.x += direction * speed * max(dt, 1 / FPS)
        if fighter.action == "idle" and not fighter.airborne:
            fighter.action = "walk"
            fighter.action_time = 0.0

    def jump(self, fighter: Fighter) -> None:
        if self.state == "fight" and not fighter.airborne and fighter.hitstun <= 0:
            fighter.jump_y = 0.1
            fighter.velocity_y = 19.0
            fighter.action = "jump"
            fighter.action_time = 0.0

    def block(self, fighter: Fighter) -> None:
        if self.state == "fight" and fighter.hitstun <= 0 and not fighter.airborne:
            fighter.block_time = 0.22
            if fighter.action in ("idle", "walk"):
                fighter.action = "idle"

    def crouch(self, fighter: Fighter) -> None:
        if self.state == "fight" and fighter.hitstun <= 0 and not fighter.airborne:
            fighter.action = "crouch"
            fighter.action_time = 0.0

    def resolve_attack(self, attacker: Fighter, defender: Fighter) -> None:
        if attacker.action not in ATTACKS or attacker.action_hit:
            return
        attack = ATTACKS[attacker.action]
        if not (attack.active_from <= attacker.action_time <= attack.active_to):
            return
        in_front = (defender.x - attacker.x) * attacker.facing > 0
        distance = abs(defender.x - attacker.x)
        vertical_ok = abs(attacker.jump_y - defender.jump_y) < 7
        if not (in_front and distance <= attack.reach and vertical_ok):
            return

        attacker.action_hit = True
        blocked = defender.blocking and defender.facing == -attacker.facing
        damage = max(1, round(attack.damage * (0.25 if blocked else 1.0)))
        defender.health = max(0, defender.health - damage)
        defender.flash_time = 0.10
        defender.x += attacker.facing * attack.knockback * (0.4 if blocked else 1.0)
        attacker.meter = min(100, attacker.meter + (5 if blocked else 12))
        defender.meter = min(100, defender.meter + 7)
        if blocked:
            defender.hitstun = 0.10
            self.message = "BLOCKED"
            spark_color = 5
        else:
            defender.hitstun = 0.18 if attack.name == "PUNCH" else 0.28
            defender.action = "hurt"
            defender.action_time = 0.0
            attacker.combo += 1
            attacker.combo_time = 1.1
            self.message = attack.name
            spark_color = 4
        self.state_time = 0.0
        self.shake = 0.12 if attack.name != "ARC BURST" else 0.25
        self.freeze = 0.035 if blocked else (0.06 if attack.name != "ARC BURST" else 0.11)
        self.spawn_hit((attacker.x + defender.x) / 2, 6 + defender.jump_y, spark_color, attack.name == "ARC BURST")

    def spawn_hit(self, x: float, y: float, color: int, big: bool = False) -> None:
        chars = "*+x." if not big else "*+#@x"
        for _ in range(10 if not big else 24):
            angle = random.random() * math.tau
            speed = random.uniform(6, 18 if big else 12)
            self.particles.append(Particle(x, y, math.cos(angle) * speed, math.sin(angle) * speed, random.uniform(.18, .5), random.choice(chars), color))

    def update_particles(self, dt: float) -> None:
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life > 0:
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vy -= 18 * dt
                alive.append(p)
        self.particles = alive

    def end_round(self) -> None:
        if self.player.health == self.enemy.health:
            self.round_winner = 0
            self.banner = "DRAW - HONOR HOLDS"
            self.player.action = "victory"
            self.enemy.action = "victory"
            self.state = "round_over"
        elif self.player.health > self.enemy.health:
            self.player.wins += 1
            self.round_winner = 1
            self.begin_finisher(self.player, self.enemy)
        else:
            self.enemy.wins += 1
            self.round_winner = -1
            self.begin_finisher(self.enemy, self.player)
        self.state_time = 0.0

    def begin_finisher(self, winner: Fighter, loser: Fighter) -> None:
        self.state = "finisher"
        self.story_phase = 0
        self.banner = f"{winner.name} WINS"
        self.message = "THE ROYAL FINISH"
        winner.action = "walk"
        winner.action_time = 0.0
        loser.action = "defeated"
        loser.action_time = 0.0

    def story_fighters(self) -> tuple[Fighter, Fighter]:
        if self.round_winner == 1:
            return self.player, self.enemy
        return self.enemy, self.player

    def update_finisher(self, dt: float, width: int) -> None:
        winner, loser = self.story_fighters()
        winner.facing = 1 if loser.x > winner.x else -1
        loser.facing = -winner.facing
        target = loser.x - winner.facing * 7.0

        if self.state_time < 1.05:
            winner.action = "walk"
            step = min(abs(target - winner.x), 15.0 * dt)
            winner.x += step if target > winner.x else -step
            loser.action = "defeated"
        elif self.state_time < 1.85:
            winner.action = "finish"
            loser.action = "defeated"
            if self.story_phase == 0:
                self.story_phase = 1
                self.banner = "BRUTALITY!"
                loser.health = 0
                loser.flash_time = 0.18
                self.shake = 0.28
                self.spawn_hit(loser.x, 7, 4, big=True)
        else:
            winner.action = "victory"
            loser.action = "fallen"
            if self.story_phase < 2:
                self.story_phase = 2
                self.banner = f"{winner.name} CLAIMS THE ROUND"

        self.keep_in_arena(width)
        if self.state_time < FINISHER_DURATION:
            return
        if winner.wins >= 2:
            self.start_wedding(winner, loser)
        else:
            self.state = "round_over"
            self.state_time = 0.0

    def start_wedding(self, winner: Fighter, loser: Fighter) -> None:
        self.state = "wedding"
        self.state_time = 0.0
        self.story_phase = 0
        self.banner = "THE CASTLE AWAITS"
        self.message = "TANGLED: ASCEND, BRAVE KNIGHT!"
        winner.action = "walk"
        winner.jump_y = 0.0
        loser.action = "fallen"

    def update_wedding(self, dt: float, width: int) -> None:
        champion, loser = self.story_fighters()
        castle_x = width / 2
        loser.action = "fallen"

        if self.state_time < 1.6:
            champion.action = "walk"
            step = min(abs(castle_x - champion.x), 17.0 * dt)
            champion.x += step if castle_x > champion.x else -step
            champion.facing = 1 if castle_x >= champion.x else -1
        elif self.state_time < 4.4:
            self.story_phase = max(self.story_phase, 1)
            champion.action = "climb"
            champion.x += (castle_x - champion.x) * min(1.0, dt * 7.0)
            champion.jump_y = min(10.0, (self.state_time - 1.6) * 3.8)
            champion.facing = 1
            self.banner = "ASCEND TO TANGLED"
        else:
            champion.action = "victory"
            champion.x = castle_x
            champion.jump_y = 10.0
            if self.story_phase < 2:
                self.story_phase = 2
                self.spawn_hit(castle_x, 20, 3, big=True)
            self.banner = f"TANGLED ♥ {champion.name}"
            self.message = "A NEW LEGEND BEGINS"

        if self.state_time >= WEDDING_DURATION:
            self.state = "match_over"
            self.state_time = 0.0
            self.banner = f"TANGLED ♥ {champion.name}"

    def advance(self, width: int) -> None:
        if self.state != "round_over":
            return
        self.round_number += 1
        self.start_round(width)


def safe_add(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Draw clipped text and silently ignore resize-edge curses errors."""
    height, width = win.getmaxyx()
    if y < 0 or y >= height or x >= width or x + len(text) <= 0:
        return
    if x < 0:
        text, x = text[-x:], 0
    text = text[: max(0, width - x - 1)]
    if not text:
        return
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def bar(value: int, maximum: int, width: int, left_to_right: bool = True) -> str:
    filled = max(0, min(width, round(width * value / maximum)))
    empty = width - filled
    return ("█" * filled + "░" * empty) if left_to_right else ("░" * empty + "█" * filled)


def mirrored(lines: list[str]) -> list[str]:
    swap = str.maketrans("/\\()<>[]{}", "\\/)(><][}{")
    return [line.translate(swap)[::-1] for line in lines]


def _frame(*lines: str) -> list[str]:
    """Normalize a color-coded terminal sprite to one stable cell grid."""
    return [line.ljust(SPRITE_WIDTH)[:SPRITE_WIDTH] for line in lines]


def fighter_sprite(f: Fighter, tick: int) -> list[str]:
    """Return a tiny knight pose encoded as material/color cells.

    M/m = armor, R = plume, F = face, O = eye, H/E = shield/emblem,
    S/G = sword/guard, B = boots, and A = arc energy.
    """
    idle_a = _frame(
        "    RRR",
        "   RRRR     SS",
        "    MMMMM  SS",
        "   MMFOFMMSS",
        " HHMMMMMMG",
        " HEH mMMG",
        " HHH mMm",
        "     m m",
        "    BB BB",
    )
    idle_b = _frame(
        "     RRR",
        "    RRRR    SS",
        "    MMMMM  SS",
        "   MMFOFMMSS",
        " HHMMMMMMG",
        " HEH mMMG",
        " HHH mMm",
        "    m   m",
        "   BB   BB",
    )
    poses = {
        # A short sword jab reads as the quick punch attack.
        "punch": _frame(
            "    RRR",
            "   RRRR",
            "    MMMMM",
            "   MMFOFMM GSSSSS",
            " HHMMMMMMMG",
            " HEH mMMM",
            " HHH mMm",
            "     m m",
            "    BB BB",
        ),
        "kick": _frame(
            "    RRR",
            "   RRRR     SS",
            "    MMMMM  SS",
            "   MMFOFMMSS",
            " HHMMMMMMG",
            " HEH mMMG",
            " HHH mMm",
            "    m  mMMMM",
            "   BB",
        ),
        "special": _frame(
            "    RRR       A",
            "   RRRR    S AA",
            "    MMMMM S AAA",
            "   MMFOFMMSAAAAA",
            " HHMMMMMMG AAAAA",
            " HEH mMMG   AAA",
            " HHH mMm     A",
            "     m m",
            "    BB BB",
        ),
        "block": _frame(
            "    RRR",
            "   RRRR",
            "    MMMMM",
            "   MMFOFMM HHH",
            "   MMMMMMM HEH",
            "    mMMm  HHH",
            "    mMMm",
            "     m m",
            "    BB BB",
        ),
        "crouch": _frame(
            "    RRR",
            "   RRRR",
            "    MMMMM",
            " HHMMFOFMM  SS",
            " HEHMMMMMMGSS",
            " HHH mMMm",
            "    BB BB",
        ),
        "hurt": _frame(
            " RRR",
            "  RRRR        S",
            "   MMMMM     S",
            "  MMOFOMM   S",
            " HHMMMMMM  G",
            " HEH mMMm G",
            " HHH  mMm",
            "      m m",
            "     BB BB",
        ),
        "jump": _frame(
            "    RRR",
            "   RRRR     SS",
            "    MMMMM  SS",
            "   MMFOFMMSS",
            " HHMMMMMMG",
            " HEH mMMG",
            " HHH mMm",
            "    mBmB",
            "     BB",
        ),
        "defeated": _frame(
            "      RRR",
            "     RRRR",
            "      MMMMM",
            "     MMOFOMM",
            "   HHMMMMMM",
            "   HEH mMMm",
            "   HHH mMm",
            "      m m",
            "     BB BB",
        ),
        "finish": _frame(
            "    RRR       S",
            "   RRRR      S",
            "    MMMMM   S",
            "   MMFOFMM S",
            " HHMMMMMMMG",
            " HEH mMMM",
            " HHH mMm",
            "     m m",
            "    BB BB",
        ),
        "victory": _frame(
            "    RRR    SS",
            "   RRRR  SS",
            "    MMMMMS",
            "   MMFOFMG",
            " HHMMMMMMM",
            " HEH mMMm",
            " HHH mMm",
            "     m m",
            "    BB BB",
        ),
        "fallen": _frame(
            "",
            "",
            "",
            "",
            "",
            "",
            " RRR       SS",
            "HHMMMMMMMMG",
            "HEH BB BB",
        ),
        "climb": _frame(
            "     RRR",
            "    RRRR",
            "     MMMMM",
            "    MMFOFMM",
            "   HHMMMMMM",
            "   HEH mMMm",
            "   HHH mMm",
            "      m m",
            "     BB BB",
        ),
        "walk": idle_b if tick % 2 else idle_a,
        "idle": idle_b if (tick // 12) % 2 else idle_a,
    }
    key = "block" if f.blocking else f.action
    lines = poses.get(key, idle_a)
    return lines if f.facing == 1 else [line[::-1] for line in lines]


def tangled_sprite(tick: int) -> list[str]:
    """Return Tangled as a compact pixel-art princess inspired by her portrait.

    Y/y = golden hair, F = face, E = green eyes, N/S = nose/smile,
    P/p = purple dress, and H = the pink bodice detail.
    """
    eyes = " YFFFFFY " if tick % 90 in (0, 1, 2, 3) else " YFEFEFY "
    return [
        "   YYY   ",
        "  yYYYYy ",
        " yYFFFYy ",
        eyes,
        " YFFNFFY ",
        " yFFSFFy ",
        "  pPHPp  ",
        "  FPPPF  ",
        "   PPP   ",
    ]


class Renderer:
    def __init__(self, win: curses.window) -> None:
        self.win = win
        self.has_colors = curses.has_colors()
        if self.has_colors:
            curses.start_color()
            default_bg = -1
            try:
                curses.use_default_colors()
            except curses.error:
                default_bg = curses.COLOR_BLACK
            palette = [
                (curses.COLOR_WHITE, default_bg),
                (curses.COLOR_CYAN, default_bg),
                (curses.COLOR_MAGENTA, default_bg),
                (curses.COLOR_YELLOW, default_bg),
                (curses.COLOR_RED, default_bg),
                (curses.COLOR_BLUE, default_bg),
                (curses.COLOR_GREEN, default_bg),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
            ]
            for index, colors in enumerate(palette, 1):
                try:
                    curses.init_pair(index, *colors)
                except curses.error:
                    pass

    def c(self, pair: int, bold: bool = False, dim: bool = False) -> int:
        attr = curses.color_pair(pair) if self.has_colors else 0
        if bold:
            attr |= curses.A_BOLD
        if dim:
            attr |= curses.A_DIM
        return attr

    def draw(self, game: Game, tick: int) -> None:
        self.win.erase()
        height, width = self.win.getmaxyx()
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            self.draw_too_small(width, height)
            self.win.refresh()
            return
        shake_x = random.choice((-1, 0, 1)) if game.shake > 0 else 0
        shake_y = random.choice((-1, 0)) if game.shake > 0 else 0
        self.draw_arena(game, width, height, tick, shake_x, shake_y)
        if game.state == "title":
            self.draw_title(game, width, height, tick)
            self.win.refresh()
            return
        if game.state == "settings":
            self.draw_settings(game, width, height, tick)
            self.win.refresh()
            return
        if game.state in ("hosting", "searching"):
            self.draw_network_lobby(game, width, height, tick)
            self.win.refresh()
            return
        ground = height - 5 + shake_y
        if game.state not in ("wedding", "match_over"):
            self.draw_hud(game, width)
            self.draw_fighter(game.player, ground, tick, shake_x)
            self.draw_fighter(game.enemy, ground, tick, shake_x)
        elif game.state == "wedding":
            champion, loser = game.story_fighters()
            if game.state_time < 2.2:
                self.draw_fighter(loser, ground, tick, shake_x)
            if game.state_time < 4.4:
                self.draw_fighter(champion, ground, tick, shake_x)
        self.draw_particles(game, ground, shake_x)
        self.draw_overlays(game, width, height, tick)
        self.win.refresh()

    def draw_too_small(self, width: int, height: int) -> None:
        lines = ["NEON DOJO", "Terminal too small", f"Current: {width} x {height}", f"Needed: {MIN_WIDTH} x {MIN_HEIGHT}", "Resize the window or press Q"]
        for i, line in enumerate(lines):
            safe_add(self.win, max(0, height // 2 - 2 + i), max(0, (width - len(line)) // 2), line, self.c(2 if i == 0 else 1, True))

    def draw_arena(self, game: Game, width: int, height: int, tick: int, ox: int, oy: int) -> None:
        base = height - 7 + oy

        # Dense jungle frames the castle while leaving the fighters readable.
        tree_centers = (4, 14, width - 15, width - 5)
        for index, center in enumerate(tree_centers):
            sway = -1 if (tick // 18 + index) % 2 else 0
            canopy_y = 5 + (index % 2) + oy
            for row, leaves in enumerate(("♣♣♣", "♣♣♣♣♣", "♣♣♣♣♣♣♣", "♣♣♣♣♣")):
                safe_add(
                    self.win,
                    canopy_y + row,
                    center - len(leaves) // 2 + sway + ox,
                    leaves,
                    self.c(7, bold=row < 2, dim=row > 1),
                )
            for y in range(canopy_y + 4, base):
                trunk = "╲║╱" if y == canopy_y + 4 else " ║ "
                safe_add(self.win, y, center - 1 + ox, trunk, self.c(4, dim=True))
            vine_x = center + (-4 if center < width // 2 else 4) + ox
            for y in range(canopy_y + 1, min(base, canopy_y + 7)):
                safe_add(self.win, y, vine_x, "│" if (y + tick // 10) % 2 else "╵", self.c(7, dim=True))

        castle = (
            "                    /\\                    ",
            "             ______/  \\______             ",
            "            /      TANGLED      \\            ",
            "       ____|╔══════════════════╗|____       ",
            "  ____| [] |║                  ║| [] |____  ",
            " | [] |    |║                  ║|    | [] | ",
            " |    | [] |║                  ║| [] |    | ",
            " | [] |    |║                  ║|    | [] | ",
            " |    | [] |╚══════════════════╝| [] |    | ",
            " | [] |    |        ██        |    | [] | ",
            " |    | [] |        ██        | [] |    | ",
            " |____|____|________██________|____|____| ",
        )
        castle_width = max(map(len, castle))
        castle_x = (width - castle_width) // 2 + ox
        castle_y = 5 + oy
        for row, line in enumerate(castle):
            text = line.center(castle_width)
            attr = self.c(4, True) if row in (2, 3, 8) else self.c(6, bold=row in (0, 1), dim=row > 3)
            safe_add(self.win, castle_y + row, castle_x, text, attr)

        center = width // 2 + ox
        married = game.state == "match_over" or (game.state == "wedding" and game.state_time >= 4.4)
        tangled_center = center + (3 if married else 0)
        self.draw_tangled(tangled_center, castle_y + 3, base, tick)
        if married:
            self.draw_window_knight(game, center - 7, castle_y + 4)
            heart_center = min(width - 7, center + castle_width // 2 + 7)
            self.draw_wedding_heart(heart_center, castle_y + 3, tick)

        # Grass and roots replace the old neon grid floor.
        grass = "".join("♣" if (col + tick // 8) % 7 == 0 else "━" for col in range(width - 1))
        safe_add(self.win, base, 0, grass, self.c(7, True))
        for row in range(1, max(3, height - base - 1)):
            pattern = "".join("╱" if (col + row * 3) % 17 == 0 else ("·" if col % 2 == 0 else " ") for col in range(width - 1))
            safe_add(self.win, base + row, 0, pattern, self.c(4 if row > 2 else 7, dim=True))

    def draw_tangled(self, center: int, top: int, base: int, tick: int) -> None:
        sprite = tangled_sprite(tick)
        left = center - len(sprite[0]) // 2
        glyphs = {
            "Y": "▓",  # long golden hair
            "y": "▒",  # golden highlights
            "F": "█",  # bright white face and hands
            "E": "●",  # green eyes
            "N": "·",  # small nose
            "S": "⌣",  # smile
            "P": "█",  # royal purple dress
            "p": "▓",  # striped sleeves
            "H": "♥",  # pink bodice embroidery
        }
        colors = {
            "Y": self.c(4, True),
            "y": self.c(4),
            "F": self.c(1, True),
            "E": self.c(7, True),
            "N": self.c(4, True),
            "S": self.c(5, True),
            "P": self.c(3, True),
            "p": self.c(3),
            "H": self.c(5, True),
        }
        for row, line in enumerate(sprite):
            for col, code in enumerate(line):
                if code != " ":
                    safe_add(self.win, top + row, left + col, glyphs[code], colors[code])

        # One long braid hangs from the window and sways in the breeze.
        braid_x = left + len(sprite[0]) - 2
        for y in range(top + 5, base):
            sway = (y + tick // 12) % 2
            safe_add(self.win, y, braid_x + sway, "●", self.c(4, True))
        safe_add(self.win, base - 1, braid_x + 1, "◉", self.c(4, True))

    def draw_wedding_heart(self, center: int, top: int, tick: int) -> None:
        heart = (
            " ♥♥♥   ♥♥♥ ",
            "♥♥♥♥♥ ♥♥♥♥♥",
            "♥♥♥♥♥♥♥♥♥♥♥",
            " ♥♥♥♥♥♥♥♥♥ ",
            "  ♥♥♥♥♥♥♥  ",
            "   ♥♥♥♥♥   ",
            "    ♥♥♥    ",
            "     ♥     ",
        )
        width = max(map(len, heart))
        attr = self.c(5 if tick % 12 < 6 else 3, True)
        for row, line in enumerate(heart):
            for col, char in enumerate(line.center(width)):
                if char == "♥":
                    safe_add(self.win, top + row, center - width // 2 + col, char, attr)

    def draw_window_knight(self, game: Game, center: int, top: int) -> None:
        champion, _ = game.story_fighters()
        sprite = (" RRR ", " MMM ", "MFOFM", "HMMMG", "H m S", " m m ", "B   B")
        glyphs = {"R": "▓", "M": "█", "F": "▒", "O": "●", "H": "▐", "G": "◆", "S": "╱", "m": "▓", "B": "▄"}
        colors = {"R": 5, "M": champion.color, "F": 4, "O": 1, "H": champion.color, "G": 4, "S": 1, "m": champion.color, "B": champion.color}
        for row, line in enumerate(sprite):
            for col, code in enumerate(line):
                if code != " ":
                    safe_add(self.win, top + row, center - 2 + col, glyphs[code], self.c(colors[code], True))

    def draw_hud(self, game: Game, width: int) -> None:
        bar_width = max(14, min(32, (width - 24) // 2))
        timer = f"{math.ceil(game.round_time):02d}"
        player_label = f" {game.player.name} "
        enemy_label = f" {game.enemy.name} "
        safe_add(self.win, 0, 2, player_label, self.c(game.player.color, True))
        safe_add(self.win, 0, width - 2 - len(enemy_label), enemy_label, self.c(game.enemy.color, True))
        safe_add(self.win, 0, (width - 10) // 2, f"◢ {timer} ◣", self.c(4, True))
        safe_add(self.win, 1, 2, bar(game.player.health, 100, bar_width), self.c(game.player.color, True))
        safe_add(self.win, 1, width - 2 - bar_width, bar(game.enemy.health, 100, bar_width, False), self.c(game.enemy.color, True))
        safe_add(self.win, 2, 2, "◆" * game.player.wins + "◇" * (2 - game.player.wins), self.c(1, True))
        safe_add(self.win, 2, width - 4, "◇" * (2 - game.enemy.wins) + "◆" * game.enemy.wins, self.c(3, True))
        meter_w = max(10, bar_width - 6)
        safe_add(self.win, 3, 2, "ARC " + bar(game.player.meter, 100, meter_w), self.c(2))
        safe_add(self.win, 3, width - meter_w - 6, bar(game.enemy.meter, 100, meter_w, False) + " ARC", self.c(2))

    def draw_fighter(self, fighter: Fighter, ground: int, tick: int, ox: int) -> None:
        sprite = fighter_sprite(fighter, tick)
        x = round(fighter.x) - SPRITE_WIDTH // 2 + ox
        y = ground - len(sprite) - round(fighter.jump_y / 2)
        glyphs = {
            "R": "▓",  # red plume
            "M": "█",  # polished armor
            "m": "▓",  # shadowed armor
            "F": "▒",  # face
            "O": "●",  # eye slit
            "H": "▐" if fighter.facing == 1 else "▌",  # shield
            "E": "✚",  # shield emblem
            "S": "╱" if fighter.facing == 1 else "╲",  # blade
            "G": "◆",  # golden guard
            "B": "▄",  # boots
            "A": "✦",  # arc energy
        }
        colors = {
            "R": self.c(5, True),
            "M": self.c(fighter.color, True),
            "m": self.c(fighter.color, dim=True),
            "F": self.c(4, True),
            "O": self.c(1, True),
            "H": self.c(fighter.color, True),
            "E": self.c(5, True),
            "S": self.c(1, True),
            "G": self.c(4, True),
            "B": self.c(fighter.color, dim=True),
            "A": self.c(2 if tick % 4 < 2 else 4, True),
        }
        for row, line in enumerate(sprite):
            for col, code in enumerate(line):
                if code == " ":
                    continue
                attr = self.c(1, True) if fighter.flash_time > 0 else colors[code]
                safe_add(self.win, y + row, x + col, glyphs[code], attr)
        if fighter.airborne:
            shadow = "·" * 11
            safe_add(self.win, ground - 1, x + 3, shadow, self.c(6, dim=True))

    def draw_particles(self, game: Game, ground: int, ox: int) -> None:
        for p in game.particles:
            safe_add(self.win, ground - round(p.y / 2), round(p.x) + ox, p.char, self.c(p.color, True))

    def draw_overlays(self, game: Game, width: int, height: int, tick: int) -> None:
        if game.state in ("intro", "fight") and tick % 180 < 118:
            cheers = (
                "TANGLED: FIGHT, BRAVE KNIGHTS!",
                "TANGLED: SHOW YOUR COURAGE!",
                "TANGLED: ONE SHALL ASCEND!",
            )
            cheer = cheers[(tick // 180) % len(cheers)]
            safe_add(self.win, 4, (width - len(cheer)) // 2, cheer, self.c(4, True))
        if game.banner:
            attr = self.c(4 if game.banner == "FIGHT!" else 3, True) | (curses.A_REVERSE if game.banner == "FIGHT!" and tick % 6 < 3 else 0)
            text = f"  {game.banner}  "
            banner_y = 3 if game.state in ("wedding", "match_over") else height // 2 - 3
            safe_add(self.win, banner_y, (width - len(text)) // 2, text, attr)
        if game.state == "finisher":
            story = "TANGLED: THE VICTOR CLAIMS THE FIELD!" if game.story_phase >= 2 else game.message
            safe_add(self.win, 4, (width - len(story)) // 2, story, self.c(4, True))
        if game.state == "round_over":
            text = "WAITING FOR HOST" if game.mode == "client" else "ENTER  CONTINUE"
            safe_add(self.win, height // 2 - 1, (width - len(text)) // 2, text, self.c(1, True))
        elif game.state == "wedding":
            story = game.message if game.story_phase >= 2 else "THE CHAMPION CLIMBS TANGLED'S GOLDEN HAIR"
            safe_add(self.win, height - 2, (width - len(story)) // 2, story, self.c(4, True))
        elif game.state == "match_over":
            text = "WAITING FOR HOST" if game.mode == "client" else "ENTER  REMATCH    Q  QUIT"
            legend = "THE CHAMPION AND TANGLED ARE MARRIED"
            safe_add(self.win, height - 3, (width - len(legend)) // 2, legend, self.c(4, True))
            safe_add(self.win, height - 2, (width - len(text)) // 2, text, self.c(1, True))
        elif game.state == "paused":
            text = "  HOST PAUSED  " if game.mode == "client" else "  PAUSED  "
            safe_add(self.win, height // 2 - 2, (width - len(text)) // 2, text, self.c(3, True) | curses.A_REVERSE)
            hint = "WAITING FOR HOST" if game.mode == "client" else "P / ESC  RESUME"
            safe_add(self.win, height // 2, (width - len(hint)) // 2, hint, self.c(1))
        if game.state == "fight" and game.message and game.state_time < 0.55:
            safe_add(self.win, 5, (width - len(game.message)) // 2, game.message, self.c(4, True))
        for f, side in ((game.player, 1), (game.enemy, -1)):
            if f.combo >= 2 and f.combo_time > 0:
                text = f"{f.combo} HIT COMBO"
                x = 3 if side == 1 else width - len(text) - 3
                safe_add(self.win, 5, x, text, self.c(f.color, True))
        if game.state not in ("wedding", "match_over"):
            safe_add(self.win, height - 1, 1, "← → move  ↑ jump  ↓ crouch  Z punch  X kick  C arc  SPACE block  P pause  Q quit", self.c(1, dim=True))

    def draw_title(self, game: Game, width: int, height: int, tick: int) -> None:
        logo = [
            "███╗  ██╗███████╗ ██████╗ ███╗  ██╗",
            "████╗ ██║██╔════╝██╔═══██╗████╗ ██║",
            "██╔██╗██║█████╗  ██║   ██║██╔██╗██║",
            "██║╚████║██╔══╝  ██║   ██║██║╚████║",
            "██║ ╚███║███████╗╚██████╔╝██║ ╚███║",
        ]
        start_y = max(4, height // 2 - 8)
        for row, line in enumerate(logo):
            safe_add(self.win, start_y + row, (width - len(line)) // 2, line, self.c(2 if row % 2 == 0 else 1, True))
        subtitle = "D  O  J  O"
        safe_add(self.win, start_y + 6, (width - len(subtitle)) // 2, subtitle, self.c(3, True))
        for index, item in enumerate(MENU_ITEMS):
            selected = index == game.menu_index
            label = f"▶ {item} ◀" if selected else f"  {item}  "
            attr = self.c(4 if selected else 1, True)
            if selected and tick % 20 < 10:
                attr |= curses.A_REVERSE
            safe_add(self.win, start_y + 8 + index, (width - len(label)) // 2, label, attr)
        hint = "↑ ↓ SELECT   ENTER CONFIRM   Q QUIT"
        safe_add(self.win, start_y + 13, (width - len(hint)) // 2, hint, self.c(1, dim=True))
        safe_add(self.win, height - 2, (width - 39) // 2, "Solo · LAN discovery · direct WAN address", self.c(6, dim=True))

    def draw_settings(self, game: Game, width: int, height: int, tick: int) -> None:
        title = "PLAYER SETTINGS"
        safe_add(self.win, 4, (width - len(title)) // 2, title, self.c(2, True))
        current = f"FIGHTER NAME: {game.settings.character_name}"
        source = "OS USERNAME" if game.settings.name_source == "os" else "CUSTOM NAME"
        source_line = f"SOURCE: {source}"
        safe_add(self.win, 6, (width - len(current)) // 2, current, self.c(4, True))
        safe_add(self.win, 7, (width - len(source_line)) // 2, source_line, self.c(1, dim=True))
        for index, item in enumerate(SETTINGS_ITEMS):
            selected = index == game.settings_index
            if index == 0:
                item = f"{item}: {os_username()}"
            label = f"▶ {item} ◀" if selected else f"  {item}  "
            attr = self.c(3 if selected else 1, True)
            if selected and tick % 20 < 10:
                attr |= curses.A_REVERSE
            safe_add(self.win, 10 + index * 2, (width - len(label)) // 2, label, attr)
        if game.settings_message:
            safe_add(self.win, 17, (width - len(game.settings_message)) // 2, game.settings_message, self.c(7, True))
        hint = "↑ ↓ SELECT   ENTER CONFIRM   ESC BACK"
        safe_add(self.win, height - 2, (width - len(hint)) // 2, hint, self.c(1, dim=True))

    def draw_network_lobby(self, game: Game, width: int, height: int, tick: int) -> None:
        hosting = game.state == "hosting"
        title = "ADD SERVER" if hosting else "JOIN SERVER"
        safe_add(self.win, 5, (width - len(title)) // 2, title, self.c(2 if hosting else 3, True))
        box_width = min(54, width - 8)
        left = (width - box_width) // 2
        safe_add(self.win, 7, left, "┏" + "━" * (box_width - 2) + "┓", self.c(2))
        for row in range(8, 15):
            safe_add(self.win, row, left, "┃", self.c(2))
            safe_add(self.win, row, left + box_width - 1, "┃", self.c(2))
        safe_add(self.win, 15, left, "┗" + "━" * (box_width - 2) + "┛", self.c(2))
        if hosting:
            heading = "SERVER ONLINE"
            status = game.network_status or "Waiting for another knight"
            address = f"Share: {game.server_address}"
            safe_add(self.win, 9, (width - len(heading)) // 2, heading, self.c(7, True))
            safe_add(self.win, 11, (width - len(status)) // 2, status, self.c(1))
            safe_add(self.win, 13, (width - len(address)) // 2, address, self.c(4, True))
            invite = "Press I to invite a routed player by IP"
            safe_add(self.win, 14, (width - len(invite)) // 2, invite, self.c(4, True))
        else:
            dots = "." * (1 + (tick // 10) % 3)
            heading = "SCANNING FOR SERVERS" + dots
            status = game.network_status or "Scanning IPv4 networks and Tailscale"
            safe_add(self.win, 9, (width - len(heading)) // 2, heading, self.c(3, True))
            safe_add(self.win, 11, (width - len(status)) // 2, status, self.c(1))
            direct = "Press I to enter or retry a routed / WAN address"
            safe_add(self.win, 13, (width - len(direct)) // 2, direct, self.c(4, True))
        cancel = "ESC  BACK TO MENU"
        safe_add(self.win, 17, (width - len(cancel)) // 2, cancel, self.c(1, dim=True))


def update_ai(game: Game, dt: float) -> None:
    if game.state != "fight":
        return
    ai, player = game.enemy, game.player
    if ai.hitstun > 0:
        return
    game.ai_think -= dt
    distance = abs(ai.x - player.x)
    toward = 1 if player.x > ai.x else -1

    # Blocking reacts immediately enough to feel smart, but is not guaranteed.
    if player.action in ATTACKS:
        attack = ATTACKS[player.action]
        if distance < attack.reach + 3 and random.random() < 0.16:
            game.block(ai)

    if game.ai_think > 0:
        if distance > 9:
            game.move(ai, toward, dt * 0.7)
        return
    game.ai_think = random.uniform(0.08, 0.24)

    if distance > 15:
        game.move(ai, toward, dt * random.uniform(1.0, 2.5))
        if random.random() < 0.05:
            game.jump(ai)
    elif distance < 6 and random.random() < 0.35:
        game.move(ai, -toward, dt * 2.0)
    elif ai.action == "idle":
        roll = random.random()
        if ai.meter >= 35 and roll < 0.18:
            ai.start_attack("special")
        elif roll < 0.57:
            ai.start_attack("punch")
        elif roll < 0.88:
            ai.start_attack("kick")
        else:
            game.block(ai)


def control_from_key(key: int) -> str | None:
    if key in (curses.KEY_LEFT, ord("a"), ord("A")):
        return "left"
    if key in (curses.KEY_RIGHT, ord("d"), ord("D")):
        return "right"
    if key in (curses.KEY_UP, ord("w"), ord("W")):
        return "jump"
    if key in (curses.KEY_DOWN, ord("s"), ord("S")):
        return "crouch"
    if key in (ord("z"), ord("Z")):
        return "punch"
    if key in (ord("x"), ord("X")):
        return "kick"
    if key in (ord("c"), ord("C")):
        return "special"
    if key == ord(" "):
        return "block"
    return None


def apply_control(game: Game, fighter: Fighter, command: str, dt: float) -> None:
    if command == "left":
        game.move(fighter, -1, dt * 2.1)
    elif command == "right":
        game.move(fighter, 1, dt * 2.1)
    elif command == "jump":
        game.jump(fighter)
    elif command in ATTACKS:
        fighter.start_attack(command)
    elif command == "block":
        game.block(fighter)
    elif command == "crouch":
        game.crouch(fighter)


def handle_input(
    win: curses.window,
    game: Game,
    dt: float,
    width: int,
    role: str,
) -> tuple[bool, str | None, list[str]]:
    keys: list[int] = []
    app_command: str | None = None
    outgoing: list[str] = []
    while True:
        try:
            key = win.getch()
        except curses.error:
            break
        if key == -1:
            break
        keys.append(key)
    for key in keys:
        if key in (ord("q"), ord("Q")):
            return False, None, outgoing
        if game.state == "title":
            if key in (curses.KEY_UP, ord("w"), ord("W")):
                game.menu_index = (game.menu_index - 1) % len(MENU_ITEMS)
            elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
                game.menu_index = (game.menu_index + 1) % len(MENU_ITEMS)
            elif key in (10, 13, curses.KEY_ENTER):
                if game.menu_index == 0:
                    game.mode = "single"
                    game.player.name = game.settings.character_name
                    game.enemy.name = "ONYX"
                    game.start_match(width)
                elif game.menu_index == 1:
                    app_command = "host"
                elif game.menu_index == 2:
                    app_command = "join"
                else:
                    game.state = "settings"
                    game.settings_index = 0
                    game.settings_message = ""
            continue
        if game.state == "settings":
            if key == 27:
                game.state = "title"
            elif key in (curses.KEY_UP, ord("w"), ord("W")):
                game.settings_index = (game.settings_index - 1) % len(SETTINGS_ITEMS)
            elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
                game.settings_index = (game.settings_index + 1) % len(SETTINGS_ITEMS)
            elif key in (10, 13, curses.KEY_ENTER):
                if game.settings_index == 0:
                    app_command = "use_os_name"
                elif game.settings_index == 1:
                    app_command = "custom_name"
                else:
                    game.state = "title"
            continue
        if game.state in ("hosting", "searching"):
            if key == 27:
                app_command = "menu"
            elif game.state == "searching" and key in (ord("i"), ord("I")):
                app_command = "direct"
            elif game.state == "hosting" and key in (ord("i"), ord("I")):
                app_command = "invite"
            continue
        if game.state == "match_over" and key in (10, 13, curses.KEY_ENTER) and role != "client":
            game.start_match(width)
            continue
        if game.state == "round_over" and key in (10, 13, curses.KEY_ENTER) and role != "client":
            game.advance(width)
            continue
        if key in (ord("p"), ord("P"), 27) and game.state in ("fight", "paused") and role != "client":
            game.state = "paused" if game.state == "fight" else "fight"
            game.state_time = 0.0
            continue
        if game.state != "fight":
            continue
        control = control_from_key(key)
        if control:
            if role == "client":
                outgoing.append(control)
            else:
                apply_control(game, game.player, control, dt)
    return True, app_command, outgoing


def prompt_server_address(win: curses.window, prompt: str = "Server IP or hostname[:port]: ") -> str:
    height, width = win.getmaxyx()
    y = min(height - 2, 19)
    win.nodelay(False)
    try:
        curses.echo()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        safe_add(win, y, 2, " " * max(0, width - 4))
        safe_add(win, y, 2, prompt, curses.A_BOLD)
        win.refresh()
        raw = win.getstr(y, min(width - 2, 2 + len(prompt)), max(1, min(60, width - len(prompt) - 4)))
        return raw.decode("utf-8", "replace").strip()
    except curses.error:
        return ""
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        win.nodelay(True)


def run(win: curses.window) -> None:
    locale.setlocale(locale.LC_ALL, "")
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    win.nodelay(True)
    win.keypad(True)
    renderer = Renderer(win)
    settings = load_settings()
    game = Game(Fighter(settings.character_name, 18, 2), Fighter("ONYX", 55, 3, facing=-1), settings=settings)
    last = time.monotonic()
    tick = 0
    running = True
    network: NetworkSession | None = None
    try:
        while running:
            frame_start = time.monotonic()
            dt = min(0.05, frame_start - last)
            last = frame_start
            height, width = win.getmaxyx()
            role = network.role if network else "single"
            running, app_command, outgoing = handle_input(win, game, dt, width, role)

            if app_command == "use_os_name":
                game.settings.name_source = "os"
                game.player.name = game.settings.character_name
                game.settings_message = "OS username selected" if save_settings(game.settings) else "Could not save settings"
            elif app_command == "custom_name":
                name = prompt_server_address(win, "Character name: ")
                if name:
                    game.settings.custom_name = normalize_character_name(name)
                    game.settings.name_source = "custom"
                    game.player.name = game.settings.character_name
                    game.settings_message = "Custom name saved" if save_settings(game.settings) else "Could not save settings"
            elif app_command == "menu":
                if network:
                    network.close()
                    network = None
                game.state = "title"
                game.network_status = ""
                game.server_address = ""
            elif app_command in ("host", "join"):
                if network:
                    network.close()
                try:
                    network_role = "host" if app_command == "host" else "client"
                    game.player.name = game.settings.character_name
                    game.enemy.name = "PLAYER"
                    network = NetworkSession(
                        network_role,
                        game.settings.character_name,
                        state_applier=lambda target, payload: apply_game_data(
                            target,
                            payload,
                            Fighter,
                            Particle,
                        ),
                    )
                    if app_command == "host":
                        game.mode = "host"
                        game.state = "hosting"
                        game.network_status = "Waiting for another knight"
                        game.server_address = local_server_addresses()
                    else:
                        game.mode = "client"
                        game.state = "searching"
                        game.network_status = "Scanning IPv4 networks and Tailscale"
                except OSError as error:
                    network = None
                    game.state = "hosting" if app_command == "host" else "searching"
                    game.network_status = f"Network error: {error}"
            elif app_command == "direct" and network and network.role == "client":
                address = prompt_server_address(win)
                if address:
                    try:
                        game.network_status = network.connect_direct(address)
                    except (OSError, ValueError) as error:
                        game.network_status = f"Address error: {error}"
            elif app_command == "invite" and network and network.role == "host":
                address = prompt_server_address(win, "Waiting player IP[:port]: ")
                if address:
                    try:
                        game.network_status = network.invite_player(address)
                    except (OSError, ValueError) as error:
                        game.network_status = f"Invite failed: {error}"

            if network and network.role == "client":
                for command in outgoing:
                    network.send_command(command)

            network_events: list[str] = []
            if network:
                network_events.extend(network.poll(game))
            for event in network_events:
                if event == "joined" and network and network.role == "host":
                    game.network_status = f"Knight joined from {network.peer[0]}"
                    game.start_match(width)
                elif event.startswith("input:") and network and network.role == "host":
                    apply_control(game, game.enemy, event.split(":", 1)[1], 1 / FPS)
                elif event == "found":
                    game.network_status = f"Found {network.peer[0]} — joining"
                elif event == "connected":
                    game.network_status = "Connected"
                elif event == "busy":
                    game.state = "searching"
                    game.network_status = "Server was busy — scanning again"
                elif event == "left" and network and network.role == "host":
                    network.reset_peer()
                    game.state = "hosting"
                    game.network_status = "Player left — waiting for another knight"
                elif event == "left" and network and network.role == "client":
                    network.reset_peer()
                    game.state = "searching"
                    game.network_status = "Host left — scanning again"

            if width >= MIN_WIDTH and height >= MIN_HEIGHT:
                if network is None:
                    update_ai(game, dt)
                    game.update(dt, width)
                elif network.role == "host" and network.peer:
                    game.update(dt, width)

            tick_events: list[str] = network.tick(game) if network else []
            if "timeout" in tick_events and network:
                if network.role == "host":
                    network.reset_peer()
                    game.state = "hosting"
                    game.network_status = "Connection lost — waiting for another knight"
                else:
                    network.reset_peer()
                    game.state = "searching"
                    game.network_status = "Connection lost — scanning again"

            renderer.draw(game, tick)
            tick += 1
            elapsed = time.monotonic() - frame_start
            time.sleep(max(0, 1 / FPS - elapsed))
    finally:
        if network:
            network.close()


def main() -> None:
    if not ensure_dependencies():
        raise SystemExit(1)
    assert curses is not None
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
