# Character art references

The character pixels in `sprites.py` are original code-authored art distributed
under this repository's MIT license. No sprite sheets or pixels from the packs
below are bundled, traced, or imported. These public references informed the
small silhouettes, compact palettes, and pose separation:

- [Kenney — Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon): 16×16 tiles,
  130 files, CC0. A useful reference for legible small fantasy forms.
- [Kenney — Pixel Platformer](https://kenney.nl/assets/pixel-platformer): 18×18
  tiles, 200 files, CC0. A useful reference for compact color clusters.
- [OpenGameArt — LPC Character Bases](https://opengameart.org/content/lpc-character-bases):
  character bases and walk-cycle reference, offered under CC-BY-SA 3.0/GPL 3.0.
  Consult that page's attribution and license requirements before reusing its
  assets; this project does not incorporate them.

The game renders each pair of pixel rows with Unicode half blocks (`▀`, `▄`).
A 17×18 knight occupies the same 17×9 terminal cells as before, while a 9×14
princess occupies 9×7 cells. This counteracts the tall shape of terminal cells.
256-color terminals show the full palette; eight-color terminals use portable
colors, and monochrome terminals retain silhouettes through block shading.
No image library, asset download, or external font is needed to play.
