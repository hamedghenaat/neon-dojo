"""Original small fantasy pixel art and terminal half-block rendering.

Two square source pixels share one terminal cell. Art is authored here, not
copied from the reference packs listed in ART_REFERENCES.md.
"""
from __future__ import annotations

import importlib

try:
    import curses
except ImportError:
    curses = None  # First-run setup may install windows-curses later.
from collections.abc import Callable

KNIGHT_WIDTH = 17
KNIGHT_HEIGHT = 18


def _canvas(width: int, height: int) -> list[list[str]]:
    return [[" "] * width for _ in range(height)]


def _stamp(canvas: list[list[str]], x: int, y: int, rows: tuple[str, ...]) -> None:
    for dy, row in enumerate(rows):
        for dx, pixel in enumerate(row):
            if pixel != " " and 0 <= y + dy < len(canvas) and 0 <= x + dx < len(canvas[0]):
                canvas[y + dy][x + dx] = pixel


def _line(canvas: list[list[str]], start: tuple[int, int], end: tuple[int, int], ink: str) -> None:
    x, y = start
    dx, dy = end[0] - x, end[1] - y
    steps = max(abs(dx), abs(dy))
    for i in range(steps + 1):
        fraction = i / max(1, steps)
        px, py = round(x + dx * fraction), round(y + dy * fraction)
        if 0 <= py < len(canvas) and 0 <= px < len(canvas[0]):
            canvas[py][px] = ink


