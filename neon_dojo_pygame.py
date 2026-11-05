#!/usr/bin/env python3
"""NEON DOJO with pygame-ce and bundled Aseprite-exported PNG sprites."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

WIDTH, HEIGHT = 400, 240


PIXEL_FONT = {
    'A': ('010','101','111','101','101'), 'B': ('110','101','110','101','110'),
    'C': ('011','100','100','100','011'), 'D': ('110','101','101','101','110'),
    'E': ('111','100','110','100','111'), 'F': ('111','100','110','100','100'),
    'G': ('011','100','101','101','011'), 'H': ('101','101','111','101','101'),
    'I': ('111','010','010','010','111'), 'J': ('001','001','001','101','010'),
    'K': ('101','101','110','101','101'), 'L': ('100','100','100','100','111'),
    'M': ('101','111','111','101','101'), 'N': ('101','111','111','111','101'),
    'O': ('010','101','101','101','010'), 'P': ('110','101','110','100','100'),
    'Q': ('010','101','101','111','011'), 'R': ('110','101','110','101','101'),
    'S': ('011','100','010','001','110'), 'T': ('111','010','010','010','010'),
    'U': ('101','101','101','101','111'), 'V': ('101','101','101','101','010'),
    'W': ('101','101','111','111','101'), 'X': ('101','101','010','101','101'),
    'Y': ('101','101','010','010','010'), 'Z': ('111','001','010','100','111'),
    '0': ('111','101','101','101','111'), '1': ('010','110','010','010','111'),
    '2': ('110','001','010','100','111'), '3': ('110','001','010','001','110'),
    '4': ('101','101','111','001','001'), '5': ('111','100','110','001','110'),
    '6': ('011','100','110','101','010'), '7': ('111','001','010','010','010'),
    '8': ('010','101','010','101','010'), '9': ('010','101','011','001','110'),
    ' ': ('000',)*5, '.': ('000','000','000','000','010'),
    ':': ('000','010','000','010','000'), '/': ('001','001','010','100','100'),
    '-': ('000','000','111','000','000'), '_': ('000','000','000','000','111'),
    '>': ('100','010','001','010','100'), '<': ('001','010','100','010','001'),
    '!': ('010','010','010','000','010'), '?': ('110','001','010','000','010'),
    "'": ('010','010','000','000','000'), ',': ('000','000','000','010','100'),
    '(': ('001','010','010','010','001'), ')': ('100','010','010','010','100'),
    '+': ('000','010','111','010','000'), '=': ('000','111','000','111','000'),
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--smoke-test', action='store_true', help='render a finite test using SDL dummy video/audio')
    result.add_argument('--frames', type=int, default=90, help='number of frames in smoke-test mode (default: 90)')
    result.add_argument('--scene', choices=('title', 'fight', 'finisher', 'wedding', 'match_over'), default='fight', help='initial scene in smoke-test mode')
    result.add_argument('--screenshot', type=Path, help='save the final logical-resolution frame as PNG')
    return result


class Canvas:
    """Small rendering adapter; the game rules and composition are shared."""

    def __init__(self, pygame, surface):
        self.pg, self.surface = pygame, surface
        self.sheets = {}
        self.frames = {}

    def clear(self, color):
        self.surface.fill(color)

    def rect(self, x, y, w, h, color):
        self.pg.draw.rect(self.surface, color, (round(x), round(y), max(0, round(w)), max(0, round(h))))

    def line(self, x1, y1, x2, y2, color):
        self.pg.draw.line(self.surface, color, (round(x1), round(y1)), (round(x2), round(y2)))

    def text(self, x, y, text, color, scale=1):
        # Original 3x5 bitmap glyphs share Pyxel's four-pixel advance. Scaling
        # an arbitrary desktop font down to six pixels destroys its strokes.
        for index, character in enumerate(str(text).upper()):
            rows = PIXEL_FONT.get(character, PIXEL_FONT['?'])
            for row, bits in enumerate(rows):
                for col, bit in enumerate(bits):
                    if bit == '1':
                        self.rect(x + (index * 4 + col) * scale, y + row * scale, scale, scale, color)

    def sprite(self, name, action, x, y, flip=False, scale=1, tick=0):
        from sprite_assets import ASSET_DIR, frame_info
        if name not in self.sheets:
            self.sheets[name] = self.pg.image.load(str(ASSET_DIR / f'{name}.png')).convert_alpha()
        frame = frame_info(name, action, tick)
        key = (name, frame['x'], frame['y'], frame['w'], frame['h'], flip, scale)
        if key not in self.frames:
            result = self.sheets[name].subsurface((frame['x'], frame['y'], frame['w'], frame['h']))
            if flip:
                result = self.pg.transform.flip(result, True, False)
            if scale != 1:
                result = self.pg.transform.scale(result, (max(1, round(frame['w'] * scale)), max(1, round(frame['h'] * scale))))
            self.frames[key] = result
        self.surface.blit(self.frames[key], (round(x), round(y)))


def key_map(pygame):
    return {getattr(pygame, name): value for name, value in (
        ('K_UP', 'up'), ('K_DOWN', 'down'), ('K_LEFT', 'left'), ('K_RIGHT', 'right'),
        ('K_RETURN', 'enter'), ('K_KP_ENTER', 'enter'), ('K_ESCAPE', 'escape'),
        ('K_SPACE', 'space'), ('K_p', 'p'), ('K_q', 'q'), ('K_z', 'z'),
        ('K_x', 'x'), ('K_c', 'c'), ('K_w', 'w'), ('K_a', 'a'),
        ('K_s', 's'), ('K_d', 'd'), ('K_i', 'i'),
    )}


def seed_smoke_scene(controller, scene):
    """Deterministic entry points for renderer validation without changing play."""
    if scene == 'title':
        return
    controller.game.start_match(100)
    controller.game.state = scene
    controller.game.banner = ''
    if scene in ('finisher', 'wedding', 'match_over'):
        controller.game.round_winner = 1
        controller.game.player.wins = 2
        controller.game.enemy.health = 0
        controller.game.enemy.action = 'fallen'
        if scene == 'match_over':
            controller.game.banner = f'TANGLED ♥ {controller.game.player.name}'


def run(args, pygame):
    from variant_game import Controller
    from variant_scene import draw_scene
    controller = None
    try:
        pygame.init()
        if not pygame.IS_CE:
            raise RuntimeError('This edition requires pygame-ce, not the original pygame package.')
        window = pygame.display.set_mode((WIDTH * 3, HEIGHT * 3), pygame.RESIZABLE)
        pygame.display.set_caption('NEON DOJO — pygame-ce / Aseprite')
        surface = pygame.Surface((WIDTH, HEIGHT)).convert()
        canvas = Canvas(pygame, surface)
        controller = Controller()
        if args.smoke_test:
            seed_smoke_scene(controller, args.scene)
        keys = key_map(pygame)
        clock = pygame.time.Clock()
        count = 0
        text_active = False
        while controller.running and (not args.smoke_test or count < args.frames):
            dt = 1 / 30 if args.smoke_test else min(clock.tick(60) / 1000, .05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    controller.running = False
                elif event.type == pygame.VIDEORESIZE:
                    window = pygame.display.set_mode((max(WIDTH, event.w), max(HEIGHT, event.h)), pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        controller.backspace()
                    elif event.key in keys:
                        controller.press(keys[event.key])
                elif event.type == pygame.TEXTINPUT and controller.text_prompt is not None:
                    controller.text(event.text)
            if bool(controller.text_prompt) != text_active:
                text_active = bool(controller.text_prompt)
                if text_active:
                    pygame.key.start_text_input()
                else:
                    pygame.key.stop_text_input()
            pressed = pygame.key.get_pressed()
            held = {command for code, command in keys.items() if command in ('left', 'right', 'down', 'a', 'd', 's', 'space') and pressed[code]}
            controller.update(dt, held)
            draw_scene(controller, canvas, None)
            factor = max(1, min(window.get_width() // WIDTH, window.get_height() // HEIGHT))
            scaled = pygame.transform.scale(surface, (WIDTH * factor, HEIGHT * factor))
            window.fill('#080c18')
            window.blit(scaled, ((window.get_width() - scaled.get_width()) // 2, (window.get_height() - scaled.get_height()) // 2))
            pygame.display.flip()
            count += 1
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(surface, str(args.screenshot))
        if args.smoke_test:
            print(f'pygame-ce smoke test: rendered {count} frames; final state={controller.game.state}')
        return 0
    finally:
        if controller is not None:
            controller.close()
        pygame.quit()


def main():
    args = parser().parse_args()
    if args.frames < 1:
        parser().error('--frames must be positive')
    if args.smoke_test:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    from variant_setup import ensure_runtime
    ensure_runtime({'pygame': 'pygame-ce>=2.5', 'PIL': 'Pillow>=10'})
    import pygame
    try:
        return run(args, pygame)
    except KeyboardInterrupt:
        return 0
    except (pygame.error, RuntimeError, OSError, ValueError) as error:
        print(f'Cannot start pygame-ce edition: {error}', file=sys.stderr)
        print('Use a desktop session with a working display, or --smoke-test for a headless check.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
