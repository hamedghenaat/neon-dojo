#!/usr/bin/env python3
"""Pyxel edition of NEON DOJO, using the bundled Aseprite PNG exports."""
from __future__ import annotations

import argparse
import os
import sys
from functools import lru_cache
from pathlib import Path
import time


class PyxelCanvas:
    """Adapt the shared scene to Pyxel with cached, transparent PNG frames.

    Palette index zero is reserved for transparency. Opaque black is allocated
    its own entry so outlines never disappear into the transparent background.
    Frames are cropped before conversion; sprite sheets need not fit an image
    bank, and integer scaling is nearest-neighbor with an unchanged top-left.
    """

    def __init__(self, engine):
        self.engine = engine
        self.palette: dict[int, int] = {}
        self._colors = [0xFF00FF]
        self._sync_palette()

    def _sync_palette(self):
        palette = self.engine.colors
        try:
            palette[:] = self._colors
        except (TypeError, AttributeError):
            palette.from_list(self._colors)

    def color(self, value: str | tuple[int, ...]) -> int:
        if isinstance(value, str):
            rgb = int(value.lstrip('#'), 16)
        else:
            rgb = value[0] << 16 | value[1] << 8 | value[2]
        if rgb in self.palette:
            return self.palette[rgb]
        if len(self._colors) >= 256:
            # Allow external Aseprite art with many colors without exhausting
            # Pyxel's palette; retain the nearest already allocated color.
            r, g, b = rgb >> 16, (rgb >> 8) & 255, rgb & 255
            nearest = min(self.palette, key=lambda c: (r-(c >> 16))**2 + (g-((c >> 8)&255))**2 + (b-(c&255))**2)
            return self.palette[nearest]
        index = len(self._colors)
        self._colors.append(rgb)
        self.palette[rgb] = index
        self._sync_palette()
        return index

    def clear(self, color):
        self.engine.cls(self.color(color))

    def rect(self, x, y, width, height, color):
        if width > 0 and height > 0:
            self.engine.rect(round(x), round(y), round(width), round(height), self.color(color))

    def line(self, x1, y1, x2, y2, color):
        self.engine.line(round(x1), round(y1), round(x2), round(y2), self.color(color))

    @lru_cache(maxsize=128)
    def _large_text(self, text, color, scale):
        source = self.engine.Image(max(1, len(text)*4), 6)
        source.cls(0)
        source.text(0, 0, text, color)
        image = self.engine.Image(source.width*scale, source.height*scale)
        image.cls(0)
        for y in range(source.height):
            for x in range(source.width):
                ink = source.pget(x, y)
                if ink:
                    image.rect(x*scale, y*scale, scale, scale, ink)
        return image

    def text(self, x, y, text, color, scale=1):
        # Pyxel's built-in tiny font is ASCII; keep layout stable for OS names.
        text = str(text).replace('♥', '<3').encode('ascii', 'replace').decode('ascii')
        ink = self.color(color)
        scale = max(1, int(scale))
        if scale == 1:
            self.engine.text(round(x), round(y), text, ink)
        else:
            image = self._large_text(text, ink, scale)
            self.engine.blt(round(x), round(y), image, 0, 0, image.width, image.height, 0)

    @lru_cache(maxsize=128)
    def _frame(self, name, sx, sy, width, height, flip, scale):
        from PIL import Image
        from sprite_assets import load_sheet
        sheet, _ = load_sheet(name)
        pixels = sheet.crop((sx, sy, sx+width, sy+height))
        if flip:
            pixels = pixels.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if scale != 1:
            pixels = pixels.resize((width*scale, height*scale), Image.Resampling.NEAREST)
        image = self.engine.Image(pixels.width, pixels.height)
        image.cls(0)
        for y in range(pixels.height):
            for x in range(pixels.width):
                rgba = pixels.getpixel((x, y))
                if rgba[3] >= 128:
                    image.pset(x, y, self.color(rgba))
        return image

    def sprite(self, name, action, x, y, flip=False, scale=1, tick=0):
        from sprite_assets import frame_info
        frame = frame_info(name, action, tick)
        image = self._frame(name, frame['x'], frame['y'], frame['w'], frame['h'], bool(flip), max(1, int(scale)))
        self.engine.blt(round(x), round(y), image, 0, 0, image.width, image.height, 0)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--smoke-test', action='store_true', help='Run a finite real Pyxel render test, then exit.')
    result.add_argument('--frames', type=int, default=12, help='Frames to draw in smoke-test mode (default: 12).')
    result.add_argument('--scene', choices=('title', 'fight', 'match_over'), default='fight', help='Scene to display in smoke-test mode.')
    result.add_argument('--screenshot', type=Path, help='Save the final smoke-test frame as PNG.')
    return result


