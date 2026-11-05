#!/usr/bin/env python3
"""Play the full terminal game using bundled PNG/Aseprite sprite-sheet exports."""
from __future__ import annotations

import argparse
import platform


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Verify PNG loading and terminal conversion without an interactive terminal')
    args = parser.parse_args(argv)
    from variant_setup import ensure_runtime
    dependencies = {'PIL': 'Pillow>=10'}
    if platform.system() == 'Windows':
        dependencies['curses'] = 'windows-curses'
    ensure_runtime(dependencies)

    import neon_dojo as game_module
    from png_to_terminal import PNGRenderer, ansi_lines
    from sprite_assets import frame_image, load_sheet, SHEET_NAMES

    if args.smoke_test:
        for name in SHEET_NAMES:
            _, metadata = load_sheet(name)
            for tag in metadata['meta']['frameTags']:
                frame = frame_image(name, tag['name'], 12)
                assert len(list(ansi_lines(frame))) == (frame.height + 1) // 2
        print('PNG terminal smoke test passed: all sheets, actions and half-block conversion.')
        return 0

    class PNGGameRenderer(game_module.Renderer):
        def __init__(self, win):
            super().__init__(win)
            # Replace (rather than add to) the pixel cache: HUD/scenery keep 1..8.
            self.pixels = PNGRenderer(
                lambda y, x, text, attr: game_module.safe_add(self.win, y, x, text, attr),
                self.has_colors, self.pixels.background,
            )

        def draw_fighter(self, fighter, ground, tick, ox):
            name = 'knight_cyan' if fighter.color == 2 else 'knight_magenta'
            action = 'block' if fighter.blocking else fighter.action
            image = frame_image(name, action, tick)
            x = round(fighter.x) - game_module.SPRITE_WIDTH // 2 + ox
            y = ground - (image.height + 1) // 2 - round(fighter.jump_y / 2)
            self.pixels.draw_image(image, x, y, fighter.facing != 1, fighter.flash_time > 0)
            if fighter.airborne:
                game_module.safe_add(self.win, ground - 1, x + 3, '·' * 11, self.c(6, dim=True))

        def draw_tangled(self, center, top, base, tick):
            image = frame_image('princess', 'idle', tick)
            left = center - image.width // 2
            self.pixels.draw_image(image, left, top)
            for y in range(top + 3, base):
                game_module.safe_add(self.win, y, left + 8, '╲' if (y + tick // 12) % 2 else '╱', self.c(4, True))
            if base > top + 3:
                game_module.safe_add(self.win, base - 1, left + 8, '◆', self.c(4, True))

        def draw_window_knight(self, game, center, top):
            champion, _ = game.story_fighters()
            name = 'knight_cyan' if champion.color == 2 else 'knight_magenta'
            image = frame_image(name, 'balcony')
            self.pixels.draw_image(image, center - image.width // 2, top)

    original_renderer = game_module.Renderer
    try:
        game_module.Renderer = PNGGameRenderer
        game_module.main()
    finally:
        game_module.Renderer = original_renderer
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
