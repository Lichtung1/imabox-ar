# IMABOX

Five animated characters, a gallery, and platform-specific AR. Hosted on GitHub Pages.

Build: `v15-20260922.1`

## Models

| Page | Model | Source revision | Duration |
|---|---|---|---:|
| 01 | char4 | v2 | 18.375 s |
| 02 | char1 | v3 | 13.500 s |
| 03 | char3 | v2 | 17.042 s |
| 04 | char5 | v2 | 13.625 s |
| 05 | char2 | v3 | 25.375 s |

GLB and USDZ files come from the same approved scene timelines. Each GLB contains one Scene clip. Per-model hashes, timing and approach profiles are in characters.js.

Android uses WebXR with floor placement, measured forward movement, a two-metre stopping distance and complete animation playback. Apple uses the exported USDZ in AR Quick Look. Apple placement appearance and playback controls belong to Quick Look.

The aura in char5 retains its timed visibility and 24 fps deformation. Its mobile mesh uses one subdivision level and an emissive material approximation. It is excluded from character sizing and floor measurement.

## Development

Serve this directory through a local HTTP server for desktop previews. AR requires a secure context and supported hardware.

Run `npm install` and `npm test` for automated checks.

Keep the licences supplied with Three.js and the QR code libraries in vendor/.
