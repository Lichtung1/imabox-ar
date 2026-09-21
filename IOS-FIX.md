# Why iPhone was broken, and what changed · v11-20260921.1

Android and iPhone take completely different routes through this site, and only
one of them was ever forgiving.

On Android, `js/experience.js` loads the `.glb` into Three.js and fixes the
model up at runtime: it rescales the character to `height` (1 m), re-grounds it
on its evaluated first pose, and cancels the baked-in root travel so the app can
drive the approach itself. Any oddity in the export gets normalised in code.

On iPhone there is no such layer. Safari has no WebXR — still true in 2026 —
so the only route is AR Quick Look, which takes the `.usdz` exactly as written:
one unit is one metre, the file origin lands on the tapped surface, Y is up, and
the whole stage time range plays. Every flaw in the export shows up untouched.

The `.usdz` files had five of them.

## What was wrong with the models

| | before | after |
|---|---|---|
| up axis | Z (Blender's) — Apple's usdz spec requires Y | Y |
| size as Quick Look reads it | 5.67 m wide, 5.16 m deep, lying on its back | 1.10 × 1.00 × 0.25 m, standing |
| origin | floor 0.6–1.3 m below it (char3: 7.0 m) | character stands on y = 0 |
| ending | launched from 5 m *below* the floor, at a broken scale | launches to ~6.6 m from a grounded 1 m character |
| char3 | no animation at all, frozen mid-launch | 12.9 s grafted from `char3.glb` |
| char5 | ships a camera and two area lights | removed |

Any one of these alone is enough to break the experience. Together, an iPhone
visitor tapped **View in AR** and got a five-metre-wide object lying on its back
that Quick Look often could not anchor at all — [an oversized bounding box
leaves the model floating at camera level instead of finding a
plane](https://developer.apple.com/forums/thread/709442). And `allowsContentScaling=0`
in the link meant they could not even pinch it down to see what it was.

char3 was the worst: its USDZ had no `UsdSkelAnimation` whatsoever and its rest
pose was the final frame of the launch, so it was a static model hanging seven
metres over the spot you tapped.

## The pages were showing the wrong characters

Separate from the AR work, and true on every platform: `charN.glb` does not
hold the character in `imabox--0N.png`. Only character 03 was ever paired
correctly. The torso textures baked into each model say which is which:

| page | poster | used to load | actually is |
|---|---|---|---|
| 01 | green | char1 (orange) | **char4** |
| 02 | orange | char2 (red "21") | **char1** |
| 03 | blue | char3 | char3 — correct |
| 04 | pink | char4 (green) | **char5** |
| 05 | red "21" | char5 (pink) | **char2** |

The poster numbering is the real one: the accent colours in `characters.js`
were written against it (01 `#228442` green, 02 `#fa601c` orange, and so on),
so the file names are what is out of step. Each entry now points at whichever
model carries that character's artwork, and the per-model settings -- sequence,
SHA, approach -- travel with the model rather than staying on the id. No files
were renamed, so nothing else has to change.

A test pins the pairing, because it cannot be spotted by reading the code.

## What was wrong with the code

Three iPhone-specific bugs, plus two that were breaking Android too.

**`available()` treated "could not check" as "not there."** It ran a HEAD
request inside a `try` that returned `false` on any throw, and used
`AbortSignal.timeout()`, which Safari only shipped in 16.0. On iOS 15 and older
the call itself threw, so every asset check failed and every iPhone was told
*"This character's iPhone AR version is not available yet"* — with no AR button
at all. Even on current Safari, one dropped request did the same. It now
returns `ok` / `missing` / `unknown`, and only a real 404 hides the button.

**The Quick Look link carried the wrong parameters.** `allowsContentScaling=0`
locked a badly-scaled model at its broken size, and `canonicalWebPageURL` was
percent-encoded when Apple expects a plain URL. Both fixed; the canonical URL
now omits the cache-busting query so the share sheet points at a clean address.

**Social in-app browsers got a link that does nothing.** Opened from Instagram
or Facebook, `relList.supports('ar')` reports true but Quick Look never launches.
The new `apple-inapp` route tells the visitor to open the page in Safari.

**char1 and char5 could not mount on Android either.** Both GLBs pair
`ArmatureAction` with a `Fly_Away` clip that drives the same bones, and neither
had a `sequence` configured, so `resolveSequence` threw *"Animation clips
overlap"* and the experience failed before the AR button existed. char1 also had
an `expectedSHA256` for an older export, and a mismatch there wipes `sequence`,
`approach` and `motionNode` — so even a correct sequence would have been
discarded. The repo's own test suite reproduced this the moment it was pointed
at the shipped config.

## The launch played twice on Android

`Fly_Away` is not the second half of the animation. It is the last ~3.7 s of
`ArmatureAction` exported again as its own clip. Sequencing them one after the
other -- which is what the first fix here did, to stop `resolveSequence`
throwing on the overlap -- meant the character took off, reappeared on the
floor and took off again. iPhone never had this: the USDZ is one baked
timeline, and all five leave the ground exactly once.

`resolveSequence` now takes an `ignore` list, and char1 and char5 name
`Fly_Away` in it. Silently dropping a clip is still an error, so an omission
has to be stated; a name that does not match a clip, or a clip that is both
ignored and sequenced, is rejected rather than quietly losing animation.
char1 now plays 10.29 s instead of 14.00 s, char5 9.58 s instead of 13.29 s.

## Walking in toward the viewer

Three of the five have a walk in their animation; two do not. Measured from the
root motion in each GLB:

| character | model | walks | covers |
|---|---|---|---|
| 01 | char4 | 0.00–1.08 s | 1.24 m |
| 02 | char1 | 1.65–3.87 s | 2.60 m |
| 04 | char5 | 0.00–1.08 s | 1.24 m |
| 03, 05 | char3, char2 | never advances | — |

Each walker's `startDistance` is set to `stopDistance` plus exactly the distance
its feet cover, so the app's approach runs at the authored pace instead of
sliding the character along the floor. All three come out at about 1.16 m/s,
which is a good sign the intervals are right.

03 and 05 perform on the spot — there is no root motion to drive an approach
with. They appear at `startDistance` and stay there, so if 5 m reads as too far
away, lowering their `startDistance` is the knob.

None of this applies to iPhone. Quick Look anchors where the user taps and
plays; there is no approach to configure.

## About the 5 m approach

It cannot be done in Quick Look. There is no placement API, no camera awareness,
and no hit-testing you control — Quick Look finds a plane and anchors the file
origin there. Baking the offset into the model does not help either, because
placement is computed from the bounding box, so a character authored five metres
back just gets centred on the tap point anyway.

The characters therefore animate in place on iPhone. The real options for a
genuine approach on iOS are [8th Wall](https://www.8thwall.com) (its own SLAM in
WebAssembly, no app install, commercial licence) or [Variant
Launch](https://launch.variant3d.com) (injects a real WebXR API via App Clips) —
both keep the Android code path and replace only the iOS one.

If you want the characters to travel a little anyway, `tools/rebuild-usdz.py`
takes `--drift`: `0` is in place, `1` keeps the authored travel, higher numbers
exaggerate it. `--anchor end` puts the finishing position on the tapped point so
the character arrives there rather than leaving from it.

## The fly-away ending

It is the artist's intent, so it is kept — in full, on both platforms. All five
models are built with `--keep-flyaway` and the character launches to about
6.6 m at the end of the clip.

The reason this is safe in Quick Look is worth writing down, because it is the
one thing that could have gone wrong. Quick Look decides where to put a model by
measuring its **authored `extent`**, which is the bind pose and does not move.
That box is the standing character: 1.10 × 1.00 × 0.25 m. The launch happens
during playback, outside that box, so it does not affect placement. If the
launch *had* widened the placement box, Quick Look would have treated the file
as a 6 m object and likely failed to anchor it at all — which is exactly how the
original files behaved at 5.67 m wide.

`tools/verify-usdz.py --allow-launch` checks this directly: it reports the peak
height as expected rather than as a failure, and asserts that the placement box
is still the standing pose.

## char5's aura (the power-up ball)

It rendered as a solid white sphere swallowing the character, on **both**
platforms, and it did so before any of these changes — it only became visible
once the rest of char5 started working.

In Blender the aura is a bare **Emission** shader: black base colour, white
emissive at strength 15. What makes that read as a glow there is EEVEE's blend
mode and bloom, plus a driver on the `aura visibility controler` object. None of
that is scene data, so none of it exports. What each format got instead:

- **glTF** kept the material but as fully opaque, emissive white ×15, writing
  depth. A solid white ball that occludes everything behind it.
- **USD** dropped it entirely. Blender's USD exporter only translates Principled
  BSDF, so `/root/_materials/Aura` exported as a Material prim **containing no
  shader at all**, and a mesh bound to an empty material renders default white.

Both are now handled, as close to the intent as each format allows:

- `unwrapGlowMaterials()` in `js/experience.js` spots the signature (black base,
  non-black emissive), and switches it to additive blending with `depthWrite`
  off and the emissive strength brought back to 1. Additive plus black base is
  what an emission-only material is standing in for.
- `tools/fix-glow-material.py` writes a real `UsdPreviewSurface` into the empty
  material — emissive white at `opacity 0.3`. Quick Look has no additive
  blending, so a translucent emissive surface is the closest honest equivalent.

Opacity 0.3 was picked by rendering the power-up at 0.2 / 0.3 / 0.4 / 0.5 and
choosing the one that still reads as a glow without erasing the artwork. Change
it in one line in `experience.js` and via `--opacity` on the tool.

**This is a stand-in, not the real aura.** The driver and the blend mode only
exist in the .blend. Exported properly from source — emission and alpha through
a Principled BSDF, `alphaMode: BLEND` in glTF, the driver baked to keyframes —
both platforms would get the actual effect instead of an approximation of it.

## Two things left for you to decide

**char1's `approach` window (1.75–3.83 s) was measured on an older export.** The
`char1.glb` in the repo is a different file. The timing looks about right against
the current one, but it has not been verified on a device.

One thing worth knowing rather than deciding: char5 is 18 MB against 2–3 MB for
the others, and almost all of it is the aura — an 8,962-vertex sphere with 67
frames of baked vertex positions, about 15 MB on its own. The character itself
is roughly 1,160 vertices. It is within what Quick Look handles, but it is a
slow download on mobile data. Fewer aura frames or a lighter sphere would fix
it, and both are changes to the look, so they are yours to make.

## Running the tools

```sh
npm test                                   # 11 checks, including every shipped config
python3 tools/verify-usdz.py --allow-launch char*.usdz   # what Quick Look needs
python3 tools/rebuild-usdz.py <in> <out> --height 1.0 --drift 0 --keep-flyaway
python3 tools/graft-animation.py --check char4.usdz char4.glb
```

`tools/rebuild-usdz.py` is the one to re-run after any new Blender export —
it fixes axis, scale and grounding without touching
geometry, skinning, materials or textures. `tools/graft-animation.py` is only
needed when an export loses its animation the way char3's did; its `--check`
mode re-derives the GLB-to-USD joint mapping against a file that has both, and
reports 13/13 when the mapping holds.

Originals are kept in `build/original/` and are not committed.

## What has not been tested

A real iPhone. Everything here was verified by reading the USD stages back —
axis, metres, grounding, skinned bounds over the full timeline, texture
resolution, package alignment — and by driving the pages in headless Chromium
with an iPhone user agent to confirm the AR link appears with `rel="ar"` and a
single `<img>` child. Quick Look itself has not run on any of these files.
Please test one character on a real device before rebuilding the rest.
