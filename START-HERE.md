# IMABOX v7 · 21 September 2026

The website integration is implemented. This package contains your friend’s design, the custom Android AR experience, five character routes, and the **existing repository copy of char1.glb**. The new exports were not attached, so this is not yet a verified five-character release.

## Upload to your existing GitHub repository

1. Extract the ZIP. Open the `imabox-ar` folder inside it.
2. Open [Lichtung1/imabox-ar](https://github.com/Lichtung1/imabox-ar). Choose **Add file → Upload files**.
3. Drag the **contents** of the extracted `imabox-ar` folder into the repository root. Do not upload the ZIP itself, and do not put everything inside another `imabox-ar` subfolder. Replace the matching HTML files. Commit the changes to `main`.
4. In **Settings → Pages**, retain **Deploy from a branch → main → /(root)**. No server, build command, npm installation, or separate hosting service is needed for deployment. If the repository currently uses a different Pages publishing source, put these files in that source instead.
5. Wait for the Pages deployment to finish in **Actions**, then open the links below. Check that the footer says **IMABOX · v7-20260921.1**.

Gallery: https://lichtung1.github.io/imabox-ar/?v=v7-20260921.1

Character 1: https://lichtung1.github.io/imabox-ar/characters/01/?v=v7-20260921.1

Characters 2–5 use `/characters/02/`, `/characters/03/`, `/characters/04/`, `/characters/05/` with the same version query.

These are the URLs to test **after you upload**. This work has not been pushed to GitHub or deployed for you. The existing public site remains unchanged until you upload.

The old `/ar-v6.html` and `/ar-v4.html` addresses now forward to the new character 1 page. Existing character-page links remain valid. `/?char=3` and `/?character=03` also work. QR codes are generated locally for the current character page; use the deployed HTTPS page when printing/scanning them.

## Add your new models

Put all ten files alongside `index.html`, using exactly these lowercase names:

| Character | GLB | USDZ | Included here |
| --- | --- | --- | --- |
| 1 | char1.glb | char1.usdz | Older repository GLB only |
| 2 | char2.glb | char2.usdz | Neither |
| 3 | char3.glb | char3.usdz | Neither |
| 4 | char4.glb | char4.usdz | Neither |
| 5 | char5.glb | char5.usdz | Neither |

Your screenshot lists nine files and omits `char3.glb`. It does not establish that the file is missing from your computer, only that it was not in the screenshot. The attached website ZIP contains no GLB or USDZ files at all.

**Please supply the actual new exports before treating the timing, direction and grounding of all five characters as verified.** The website checks GLB and USDZ availability separately. Missing files show the character artwork and an availability message. A USDZ can open on iPhone even if its GLB is missing.

New GLBs get a full-animation preview. A single clip is played completely. Multiple disjoint clips play simultaneously; overlapping clips require an explicit sequence in `characters.js`, rather than guessing which is the complete animation. Unreviewed exports play in place until an approach interval is configured. This avoids inventing the timing of the running section.

Your screenshot’s `char5.usdz` is about 37.3 MiB. GitHub browser uploads have a **25 MiB per-file limit**, while Git pushes allow files up to 100 MiB. For that file, use GitHub Desktop: clone this repository, copy the website contents and models into its folder, commit, then **Push origin**. Do not turn these models into Git LFS pointers for Pages. [GitHub’s upload limits](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

## What visitors do

On compatible Android Chrome: tap **Start AR**, scan a level floor, then tap **Place & Play** when the orange circle is on a suitable starting point. The animation runs in full and holds the final pose. There are no visitor size, distance, facing, or height-trim controls.

On iPhone/iPad: tap **View in AR**. This directly opens the hosted USDZ in Apple Quick Look. Visitors do not need to download a file and load it manually. Quick Look handles surface placement. Safari guidance is shown when the browser does not advertise Quick Look support.

On desktop: play the full 3D animation, drag to inspect it, or scan the character-specific QR code with a phone. Android browsers without WebXR get Chrome/device guidance.

## Configuration

Edit `characters.js`. Defaults are **5 m starting distance (provisional), 2 m stopping distance, 1 m character height**. Individual characters can override them.

The start point uses the camera’s horizontal heading at the configured distance and the detected surface’s height. The marker and spawn use the same stored point. This extends the detected level surface mathematically; it does not prove that a floor exists across the entire path. Use a clear, level floor, not a tabletop or stairs.

The destination is 2 m from the viewer’s placement-time position. A live horizontal proximity check can stop the approach earlier if the viewer moves into the route. The model does not chase someone who walks away. Distance refers to the character’s anchor, not its foremost animated limb.

For the supplied older char1 export, approach is configured from **1.75 to 3.8333333333 seconds**. The full clip ends at **8.9166669846 seconds**. The approach stops before the bending/recovery section, which continues to the final upright pose. This is a visual/numeric interpretation of the export, not animator-provided timing metadata.

The char1 profile includes its SHA-256 fingerprint. If you replace that file, the old timing and named-clip assumptions are discarded automatically. Review the new file and update `expectedSHA256`, `motionNode`, `sequence`, and `approach`. Set a per-character interval such as `approach: {start: 1.75, end: 3.8333333333}` only after reviewing it. For consecutive clips, use `sequence: [{clips: ['Run']}, {clips: ['Ending']}]`; tracks in the same group must be disjoint. Every exported clip must be accounted for.

Change `assetRevision` when replacing a model. For code releases, update the visible build string and version queries in HTML/JS too. A query string on the page alone does not invalidate unchanged model URLs.

## Apple behaviour and remaining testing

Quick Look supports hosted USDZ models and embedded animation. Its `rel="ar"` link opens the native viewer directly. The link asks Quick Look to disable scaling with `allowsContentScaling=0`, and sharing points back to the character webpage. [Apple’s current gallery](https://developer.apple.com/quick-look-gallery/), [WebKit’s link requirements](https://webkit.org/blog/8421/viewing-augmented-reality-assets-in-safari-for-ios/), [Apple’s scaling/link parameters](https://developer.apple.com/videos/play/wwdc2020/10604/).

Quick Look does not execute this website’s Three.js code. To resemble the Android sequence, each USDZ needs the whole skeletal animation, intended dimensions, correct ground origin and facing, and its approach/ending motion authored inside the asset. A baked path is relative to the placed model. It cannot guarantee an automatic start 5 m from the current viewer or a stop exactly 2 m in front of that viewer. Native placement/rotation UI remains under Apple’s control. A one-shot ending/held pose and any looping behaviour must be checked in Quick Look; this page cannot impose the Android playback policy on the native viewer.

No iPhone was available and no USDZ bytes were supplied. Therefore no claim is made about their animation, textures, scale, grounding, MIME response after deployment, playback start, looping, final pose, or actual Quick Look launch. On a borrowed iPhone, test every character in Safari over HTTPS: direct opening, placement, size, full ending, repeat behaviour, return-to-page and sharing. The USDZ response should have `Content-Type: model/vnd.usdz+zip`.

On Android Chrome, test camera permissions, marker alignment at 5 m, grounding throughout the run/ending, the 2 m stop, stepping closer, tracking loss, replay, place again, exit and re-entry. Desktop tests cannot validate a real hit-test plane, camera pose, or ARCore performance.

## char5.usdz size

It was not supplied, so no size reduction has been performed or promised. The included `tools/inspect-usdz.py` can list archive members, image dimensions, sizes and USDZ alignment without modifying anything. This will distinguish large textures from large geometry/animation data when the file is available.

Lossless texture optimisation and removal of proven duplicate/unused data may help, but must preserve references and animation. Resolution reductions or geometry simplification need visual comparison; they are not automatically lossless. Do not just recompress it as a normal ZIP: USDZ requires stored, uncompressed members and 64-byte alignment. [OpenUSD specification](https://openusd.org/release/spec_usdz.html).

## Developer checks (optional, not needed to upload)

Run `npm install` followed by `npm test` for the regression tests. Run `node tools/audit-models.mjs > MODEL-AUDIT.json` to inspect available GLBs. The audit intentionally skips texture decoding but evaluates animation and skinned geometry. `MODEL-AUDIT.json` and `VALIDATION.md` describe the supplied model and checks performed here.

For a local browser preview, serve the folder using VS Code Live Server or `python -m http.server 8000`, then open `http://localhost:8000`. Do not double-click the HTML files: this version uses JavaScript modules and model requests. Actual phone AR should use the GitHub Pages HTTPS URL.
