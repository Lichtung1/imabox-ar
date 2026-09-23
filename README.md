# IMABOX AR

Five animated IMABOX characters you can place in your room with your phone.

Live at https://imabox-ar.github.io/ (GitHub Pages, deployed from `main`).

## How it works

- **iPhone / iPad:** VIEW IN AR opens the character's `.usdz` in Apple's AR viewer.
- **Android (Chrome):** VIEW IN AR starts AR in the browser. Tap the floor and the character walks in and plays its animation.
- **Everything else:** a 3D model you can drag around, plus a QR code to open the page on a phone.

## Characters

| Page | Model files |
|---|---|
| `characters/01/` | `char4.glb`, `char4.usdz` |
| `characters/02/` | `char1.glb`, `char1.usdz` |
| `characters/03/` | `char3.glb`, `char3.usdz` |
| `characters/04/` | `char5.glb`, `char5.usdz` |
| `characters/05/` | `char2.glb`, `char2.usdz` |

The page numbers follow the posters in `assets/`. Settings for each character (timing, walk-in, file hashes) are in `characters.js`.

## Updating a model

1. Export a new `.glb` and `.usdz` from Blender and replace the matching files.
2. Run the iPhone fixes on the new `.usdz` (see `tools/`):
   - `rebuild-usdz.py`: stands the model up, sizes it to 1 m and puts it on the floor
   - `bevel-usdz.py`: applies the rounded edges Blender's USD export leaves out
   - `aura-usdz.py`: Imabox 04 only, rebuilds the power-up aura
3. Run `npm test`. It reports any file whose hash no longer matches `characters.js`; update the hash there.
4. Bump the version (`v17-…`) in `characters.js` and the HTML pages so phones fetch the new files.

The Python tools need `pip install bpy usd-core`.

## Checking locally

```
npm install
npm test
python3 -m http.server
```

Then open http://localhost:8000. AR itself needs HTTPS and a phone, so test that on the live site.

## Credits

Characters and artwork by Bistyek. Three.js and the QR code library are included in `vendor/` under their own licences.
