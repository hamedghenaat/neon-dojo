import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

try:
    from PIL import Image
except ImportError:
    Image = None

from build_sprite_assets import ACTIONS, build
from sprite_assets import ASSET_DIR, PLATFORMER_TILES, SHEET_NAMES, frame_image, frame_info, load_sheet


@unittest.skipUnless(Image is not None, 'Pillow is optional for the original stdlib game')
class SpriteAssetTests(unittest.TestCase):
    def test_environment_tiles_are_valid_nonempty_crops(self):
        sheet, _ = load_sheet('platformer')
        self.assertEqual(sheet.mode, 'RGBA')
        for name in PLATFORMER_TILES:
            with self.subTest(tile=name):
                frame = frame_info('platformer', name)
                self.assertGreaterEqual(frame['x'], 0)
                self.assertGreaterEqual(frame['y'], 0)
                self.assertLessEqual(frame['x'] + frame['w'], sheet.width)
                self.assertLessEqual(frame['y'] + frame['h'], sheet.height)
                tile = frame_image('platformer', name)
                self.assertEqual(tile.size, (18, 18))
                self.assertIsNotNone(tile.getbbox())
        self.assertEqual(frame_image('platformer', 'cloud_left').getchannel('A').getextrema(), (0, 255))

    def test_all_actions_have_exported_frames_and_transparent_pixels(self):
        for name in SHEET_NAMES:
            sheet, data = load_sheet(name)
            self.assertEqual(sheet.mode, 'RGBA')
            tags = {tag['name'] for tag in data['meta']['frameTags']}
            self.assertGreaterEqual(tags, {'idle'} if name == 'princess' else set(ACTIONS) | {'balcony'})
            for tag in tags:
                info = frame_info(name, tag, 12)
                self.assertLessEqual(info['x'] + info['w'], sheet.width)
                self.assertLessEqual(info['y'] + info['h'], sheet.height)
                image = frame_image(name, tag)
                self.assertIn(0, image.getchannel('A').getdata())
                self.assertIn(255, image.getchannel('A').getdata())

    def test_timing_mirroring_and_unknown_action_fallback(self):
        self.assertEqual(frame_info('princess', 'idle', 104)['filename'], 'idle_0')
        self.assertEqual(frame_info('princess', 'idle', 105)['filename'], 'idle_1')
        image = frame_image('knight_cyan', 'punch')
        self.assertEqual(frame_image('knight_cyan', 'punch', mirrored=True).tobytes(),
                         image.transpose(getattr(Image, 'Transpose', Image).FLIP_LEFT_RIGHT).tobytes())
        self.assertEqual(frame_info('knight_cyan', 'unknown'), frame_info('knight_cyan', 'idle'))
        with self.assertRaises(ValueError):
            load_sheet('../other')

    def test_aseprite_compressed_cels_match_png_exports_and_duration(self):
        for name in SHEET_NAMES:
            raw = (ASSET_DIR / f'{name}.aseprite').read_bytes()
            size, magic, count, width, height, depth = struct.unpack_from('<IHHHHH', raw)
            self.assertEqual(size, len(raw))
            self.assertEqual(magic, 0xA5E0)
            self.assertEqual(depth, 32)
            sheet, data = load_sheet(name)
            self.assertEqual(count, len(data['frames']))
            offset = 128
            tag_names = []
            for index in range(count):
                frame_size, frame_magic, chunks, duration = struct.unpack_from('<IHHH', raw, offset)
                self.assertEqual(frame_magic, 0xF1FA)
                record = data['frames'][index]
                self.assertEqual(duration, record['duration'])
                pos = offset + 16
                cel_found = False
                for _ in range(chunks):
                    chunk_size, kind = struct.unpack_from('<IH', raw, pos)
                    payload = raw[pos + 6:pos + chunk_size]
                    if kind == 0x2004:
                        flags, = struct.unpack_from('<H', payload)
                        self.assertEqual(flags & 3, 3)  # visible and editable
                    elif kind == 0x2005:
                        layer, x, y, opacity, cel_type = struct.unpack_from('<HhhBH', payload)
                        self.assertEqual((layer, x, y, opacity, cel_type), (0, 0, 0, 255, 2))
                        cw, ch = struct.unpack_from('<HH', payload, 16)
                        rect = record['frame']
                        self.assertEqual((cw, ch), (rect['w'], rect['h']))
                        png = sheet.crop((rect['x'], rect['y'], rect['x'] + cw, rect['y'] + ch))
                        self.assertEqual(zlib.decompress(payload[20:]), png.tobytes())
                        cel_found = True
                    elif kind == 0x2018:
                        tag_count, = struct.unpack_from('<H', payload)
                        cursor = 10
                        for _ in range(tag_count):
                            first, last = struct.unpack_from('<HH', payload, cursor)
                            self.assertLessEqual(first, last)
                            length, = struct.unpack_from('<H', payload, cursor + 17)
                            tag_names.append(payload[cursor + 19:cursor + 19 + length].decode())
                            cursor += 19 + length
                    pos += chunk_size
                self.assertTrue(cel_found)
                self.assertEqual(pos, offset + frame_size)
                offset += frame_size
            self.assertEqual(offset, len(raw))
            self.assertEqual(tag_names, [tag['name'] for tag in data['meta']['frameTags']])

    def test_deterministic_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)
            for name in SHEET_NAMES:
                for suffix in ('.png', '.json', '.aseprite'):
                    self.assertEqual((output / (name + suffix)).read_bytes(), (ASSET_DIR / (name + suffix)).read_bytes())

    def test_arbitrary_png_conversion_keeps_alpha_and_aspect(self):
        from png_to_terminal import ansi_lines, image_materials, quantize
        image = Image.new('RGBA', (3, 3))
        image.putpixel((0, 0), (12, 230, 55, 255))
        image.putpixel((1, 1), (150, 13, 240, 255))
        image.putpixel((2, 2), (255, 255, 255, 127))
        rows, materials = image_materials(image)
        self.assertEqual([len(row) for row in rows], [3, 3, 3])
        self.assertEqual(rows[-1], '   ')
        self.assertEqual(len(materials), 2)
        lines = list(ansi_lines(image))
        self.assertEqual(len(lines), 2)
        self.assertIn('▀', lines[0])
        self.assertIn('▄', lines[0])
        self.assertEqual(quantize((255, 255, 255)), 231)
        self.assertEqual(quantize((255, 255, 255), False), 7)


if __name__ == '__main__':
    unittest.main()