def main(argv=None) -> None:
    args = parser().parse_args(argv)
    if args.frames < 1:
        raise SystemExit('--frames must be positive.')
    if args.screenshot and not args.smoke_test:
        raise SystemExit('--screenshot requires --smoke-test.')
    from variant_setup import ensure_runtime
    ensure_runtime({'pyxel': 'pyxel>=2.3', 'PIL': 'Pillow>=10'})
    import pyxel
    from variant_game import Controller
    from variant_scene import draw_scene, WIDTH, HEIGHT

    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise SystemExit('Pyxel needs a graphical desktop display. Use a desktop session (or xvfb-run for smoke tests), or run python3 neon_dojo_terminal.py in this terminal.')

    # Escape belongs to the game (pause, cancel address entry, back to menu).
    # Pyxel's default quit binding must therefore be disabled.
    try:
        pyxel.init(WIDTH, HEIGHT, title='NEON DOJO — Pyxel + Aseprite', fps=30,
                   quit_key=pyxel.KEY_NONE, display_scale=3)
    except Exception as error:
        raise SystemExit(f'Pyxel could not open a graphical window: {error}\nRun this edition in a desktop session with a working display. For a terminal/SSH session, run python3 neon_dojo_terminal.py.') from error
    controller = Controller()
    canvas = PyxelCanvas(pyxel)
    key_names = ('up', 'down', 'left', 'right', 'escape', 'p', 'q', 'z', 'x', 'c', 'space', 'w', 'a', 's', 'd', 'i')
    keys = {name: getattr(pyxel, 'KEY_'+name.upper()) for name in key_names}
    keys['enter'] = pyxel.KEY_RETURN
    last = time.monotonic()
    drawn = 0
    if args.smoke_test:
        controller.game.start_match(100)
        controller.game.state = args.scene
        controller.game.banner = ''
        if args.scene == 'match_over':
            controller.game.round_winner = 1
            controller.game.player.wins = 2
            controller.game.banner = 'TANGLED ♥ '+controller.game.player.name

    def update():
        nonlocal last
        now = time.monotonic()
        dt, last = min(0.05, now-last), now
        if args.smoke_test and drawn >= args.frames:
            print(f'Pyxel smoke test passed: {drawn} frames ({args.scene}).', flush=True)
            controller.close()
            pyxel.quit()
            return
        if controller.text_prompt is not None:
            if pyxel.input_text:
                controller.text(pyxel.input_text)
            if pyxel.btnp(pyxel.KEY_BACKSPACE, 12, 2):
                controller.backspace()
            for name in ('enter', 'escape'):
                if pyxel.btnp(keys[name]):
                    controller.press(name)
            held = set()
        else:
            for name, key in keys.items():
                if pyxel.btnp(key):
                    controller.press(name)
            held = {name for name in ('left', 'right', 'a', 'd', 'down', 's', 'space') if pyxel.btn(keys[name])}
        controller.update(dt, held)
        if not controller.running:
            controller.close()
            pyxel.quit()

    def draw():
        nonlocal drawn
        draw_scene(controller, canvas, None)
        drawn += 1
        if args.smoke_test and drawn == args.frames and args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pyxel.screen.save(str(args.screenshot), 1)
            print(f'Pyxel screenshot: {args.screenshot}', flush=True)

    try:
        pyxel.run(update, draw)
    finally:
        controller.close()
    if args.smoke_test:
        print(f'Pyxel smoke test passed: {drawn} frames ({args.scene}).', flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
