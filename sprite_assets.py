"""Load bundled PNG/Aseprite exports independently of the working directory."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / 'assets'
SHEET_NAMES = ('knight_cyan', 'knight_magenta', 'princess')

# Kenney Pixel Platformer environment tiles, kept separate from character art.
PLATFORMER_TILES = {
    'grass_left': (0, 0), 'grass': (1, 0), 'grass_right': (3, 0),
    'earth': (1, 1), 'crate': (6, 1), 'heart': (4, 2),
    'flower': (5, 6), 'sprout': (4, 6), 'mushroom': (8, 6),
    'sign': (4, 4), 'stone': (8, 3), 'flag': (12, 5),
    'cloud_left': (13, 7), 'cloud': (14, 7), 'cloud_right': (15, 7),
    'leaves_tl': (17, 0), 'leaves_top': (18, 0), 'leaves_tr': (19, 0),
    'leaves_left': (17, 1), 'leaves': (18, 1), 'leaves_right': (19, 1),
    'leaves_bl': (17, 2), 'leaves_bottom': (18, 2), 'leaves_br': (19, 2),
    'trunk': (16, 5), 'roots': (16, 6),
}


@lru_cache(maxsize=4)
def load_sheet(name: str):
    """Return a cached RGBA Pillow image and standard Aseprite JSON metadata."""
    if name == 'platformer':
        from PIL import Image
        with Image.open(ASSET_DIR / 'platformer' / 'tiles.png') as source:
            return source.convert('RGBA'), {}
    if name not in SHEET_NAMES:
        raise ValueError(f'Unknown sprite sheet: {name}')
    from PIL import Image
    metadata = json.loads((ASSET_DIR / f'{name}.json').read_text(encoding='utf-8'))
    with Image.open(ASSET_DIR / f'{name}.png') as source:
        image = source.convert('RGBA')
    return image, metadata


def frame_info(name: str, action: str, tick: int = 0) -> dict:
    """Pick a tagged animation frame using its milliseconds and a 30-Hz tick."""
    if name == 'platformer':
        col, row = PLATFORMER_TILES[action]
        return dict(x=col*18, y=row*18, w=18, h=18, duration=1000, filename=action)
    _, data = load_sheet(name)
    tags = {tag['name']: tag for tag in data['meta']['frameTags']}
    tag = tags.get(action, tags['idle'])
    frames = data['frames'][tag['from']:tag['to'] + 1]
    durations = [max(1, int(frame['duration'])) for frame in frames]
    elapsed = max(0, int(tick)) * 1000 // 30 % sum(durations)
    index = 0
    while elapsed >= durations[index]:
        elapsed -= durations[index]
        index += 1
    frame = frames[index]
    return {**frame['frame'], 'duration': frame['duration'], 'filename': frame['filename']}


def frame_image(name: str, action: str, tick: int = 0, mirrored: bool = False):
    """Crop a fresh frame; caller may tint it without mutating the cached sheet."""
    image, _ = load_sheet(name)
    frame = frame_info(name, action, tick)
    result = image.crop((frame['x'], frame['y'], frame['x'] + frame['w'], frame['y'] + frame['h']))
    if mirrored:
        from PIL import Image
        result = result.transpose(getattr(Image, 'Transpose', Image).FLIP_LEFT_RIGHT)
    return result