def knight_pixels(action: str, tick: int, facing: int = 1) -> list[str]:
    """A fixed 17x18 canvas keeps every pose on the same floor and center."""
    art = _canvas(KNIGHT_WIDTH, KNIGHT_HEIGHT)
    if action == "fallen":
        _stamp(art, 1, 13, (" rRr        SS", "KLLMKTTTTKKSG", "KLOMKttTTmmBB", " KKKKKKKKKKK"))
    else:
        crouch = action in ("crouch", "defeated")
        head_y = 4 if crouch else 0
        head_x = 5 if action == "hurt" else 4
        plume = ("  RRRr", " RRRr ") if (tick // 8) % 2 else (" RRRr ", "RRRr  ")
        _stamp(art, head_x, head_y, plume + (
            " KLLLK", "KLLMMmK", "KLMMMMK", "KLOTTMK", " KmOOmK", "  KmmK",
        ))
        body_y = head_y + 8
        _stamp(art, 4, body_y, ("KLLTTLK", "KLTTTtK", " KTTttK", " KGGGK "))
        leg_y = 16 if crouch else 12
        if action == "kick":
            _stamp(art, 5, leg_y, ("mMKK", "mMKKLLLLK", "mMK KMMmBB", "mMK", "BBK", "BBB"))
        elif action == "jump":
            _stamp(art, 4, leg_y, ("mMK KMM", " mMKMm", "  BBB", "  BBB"))
        elif action == "climb":
            _stamp(art, 4, leg_y, ("mM  mM", "mM  BB", "mM", "BB", "BBB"))
            _stamp(art, 10, 5 + (tick // 5) % 2, ("FF", "mM", "mM", "mM"))
        elif crouch:
            _stamp(art, 3, leg_y, ("KBB  BBK", "BBBB BBBB"))
        elif action == "walk" and (tick // 5) % 2:
            _stamp(art, 3, leg_y, (" mMK mM", " mMK mM", "mMK   mM", "mMK   mM", "BBK   BB", "BBB   BBB"))
        else:
            _stamp(art, 4, leg_y, (" mM mM", " mM mM", " mM mM", " mM mM", "KBB KBB", "BBB BBB"))

        # Distinct shield silhouette and a small gold cross.
        shield = (" KGGGK", "KGTTTG", "GTTETG", "GTEEEG", "GTTETG", " KGtGK", "  KGK")
        _stamp(art, 9 if action == "block" else 0, 7 if action == "block" else min(9 + head_y, 11), shield)
        if action not in ("block", "climb", "defeated"):
            hand = (11, min(body_y + 1, 14))
            tip = (15, 3 + head_y)
            if action == "punch":
                tip = (16, body_y)
            elif action == "finish":
                tip = (16, 5 if (tick // 3) % 2 else 12)
            elif action == "victory":
                hand, tip = (11, 6), (11, 0)
            elif action == "hurt":
                hand, tip = (12, 12), (16, 7)
            _line(art, (9, body_y + 1), hand, "m")
            _line(art, hand, tip, "S")
            _stamp(art, hand[0] - 1, hand[1], ("GGG", " F "))
            if action == "special":
                _stamp(art, 13, 3, ("  A", " A ", "A A", " A ", "A A", " A ", "  A"))
    lines = ["".join(row) for row in art]
    return lines if facing == 1 else [line[::-1] for line in lines]


def princess_pixels(tick: int) -> list[str]:
    """Nine pixels wide, fourteen tall: white face, gold hair, lilac gown."""
    eyes = " YFFFFFY " if tick % 110 < 4 else " YFEFEFY "
    return [
        "   YYY   ", "  YyyyY  ", " YyyYYyY ", " YFFFFFY ",
        eyes, " YFFSFFY ", " YyFFFyY ", " YYpFpYY ",
        " YpPHPpY ", " FpPHPpF ", " FpPPppF ", "  pPPpp  ",
        " pPPPPpp ", "pHHHHHHpp",
    ]


def balcony_knight_pixels() -> list[str]:
    return [
        "   Rrr   ", "  RRR    ", "  KLLK   ", " KLLMmK  ",
        " KLOOMK  ", "  KmmK   ", " KLTtLK  ", "GGTTttK  ",
        "GETTttK  ", "GGKGGK   ", "  mM mM  ", "  mM mM  ",
        " KBBKBB  ", " BBBBBB  ",
    ]


# Semantic materials use the same palette across every animation and character.
# Values are xterm-256 indices and portable eight-color fallbacks.
COLORS = {
    "outline": (235, 0), "steel": (250, 7),
    "steel_light": (255, 7), "steel_dark": (240, 4),
    "cyan": (45, 6), "cyan_dark": (30, 4),
    "magenta": (171, 5), "magenta_dark": (90, 4),
    "red": (203, 1), "red_dark": (124, 1),
    "gold": (220, 3), "gold_light": (229, 3),
    "white": (231, 7), "green": (35, 2),
    "purple": (141, 5), "purple_dark": (97, 4),
    "pink": (218, 5),
}


def knight_materials(team: int) -> dict[str, str]:
    return {
        "K": "outline", "L": "steel_light", "M": "steel", "m": "steel_dark",
        "O": "outline", "T": "cyan" if team == 2 else "magenta",
        "t": "cyan_dark" if team == 2 else "magenta_dark", "R": "red", "r": "red_dark",
        "G": "gold", "E": "gold_light", "S": "steel_light", "F": "white",
        "B": "outline", "A": "cyan",
    }


PRINCESS_MATERIALS = {
    "Y": "gold", "y": "gold_light", "F": "white", "E": "green",
    "S": "pink", "P": "purple", "p": "purple_dark", "H": "pink",
}


class PixelRenderer:
    """Paint two pixels per cell with stable color pairs and bounded allocation.

    Blank source cells are untouched. At a half-pixel edge the unoccupied half
    uses the terminal's default background, rather than a colored rectangle.
    Limited terminals fall back to shaded half blocks without changing size.
    """

    def __init__(self, put: Callable[..., None], colors: bool, background: int = -1) -> None:
        global curses
        if curses is None:
            curses = importlib.import_module("curses")
        self.put = put
        self.has_colors = colors
        self.background = background
        self.extended = colors and curses.COLORS >= 256
        self.pairs: dict[tuple[int, int], int | None] = {}
        self.next_pair = 9  # Pairs 1..8 belong to the HUD and scenery.
        self.limit = min(curses.COLOR_PAIRS, 256) if colors else 0

    def _color(self, material: str | None) -> int:
        if material is None:
            return self.background
        return COLORS[material][0 if self.extended else 1]

    def _pair(self, foreground: int, background: int) -> int | None:
        key = (foreground, background)
        if key in self.pairs:
            return self.pairs[key]
        if self.next_pair >= self.limit:
            return None
        pair = self.next_pair
        try:
            curses.init_pair(pair, foreground, background)
        except curses.error:
            self.pairs[key] = None
            return None
        self.pairs[key] = pair
        self.next_pair += 1
        return pair

    def draw(self, rows: list[str], x: int, y: int, materials: dict[str, str], flash: bool = False) -> None:
        width = max(map(len, rows), default=0)
        for row in range(0, len(rows), 2):
            upper = rows[row].ljust(width)
            lower = rows[row + 1].ljust(width) if row + 1 < len(rows) else " " * width
            for col, (a, b) in enumerate(zip(upper, lower)):
                if a == b == " ":
                    continue
                top = ("white" if flash else materials[a]) if a != " " else None
                bottom = ("white" if flash else materials[b]) if b != " " else None
                # Swap halves when only the bottom is occupied, so foreground
                # always holds a real color even without default-color support.
                char = "▄" if top is None else "▀"
                fg, bg = (bottom, None) if top is None else (top, bottom)
                pair = self._pair(self._color(fg), self._color(bg)) if self.has_colors else None
                if pair is not None:
                    attr = curses.color_pair(pair)
                    if not self.extended and fg in ("white", "steel_light", "gold_light"):
                        attr |= curses.A_BOLD
                else:
                    # Preserve silhouettes and material detail without colors.
                    if top is not None and bottom is not None:
                        char = "█" if top == bottom else "▒"
                    attr = curses.A_DIM if fg in ("outline", "steel_dark", "purple_dark") else curses.A_BOLD
                self.put(y + row // 2, x + col, char, attr)
