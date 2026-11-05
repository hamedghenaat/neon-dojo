#!/usr/bin/env python3
"""Rebuild original PNG sheets, JSON exports and editable Aseprite sources.

Requires Pillow only. Aseprite itself is optional: open assets/*.aseprite to edit
layers and tagged animation frames, then export PNG+JSON using Aseprite's CLI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import zlib

from sprites import COLORS, PRINCESS_MATERIALS, balcony_knight_pixels, knight_materials, knight_pixels, princess_pixels

ACTIONS = ('idle', 'walk', 'punch', 'kick', 'special', 'block', 'crouch',
           'hurt', 'jump', 'defeated', 'finish', 'victory', 'fallen', 'climb')


def xterm_rgb(index):
    if index >= 232:
        value = 8 + 10 * (index - 232)
        return value, value, value
    levels = (0, 95, 135, 175, 215, 255)
    index -= 16
    return levels[index // 36], levels[index // 6 % 6], levels[index % 6]


def image_from_map(rows, materials):
    from PIL import Image
    image = Image.new('RGBA', (len(rows[0]), len(rows)))
    image.putdata([(*xterm_rgb(COLORS[materials[pixel]][0]), 255) if pixel != ' ' else (0, 0, 0, 0)
                   for row in rows for pixel in row])
    return image


def string(value):
    encoded = value.encode('utf-8')
    return struct.pack('<H', len(encoded)) + encoded


def chunk(kind, data):
    return struct.pack('<IH', len(data) + 6, kind) + data


def aseprite_bytes(frames, tags, width, height):
    """Write Aseprite's documented RGBA compressed-cel file format."""
    layer = chunk(0x2004, struct.pack('<HHHHHHB', 3, 0, 0, width, height, 0, 255)
                  + bytes(3) + string('Character'))
    tag_data = struct.pack('<H', len(tags)) + bytes(8)
    for tag in tags:
        tag_data += struct.pack('<HHBH', tag['from'], tag['to'], 0, 0)
        tag_data += bytes(6) + bytes((255, 200, 90, 0)) + string(tag['name'])
    tag_chunk = chunk(0x2018, tag_data)
    encoded_frames = []
    for index, (image, duration, _) in enumerate(frames):
        # Cel layer, x/y, opacity, compressed type, z-index and reserved bytes.
        cel_data = struct.pack('<HhhBHh', 0, 0, 0, 255, 2, 0) + bytes(5)
        cel_data += struct.pack('<HH', *image.size) + zlib.compress(image.tobytes(), 9)
        chunks = ([layer, tag_chunk] if index == 0 else []) + [chunk(0x2005, cel_data)]
        body = b''.join(chunks)
        encoded_frames.append(struct.pack('<IHHHHI', 16 + len(body), 0xF1FA, len(chunks), duration, 0, 0) + body)
    body = b''.join(encoded_frames)
    header = struct.pack('<IHHHHHI', 128 + len(body), 0xA5E0, len(frames), width, height, 32, 1)
    header += struct.pack('<HII', frames[0][1], 0, 0) + bytes((0,)) + bytes(3)
    header += struct.pack('<HBBhhHH', 0, 1, 1, 0, 0, 0, 0)
    return header.ljust(128, b'\0') + body


def build(output: Path):
    from PIL import Image
    output.mkdir(parents=True, exist_ok=True)
    for name, team in (('knight_cyan', 2), ('knight_magenta', 3), ('princess', None)):
        frames, tags = [], []
        if team is None:
            variants = [('idle', [(12, 3500), (0, 133)])]
        else:
            variants = [(action, [(0, 167), (9 if action == 'walk' else (3 if action == 'finish' else 8), 167)]) for action in ACTIONS]
            variants.append(('balcony', [(0, 333)]))
        for action, samples in variants:
            first = len(frames)
            for index, (tick, duration) in enumerate(samples):
                rows = princess_pixels(tick) if team is None else (balcony_knight_pixels() if action == 'balcony' else knight_pixels(action, tick))
                materials = PRINCESS_MATERIALS if team is None else knight_materials(team)
                frames.append((image_from_map(rows, materials), duration, f'{action}_{index}'))
            tags.append({'name': action, 'from': first, 'to': len(frames) - 1, 'direction': 'forward'})
        canvas_w = max(image.width for image, _, _ in frames)
        canvas_h = max(image.height for image, _, _ in frames)
        columns = min(8, len(frames))
        sheet = Image.new('RGBA', (canvas_w * columns, canvas_h * ((len(frames) + columns - 1) // columns)))
        records = []
        for index, (image, duration, label) in enumerate(frames):
            x, y = index % columns * canvas_w, index // columns * canvas_h
            sheet.paste(image, (x, y))
            records.append({'filename': label, 'frame': {'x': x, 'y': y, 'w': image.width, 'h': image.height},
                            'rotated': False, 'trimmed': image.size != (canvas_w, canvas_h),
                            'spriteSourceSize': {'x': 0, 'y': 0, 'w': image.width, 'h': image.height},
                            'sourceSize': {'w': canvas_w, 'h': canvas_h}, 'duration': duration})
        metadata = {'frames': records, 'meta': {'app': 'Neon Dojo original-art exporter', 'version': '1',
                    'image': f'{name}.png', 'format': 'RGBA8888', 'size': {'w': sheet.width, 'h': sheet.height},
                    'scale': '1', 'frameTags': tags, 'layers': [{'name': 'Character', 'opacity': 255, 'blendMode': 'normal'}]}}
        sheet.save(output / f'{name}.png', optimize=False)
        (output / f'{name}.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        (output / f'{name}.aseprite').write_bytes(aseprite_bytes(frames, tags, canvas_w, canvas_h))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'assets')
    args = parser.parse_args()
    try:
        build(args.output)
    except ImportError:
        parser.exit(1, 'Pillow is required: python3 -m pip install "Pillow>=10"\n')
    print(f'Exported PNG, JSON and editable Aseprite files to {args.output}')


if __name__ == '__main__':
    main()
