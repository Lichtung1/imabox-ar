"""Check a USDZ against what AR Quick Look needs. Read-only.

    python tools/verify-usdz.py build/*.usdz

Reports the package layout, stage conventions, the real skinned bounds over
the whole timeline, and whether every texture resolves inside the archive.
Anything printed as FAIL will misbehave once the file is anchored to a floor.
"""

import sys
import zipfile
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel

LIMIT_MB = 25.0


def mark(ok):
    return 'ok  ' if ok else 'FAIL'


def check(path, allow_launch=False):
    path = Path(path)
    size_mb = path.stat().st_size / 1e6
    print(f'\n===== {path}  ({size_mb:.1f} MB) =====')

    # --- package layout: Quick Look memory-maps the archive, so every member
    # must be stored uncompressed and start on a 64-byte boundary.
    stored = aligned = True
    with path.open('rb') as raw, zipfile.ZipFile(path) as z:
        for item in z.infolist():
            offset = item.header_offset + 30 + len(item.filename) + len(item.extra)
            stored &= item.compress_type == zipfile.ZIP_STORED
            aligned &= offset % 64 == 0
    print(f'  {mark(stored)}  all members stored uncompressed')
    print(f'  {mark(aligned)}  all members aligned to 64 bytes')
    print(f'  {mark(size_mb <= LIMIT_MB)}  size under {LIMIT_MB:.0f} MB')

    stage = Usd.Stage.Open(str(path))
    up = UsdGeom.GetStageUpAxis(stage)
    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    print(f'  {mark(up == UsdGeom.Tokens.y)}  upAxis is Y (got {up})')
    print(f'  {mark(abs(mpu - 1.0) < 1e-6)}  metersPerUnit is 1.0 (got {mpu})')

    first, last = stage.GetStartTimeCode(), stage.GetEndTimeCode()
    fps = stage.GetTimeCodesPerSecond() or 24.0
    print(f'  --    timeline {first:.0f}..{last:.0f} @ {fps:.0f}fps = {(last - first) / fps:.2f}s')

    anim = [p for p in stage.Traverse() if p.IsA(UsdSkel.Animation)]
    print(f'  {mark(bool(anim))}  has skeletal animation')

    strays = [p.GetName() for p in stage.Traverse()
              if p.IsA(UsdGeom.Camera) or 'Light' in str(p.GetTypeName())]
    print(f'  {mark(not strays)}  no cameras or lights ({strays or "none"})')

    # --- real deformed bounds, not the frozen bind-pose extent. The bake goes
    # to a session layer so it cannot touch the file on disk.
    scratch = Usd.Stage.Open(str(path))
    scratch.SetEditTarget(scratch.GetSessionLayer())
    skel_root = next((p.GetPath() for p in scratch.Traverse()
                      if p.IsA(UsdSkel.Root)), None)
    UsdSkel.BakeSkinning(scratch.Traverse())
    # Meshes only: a Skeleton prim is boundable and reports its rest pose,
    # which would anchor the measured box near the origin the whole clip.
    meshes = [p for p in scratch.Traverse() if p.IsA(UsdGeom.Mesh)
              and (skel_root is None or p.GetPath().HasPrefix(skel_root))]
    cache = UsdGeom.BBoxCache(Usd.TimeCode(first),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])

    def bounds_at(t):
        cache.SetTime(Usd.TimeCode(t))
        rng = Gf.Range3d()
        for mesh in meshes:
            rng.UnionWith(cache.ComputeWorldBound(mesh).ComputeAlignedRange())
        return rng

    lows, highs, floors, centres = [], [], [], []
    steps = 40
    for i in range(steps):
        t = first + (last - first) * i / max(1, steps - 1)
        rng = bounds_at(t)
        lows.append(rng.GetMin())
        highs.append(rng.GetMax())
        floors.append(rng.GetMin()[1])
        centres.append(((rng.GetMin()[0] + rng.GetMax()[0]) / 2,
                        (rng.GetMin()[2] + rng.GetMax()[2]) / 2))

    r0 = bounds_at(first)
    h0 = r0.GetMax()[1] - r0.GetMin()[1]

    # The authored `extent` is what a viewer measures before it evaluates any
    # skinning, so it -- not the animated bounds -- decides where Quick Look
    # puts the model.
    xc = UsdGeom.XformCache()
    xc.SetTime(Usd.TimeCode(first))
    authored = Gf.Range3d()
    for mesh in meshes:
        e = UsdGeom.Mesh(mesh).GetExtentAttr().Get(Usd.TimeCode(first))
        if not e:
            continue
        M = xc.GetLocalToWorldTransform(mesh)
        for corner in (e[0], e[1]):
            authored.UnionWith(M.Transform(Gf.Vec3d(*corner)))
    placement = tuple(authored.GetMax()[i] - authored.GetMin()[i] for i in range(3))
    print(f'  --    opening pose: {h0:.2f} m tall, '
          f'{r0.GetMax()[0] - r0.GetMin()[0]:.2f} m wide, '
          f'{r0.GetMax()[2] - r0.GetMin()[2]:.2f} m deep')
    print(f'  {mark(abs(r0.GetMin()[1]) < 0.02)}  opening pose stands on y=0 (got {r0.GetMin()[1]:+.3f})')
    centre = abs(r0.GetMin()[0] + r0.GetMax()[0]) / 2, abs(r0.GetMin()[2] + r0.GetMax()[2]) / 2
    print(f'  {mark(max(centre) < 0.02)}  opening pose centred on the origin')

    peak = max(h[1] for h in highs)
    sink = min(floors)
    wander_x = max(c[0] for c in centres) - min(c[0] for c in centres)
    wander_z = max(c[1] for c in centres) - min(c[1] for c in centres)
    if allow_launch:
        # The fly-away ending is deliberate. What matters then is that the
        # authored extent still describes the standing pose, because that is the
        # box Quick Look measures to find a plane -- if the launch widened it,
        # the model would be placed as a 6 m object and might not anchor at all.
        print(f'  --    launches to {peak:.2f} m at the ending (kept on purpose)')
        print(f'  {mark(placement[1] < h0 * 1.5)}  placement box is still the standing pose '
              f'({placement[0]:.2f} x {placement[1]:.2f} x {placement[2]:.2f} m)')
    else:
        print(f'  {mark(peak < h0 * 2.5)}  never launches upward (peak {peak:.2f} m vs {h0:.2f} m tall)')
    print(f'  {mark(sink > -0.12)}  never sinks far through the floor (lowest {sink:+.3f} m)')
    print(f'  --    body wanders {wander_x:.2f} m sideways, {wander_z:.2f} m forward/back')
    print(f'  --    ends {centres[-1][1]:+.2f} m from where it started (forward is negative)')

    unresolved = []
    for prim in stage.Traverse():
        shader = UsdShade.Shader(prim)
        if not shader:
            continue
        for inp in shader.GetInputs():
            if inp.GetTypeName() == Sdf.ValueTypeNames.Asset:
                v = inp.Get()
                if v and not v.resolvedPath:
                    unresolved.append(v.path)
    print(f'  {mark(not unresolved)}  every texture resolves ({unresolved or "all good"})')


if __name__ == '__main__':
    # --allow-launch: the character is meant to fly away at the end, so check
    # the placement box instead of the peak height.
    allow = '--allow-launch' in sys.argv
    for arg in [a for a in sys.argv[1:] if not a.startswith('--')]:
        check(arg, allow_launch=allow)
