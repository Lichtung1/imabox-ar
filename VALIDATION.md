# Validation · v7-20260921.1

Inspected repository commit: `a217875d5eaf1977220867ca5478ed561b513575`, branch `main`. Its files were index.html, ar-v4.html, ar-v6.html and char1.glb. The root index was older than the v6 experience. The current v6 corrections were used as the basis for the integrated scene hierarchy, placement, motion compensation and animation completion behaviour.

The supplied friend ZIP contains the gallery, five character pages, posters, logo, stylesheet and JavaScript. It already proposed model-viewer routing for Android and Apple; it was not iPhone-only. All model paths were null. No models or QR images were included. Its local-file instructions were a development-preview workflow, not an implemented visitor download requirement.

## Actual model evidence

Only the older repository char1.glb could be examined. Size: 3,023,864 bytes; SHA-256: `348b61ea4dd9e3c583ccc575b134f95ecbf681b62f6c52fed5d379bff626ea90`.

One clip, ArmatureAction: 8.9166669846 seconds, 40 tracks, five mesh objects, 4,156 vertices. Frame is the compensation node; both the armature and rig contribute horizontal motion. The root hierarchy includes an existing Scale node. No export transforms or model bytes were changed.

Visual pose checks were rendered at 0, 1.667, 2.5, 3.75, 4.25, 5.8, 6.6 and 8.916667 seconds. The running section is approximately 1.75–3.83 seconds, followed by a lowered/bending pose and a return to upright around 6.5 seconds. Playback includes all of this plus the remaining clip tail.

At configured 1 m height, initial bounds are approximately x = -0.550 to +0.550 m, y = 0 to 1.000 m, z = -0.126 to +0.126 m. Initial grounding is evaluated after animation, skinning and scale. A full matrix update is essential because skinned mesh bind-matrix inverses must follow the new ancestor transforms.

Sampling at 30 Hz gives horizontal compensation error below 1e-14 m. After the floor-penetration correction, the lowest point ranges from effectively 0 to about +0.0284 m; authored upward bounce is retained. The original animation would otherwise put some geometry about 6 cm below the initial floor during the ending. Final pose remains unchanged when advancing another ten seconds. This numeric result is not a phone surface-tracking measurement.

The audit report records complete clip names, track names, sampled motion, bounds and final bone transforms. It explicitly lists every absent model.

## Checks completed

| Check | Result |
| --- | --- |
| Full clip continues after approach ends and holds final pose | Passed regression test and real-model browser playback |
| Replay resets the timeline | Passed |
| Simultaneous disjoint clips finish at longest duration | Passed |
| Overlapping clips require configured sequence | Passed |
| Explicit sequential clips include ending and reject omissions | Passed |
| Stopping-circle intersection catches a large step | Passed |
| Apple, iPad desktop UA, Android and desktop routing | Passed pure-function tests |
| Real skinned model height, grounding, compensation, final pose | Passed |
| Five gallery links and previous/next character navigation | Passed in headless Chromium |
| Missing GLB preserves poster and navigation | Passed |
| USDZ link available without GLB | Passed with emulated Quick Look capability and a stub HEAD response; no native viewer tested |
| Legacy v6 and character-query redirects | Passed |
| 390 px mobile and 1280 px desktop horizontal layout | No horizontal overflow |
| Browser JavaScript exceptions | None in tested flows |
| Visible build label and no size/distance/facing visitor inputs | Verified |

## Not verified

All newly exported character models, every USDZ, char5 optimisation, deployed Pages MIME headers, actual Android WebXR session behaviour and real iPhone Quick Look. No models were synthesized or silently substituted for missing characters. The embedded repository char1 is explicitly identified as the older export.

## Implementation notes

The app remains static and all runtime JavaScript dependencies are bundled locally (Three.js 0.180.0 and QR code generation). There is no external model-viewer/CDN dependency or backend. Versioned module/asset URLs and a visible build label help distinguish deployments. Error messages and asset checks are independent for Apple and GLB previews.

Unknown/new exports do not inherit char1 timing. Clips are never truncated to the approach duration, played only because they are first in an array, or automatically concatenated when they might be alternatives. The approach interval and clip sequence for missing exports remain pending review.
