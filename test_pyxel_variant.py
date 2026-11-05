"""Backend invariants that do not require opening a graphical window."""
import unittest
from types import SimpleNamespace

from neon_dojo_pyxel import PyxelCanvas, parser


class Palette:
    def __init__(self):
        self.colors = []

    def from_list(self, colors):
        self.colors = list(colors)


class PyxelVariantTests(unittest.TestCase):
    def test_transparency_never_consumes_opaque_black_or_magenta(self):
        engine = SimpleNamespace(colors=Palette())
        canvas = PyxelCanvas(engine)
        black = canvas.color('#000000')
        magenta = canvas.color('#ff00ff')
        self.assertNotEqual(black, 0)
        self.assertNotEqual(magenta, 0)
        self.assertNotEqual(black, magenta)
        self.assertEqual(canvas.color((0, 0, 0, 255)), black)
        self.assertEqual(engine.colors.colors[black], 0)
        self.assertEqual(engine.colors.colors[magenta], 0xff00ff)

    def test_palette_exhaustion_quantizes_without_reassigning_cached_indices(self):
        engine = SimpleNamespace(colors=Palette())
        canvas = PyxelCanvas(engine)
        for red in range(255):
            canvas.color((red, 0, 0))
        original = list(engine.colors.colors)
        result = canvas.color((254, 1, 1))
        self.assertEqual(engine.colors.colors, original)
        self.assertEqual(result, canvas.palette[0xfe0000])
        self.assertLessEqual(len(engine.colors.colors), 256)

    def test_list_palette_and_cli_scene_selection(self):
        engine = SimpleNamespace(colors=[])
        canvas = PyxelCanvas(engine)
        self.assertEqual(canvas.color('#123456'), 1)
        self.assertEqual(engine.colors, [0xff00ff, 0x123456])
        options = parser().parse_args(['--smoke-test', '--scene', 'match_over', '--frames', '2'])
        self.assertTrue(options.smoke_test)
        self.assertEqual(options.scene, 'match_over')
        self.assertEqual(options.frames, 2)


if __name__ == '__main__':
    unittest.main()
