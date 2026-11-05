import builtins
import curses
import subprocess
import sys
import unittest
from unittest.mock import patch

from sprites import (
    COLORS, KNIGHT_HEIGHT, KNIGHT_WIDTH, PRINCESS_MATERIALS, PixelRenderer,
    balcony_knight_pixels, knight_materials, knight_pixels, princess_pixels,
)

ACTIONS = ('idle', 'walk', 'punch', 'kick', 'special', 'block', 'crouch',
           'hurt', 'jump', 'defeated', 'finish', 'victory', 'fallen', 'climb')


class PixelArtTests(unittest.TestCase):
    def test_all_poses_are_renderable_and_mirror_without_changing_floor(self):
        for action in ACTIONS:
            for tick in (0, 6, 12):
                with self.subTest(action=action, tick=tick):
                    right = knight_pixels(action, tick)
                    self.assertEqual(len(right), KNIGHT_HEIGHT)
                    self.assertEqual({len(row) for row in right}, {KNIGHT_WIDTH})
                    self.assertEqual(knight_pixels(action, tick, -1), [row[::-1] for row in right])
                    self.assertLessEqual(set(''.join(right)), set(knight_materials(2)) | {' '})
        self.assertNotEqual(knight_pixels('idle', 0), knight_pixels('punch', 0))
        self.assertNotEqual(knight_pixels('walk', 0), knight_pixels('walk', 6))
        self.assertLess(sum(bool(row.strip()) for row in knight_pixels('fallen', 0)), 6)

    def test_princess_blinks_without_changing_hair_face_or_dress_size(self):
        blinking, open_eyes = princess_pixels(0), princess_pixels(12)
        self.assertEqual(len(open_eyes), 14)
        self.assertEqual({len(row) for row in open_eyes}, {9})
        self.assertEqual(PRINCESS_MATERIALS['F'], 'white')
        self.assertEqual(COLORS['white'][0], 231)
        self.assertNotIn('E', ''.join(blinking))
        self.assertEqual(''.join(open_eyes).count('E'), 2)
        self.assertEqual(blinking[:4] + blinking[5:], open_eyes[:4] + open_eyes[5:])

    def test_pair_halves_transparency_and_reuse(self):
        calls = []
        with patch.object(curses, 'COLORS', 256, create=True), patch.object(curses, 'COLOR_PAIRS', 256, create=True), patch.object(curses, 'init_pair') as init, patch.object(curses, 'color_pair', side_effect=lambda pair: pair << 8):
            renderer = PixelRenderer(lambda *args: calls.append(args), True)
            renderer.draw(['FT ', ' FF'], 4, 7, knight_materials(2))
            self.assertEqual([call[2] for call in calls], ['▀', '▀', '▄'])
            self.assertEqual([(call[0], call[1]) for call in calls], [(7, 4), (7, 5), (7, 6)])
            self.assertIn((231, -1), renderer.pairs)
            self.assertIn((45, 231), renderer.pairs)
            count = init.call_count
            renderer.draw(['FT ', ' FF'], 4, 7, knight_materials(2))
            self.assertEqual(init.call_count, count)
            calls.clear()
            renderer.draw(['  ', '  '], 0, 0, knight_materials(2))
            self.assertEqual(calls, [])

    def test_limited_colors_and_monochrome_keep_same_pixel_footprint(self):
        for colors, limit in ((True, 64), (True, 10), (False, 0)):
            calls = []
            with self.subTest(colors=colors, limit=limit), patch.object(curses, 'COLORS', 8, create=True), patch.object(curses, 'COLOR_PAIRS', limit, create=True), patch.object(curses, 'init_pair') as init, patch.object(curses, 'color_pair', return_value=0):
                renderer = PixelRenderer(lambda *args: calls.append(args), colors)
                renderer.draw(knight_pixels('idle', 0), 0, 0, knight_materials(2))
                self.assertTrue(calls)
                self.assertLessEqual(max(row for row, _, _, _ in calls), 8)
                self.assertLessEqual(max(col for _, col, _, _ in calls), 16)
                self.assertTrue(all(9 <= call.args[0] < limit for call in init.call_args_list))
                self.assertTrue(all(-1 <= value <= 7 for call in init.call_args_list for value in call.args[1:]))

    def test_full_animation_set_fits_portable_pair_budget(self):
        with patch.object(curses, 'COLORS', 8, create=True), patch.object(curses, 'COLOR_PAIRS', 64, create=True), patch.object(curses, 'init_pair'), patch.object(curses, 'color_pair', return_value=0):
            renderer = PixelRenderer(lambda *args: None, True)
            for team in (2, 3):
                for action in ACTIONS:
                    for tick in range(16):
                        renderer.draw(knight_pixels(action, tick), 0, 0, knight_materials(team))
                renderer.draw(balcony_knight_pixels(), 0, 0, knight_materials(team))
            for tick in (0, 12):
                renderer.draw(princess_pixels(tick), 0, 0, PRINCESS_MATERIALS)
            renderer.draw(knight_pixels('idle', 0), 0, 0, knight_materials(2), flash=True)
            self.assertLess(renderer.next_pair, 64)

    def test_import_still_works_before_curses_dependency_is_installed(self):
        script = '''
import builtins
original = builtins.__import__
def without_curses(name, *args, **kwargs):
    if name == "curses":
        raise ImportError("simulated missing curses")
    return original(name, *args, **kwargs)
builtins.__import__ = without_curses
import neon_dojo
assert neon_dojo.curses is None
assert any(item.key == "curses" and not item.ready for item in neon_dojo.dependency_checks())
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
