# Editable character assets

All three frontends share these original RGBA pixel characters. Each character
has a lossless `.png` sprite sheet, an Aseprite JSON-array export with frame
rectangles/timing/tags, and an editable `.aseprite` source document. The source
contains a visible Character layer, compressed RGBA cels, and named animation
tags. There are no downloaded third-party sprite files.

## Rebuild the original artwork

```sh
python3 -m pip install 'Pillow>=10'
python3 build_sprite_assets.py
```

This deterministic build uses the original material maps in `sprites.py` and
replaces all three exports. Keep edits to Aseprite sources in version control
before running it: rebuilding deliberately restores the code-authored art.
Aseprite is **not required to build or play**.

## Edit in Aseprite

Open one of the `.aseprite` documents in Aseprite, edit its Character layer and
animation tags, then save the source. Aseprite is a separate optional editor;
these scripts do not install or license it. Export a PNG sheet and JSON-array
metadata with tags. For example, from the repository root:

```sh
aseprite -b assets/knight_cyan.aseprite --sheet-type rows \
  --sheet assets/knight_cyan.png --data assets/knight_cyan.json \
  --format json-array --list-tags --list-layers
```

Keep the action tag names and canvas dimensions. In the bundled export only the
`balcony` pose has its transparent canvas margin trimmed (9×14); if re-exported
without trimming it occupies the full 17×18 canvas. Avoid trimming combat frames,
which need fixed centers and ground anchors. Exporting changes to PNG/JSON makes
them visible to the PNG terminal and graphical variants; the original
`neon_dojo.py` continues to use its built-in material maps.
