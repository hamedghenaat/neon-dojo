"""Optional backend checks; core tests do not install graphical dependencies."""
import importlib.util
import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('pygame') and importlib.util.find_spec('PIL'), 'pygame-ce/Pillow not installed in this interpreter')
class PygameCanvasTests(unittest.TestCase):
    def test_png_frame_transparency_and_horizontal_mirror(self):
        with patch.dict(os.environ, {'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy', 'PYGAME_HIDE_SUPPORT_PROMPT': '1'}):
            import pygame
            from neon_dojo_pygame import Canvas
            from sprite_assets import frame_image
            pygame.display.init()
            try:
                pygame.display.set_mode((1, 1))
                surface = pygame.Surface((64, 64), pygame.SRCALPHA)
                canvas = Canvas(pygame, surface)
                for name, action in (('knight_cyan', 'punch'), ('platformer', 'cloud_left')):
                    source = frame_image(name, action, 12)
                    for flip in (False, True):
                        surface.fill((0, 0, 0, 0))
                        canvas.sprite(name, action, 3, 5, flip=flip, tick=12)
                        for y in range(source.height):
                            for x in range(source.width):
                                expected = source.getpixel((source.width-1-x if flip else x, y))
                                actual = tuple(surface.get_at((3+x, 5+y)))
                                self.assertEqual(actual[3], expected[3])
                                if expected[3]:
                                    self.assertEqual(actual, expected)
                        self.assertEqual(surface.get_at((0, 0)).a, 0)
                cached = len(canvas.frames)
                canvas.sprite('knight_cyan', 'punch', 3, 5, tick=12)
                self.assertEqual(len(canvas.frames), cached)
            finally:
                pygame.display.quit()


if __name__ == '__main__':
    unittest.main()
