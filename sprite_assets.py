"""Load bundled PNG/Aseprite exports independently of the working directory."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / 'assets'
SHEET_NAMES = ('knight_cyan', 'knight_magenta', 'princess')


@lru_cache(maxsize=3)
def load_sheet(name: str):
    """Return a cached RGBA Pillow image and standard Aseprite JSON metadata."""
    if name not in SHEET_NAMES:
        raise ValueError(f'Unknown sprite sheet: {name}')
    from PIL import Image
    metadata = json.loads((ASSET_DIR / f'{name}.json').read_text(encoding='utf-8'))
    with Image.open(ASSET_DIR / f'{name}.png') as source:
        image = source.convert('RGBA')
    return image, metadata


def frame_info(name: str, action: str, tick: int = 0) -> dict:
    """Pick a tagged animation frame using its milliseconds and a 30-Hz tick."""
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
