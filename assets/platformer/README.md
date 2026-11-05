# Pixel Platformer environment tiles

`tiles.png` is the unmodified packed 360×162 atlas from **Pixel Platformer** by
[Kenney](https://kenney.nl/assets/pixel-platformer). Each tile is 18×18 pixels.
The pack is released under [Creative Commons CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
Credit is appreciated but not required by CC0.

The bundled atlas was retrieved from the following public mirror, whose README
credits Kenney, because the official download was unavailable in the build
environment:

- Repository: <https://github.com/Edwin-Bera/Simple_2DPlatformer>
- Revision: `c3891ff37617c0938ffd61fafb3a20d1cdf3b65a`
- Original path: `assets/art/tiles_packed.png`
- Pinned source: <https://raw.githubusercontent.com/Edwin-Bera/Simple_2DPlatformer/c3891ff37617c0938ffd61fafb3a20d1cdf3b65a/assets/art/tiles_packed.png>
- SHA-256: `0d58b43a0e6a6818a76c6dbba176299cb10538aab2ee530bce9e856702d956fa`

`sprite_assets.py` defines named crops from this atlas. Both graphical engines
render those crops at integer scales without smoothing. The castle is drawn by
`variant_scene.py`; knights and princess use this project's original Aseprite
assets. `build_sprite_assets.py` rebuilds only those original character assets
and does not replace this third-party atlas.
