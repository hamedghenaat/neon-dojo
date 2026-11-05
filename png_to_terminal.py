#!/usr/bin/env python3
"""Convert arbitrary RGBA PNG artwork to aspect-correct terminal half blocks.

Run `python3 png_to_terminal.py picture.png --width 40` for an ANSI preview.
The game uses PNGRenderer for curses output with a bounded color-pair cache.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path

from sprites import PixelRenderer

BASIC_RGB = ((0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0),
             (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170))
LEVELS = (0, 95, 135, 175, 215, 255)
XTERM_RGB = tuple((LEVELS[r], LEVELS[g], LEVELS[b]) for r in range(6) for g in range(6) for b in range(6)) + tuple((8 + 10 * n,) * 3 for n in range(24))


@lru_cache(maxsize=4096)
def quantize(rgb: tuple[int, int, int], extended: bool = True) -> int:
    palette = XTERM_RGB if extended else BASIC_RGB
    index = min(range(len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, palette[i])))
    return index + 16 if extended else index


def image_materials(image):
    """Map arbitrary RGBA colors to symbolic rows; alpha<128 is transparent."""
    rgba = image.convert('RGBA')
    inks, materials, rows = {}, {}, []
    for y in range(rgba.height):
        row = []
        for x in range(rgba.width):
            color = rgba.getpixel((x, y))
            if color[3] < 128:
                row.append(' ')
                continue
            rgb = color[:3]
            if rgb not in inks:
                ink = chr(0x100 + len(inks))
                inks[rgb] = ink
                materials[ink] = rgb
            row.append(inks[rgb])
        rows.append(''.join(row))
    return rows, materials


class PNGRenderer(PixelRenderer):
    """Same transparency/clipping contract as PixelRenderer, sourced from PNG."""
    def _color(self, material):
        if material is None or isinstance(material, str):
            return super()._color(material)
        return quantize(material, self.extended)

    def draw_image(self, image, x: int, y: int, mirrored: bool = False, flash: bool = False):
        if mirrored:
            from PIL import Image
            image = image.transpose(getattr(Image, 'Transpose', Image).FLIP_LEFT_RIGHT)
        rows, materials = image_materials(image)
        materials = {ink: ('white' if rgb == (255, 255, 255) else rgb)
                     for ink, rgb in materials.items()}
        super().draw(rows, x, y, materials, flash)


def ansi_lines(image):
    """Return ANSI 256-color half-block rows, including per-line reset."""
    rgba = image.convert('RGBA')
    for y in range(0, rgba.height, 2):
        line = []
        for x in range(rgba.width):
            top = rgba.getpixel((x, y))
            bottom = rgba.getpixel((x, y + 1)) if y + 1 < rgba.height else (0, 0, 0, 0)
            if top[3] < 128 and bottom[3] < 128:
                line.append('\x1b[0m ')
                continue
            char = '▀'
            if top[3] < 128:
                top, bottom, char = bottom, top, '▄'
            fg = f'38;5;{quantize(top[:3])}'
            bg = f'48;5;{quantize(bottom[:3])}' if bottom[3] >= 128 else '49'
            line.append(f'\x1b[{fg};{bg}m{char}')
        yield ''.join(line) + '\x1b[0m'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--width', type=int, help='Resize to this many terminal columns, preserving pixel aspect')
    args = parser.parse_args()
    if args.width is not None and args.width < 1:
        parser.error('--width must be positive')
    from variant_setup import ensure_runtime
    ensure_runtime({'PIL': 'Pillow>=10'})
    from PIL import Image
    try:
        with Image.open(args.image) as source:
            image = source.convert('RGBA')
        if args.width:
            image = image.resize((args.width, max(1, round(image.height * args.width / image.width))), getattr(Image, 'Resampling', Image).NEAREST)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Cannot open PNG: {error}\n')
    print('\n'.join(ansi_lines(image)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
