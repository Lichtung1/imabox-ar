# Why iPhone was broken, and what changed · v9-20260921.1

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
