"""Rebuild Blender-exported USDZ files so AR Quick Look can use them.

Blender writes USD in its own conventions: Z-up, scene units, the object
sitting wherever it was in the scene, and every baked clip on one timeline.
AR Quick Look assumes Y-up, treats one unit as one metre, anchors the file
origin to the tapped surface, and plays the whole stage time range. The two
do not meet, which is why these files work through the Android WebXR path
(where app.js rescales and re-grounds the GLB at runtime) and fail on iPhone.

This script leaves the geometry, skinning, materials and textures untouched.
It measures the character, then authors one animated transform on the stage's
root prim and trims the timeline. Usage:

    python tools/rebuild-usdz.py char1.usdz build/char1.usdz --height 1.0

Options:
    --height H        finished height in metres at the first pose (default 1.0)
    --drift S         fraction of the authored forward travel to keep.
                      0 = animate in place, 1 = as authored, 4 = exaggerated
                      approach (default 0)
    --anchor start|end  which moment sits on the tapped point (default start)
    --keep-flyaway    do not trim the trailing launch-into-the-sky motion
    --strip NAME      delete this root-level prim (repeatable)
"""

import argparse
import math
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, UsdUtils

FLY_AWAY_EPS = 1e-3


# ---------------------------------------------------------------- measurement

def skel_query(stage):
    """Return (skeleton query, joint order, skel root path) for the first skeleton."""
    cache = UsdSkel.Cache()
    for prim in stage.Traverse():
        if not prim.IsA(UsdSkel.Root):
            continue
        root = UsdSkel.Root(prim)
        cache.Populate(root, Usd.TraverseInstanceProxies())
        bindings = cache.ComputeSkelBindings(root, Usd.TraverseInstanceProxies())
        if not bindings:
            continue
        query = cache.GetSkelQuery(bindings[0].GetSkeleton())
        if query:
            return query, list(query.GetJointOrder()), prim.GetPath()
    return None, [], None


def joint_track(stage, query, joints, frames):
    """World-space translation of the root joint and the motion joint per frame."""
    xf = UsdGeom.XformCache()
    root_i = joints.index('Root') if 'Root' in joints else 0
    move_i = joints.index('Root/Frame') if 'Root/Frame' in joints else root_i
    track = []
    for t in frames:
        xf.SetTime(Usd.TimeCode(t))
        xs = query.ComputeJointWorldTransforms(xf)
        if not xs:
            return []
        track.append((xs[root_i].ExtractTranslation(), xs[move_i].ExtractTranslation()))
    return track


def flyaway_cut(frames, track):
    """First frame of the final uninterrupted climb, or None if there isn't one.

    Every one of these exports ends with the character launching straight up
    and holding there. That reads as a bug once the file is anchored to a
    floor, so by default we end the timeline just before the climb starts.
    """
    if len(track) < 3:
        return None
    heights = [m[2] for _, m in track]
    peak = max(heights)
    if peak <= heights[0] + 1.0:
        return None
    i = len(heights) - 1
    while i > 0 and heights[i - 1] <= heights[i] + FLY_AWAY_EPS:
        i -= 1
    return frames[i] if i > 0 else None


def measure_bounds(usd_path, frames, subject=None):
    """Axis-aligned bounds per frame, from genuinely skinned points.

    The `extent` written on a skinned mesh is the bind pose and does not move,
    so BBoxCache alone reports a frozen box. Skinning has to be baked to get
    real deformed geometry. Sdf layers are globally cached, so that bake is
    sent to a throwaway session layer -- writing it to the root layer would
    quietly fold several megabytes of baked points into the file we are about
    to save.

    Only meshes are measured, and only those under `subject` (the skel root).
    A Skeleton prim is itself boundable and reports its rest pose, which sits
    near the origin all the way through the clip; including it drags the
    measured centre back and makes the character look like it only travels
    half as far as it does. Props parented outside the skel root -- char5's
    aura and displacement helper -- are excluded for the same reason.
    """
    scratch = Usd.Stage.Open(str(usd_path))
    scratch.SetEditTarget(scratch.GetSessionLayer())
    UsdSkel.BakeSkinning(scratch.Traverse())
    meshes = [p for p in scratch.Traverse()
              if p.IsA(UsdGeom.Mesh)
              and (subject is None or p.GetPath().HasPrefix(subject))]
    if not meshes:
        meshes = [p for p in scratch.Traverse() if p.IsA(UsdGeom.Mesh)]
    cache = UsdGeom.BBoxCache(
        Usd.TimeCode(frames[0]),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
    )
    out = []
    for t in frames:
        cache.SetTime(Usd.TimeCode(t))
        rng = Gf.Range3d()
        for mesh in meshes:
            rng.UnionWith(cache.ComputeWorldBound(mesh).ComputeAlignedRange())
        out.append((rng.GetMin(), rng.GetMax()))
    return out


# ----------------------------------------------------------------- transforms

def zup_to_yup():
    """Blender's Z-up basis expressed the way Quick Look expects it."""
    m = Gf.Matrix4d(1.0)
    m.SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), -90))
    return m


def translate(v):
    m = Gf.Matrix4d(1.0)
    m.SetTranslate(Gf.Vec3d(v))
    return m


def scale(s):
    m = Gf.Matrix4d(1.0)
    m.SetScale(Gf.Vec3d(s, s, s))
    return m


def compose(drift, s, ground):
    """Cancel horizontal drift, resize to metres, stand it up, put it on the floor."""
    return translate(drift) * scale(s) * zup_to_yup() * translate(ground)


# --------------------------------------------------------------------- rebuild

def rebuild(src, dst, height=1.0, drift_keep=0.0, anchor='start',
            keep_flyaway=False, strip=()):
    work = Path(tempfile.mkdtemp(prefix='usdz-'))
    try:
        with zipfile.ZipFile(src) as z:
            z.extractall(work)
            layer_name = z.infolist()[0].filename
        layer = work / layer_name

        stage = Usd.Stage.Open(str(layer))
        fps = stage.GetTimeCodesPerSecond() or 24.0
        first, last = int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode())
        frames = list(range(first, last + 1))

        query, joints, skel_root = skel_query(stage)
        track = joint_track(stage, query, joints, frames) if query else []

        cut = None if keep_flyaway or not track else flyaway_cut(frames, track)
        if cut is not None:
            frames = [t for t in frames if t <= cut]
            track = track[:len(frames)]

        bounds = measure_bounds(layer, frames, skel_root)

        # Height comes from the first pose, matching how the Android path grounds
        # the character, so both platforms agree on scale.
        lo0, hi0 = bounds[0]
        raw_height = hi0[2] - lo0[2]
        if raw_height <= 0:
            raise SystemExit(f'{src}: model has no measurable height')
        s = height / raw_height

        # Horizontal drift, in original units, relative to the opening frame.
        if track:
            origin = track[0][0]
            drift = [Gf.Vec3d(r[0] - origin[0], r[1] - origin[1], 0.0) for r, _ in track]
        else:
            drift = [Gf.Vec3d(0, 0, 0)] * len(frames)
        comp = [d * (drift_keep - 1.0) for d in drift]

        # Where the character should stand when Quick Look drops it on a surface.
        pin = 0 if anchor == 'start' else len(frames) - 1
        lo_pin, hi_pin = bounds[pin]
        pinned = comp[pin]
        cx = (lo_pin[0] + hi_pin[0]) / 2 + pinned[0]
        cy = (lo_pin[1] + hi_pin[1]) / 2 + pinned[1]
        floor = lo0[2]
        # After the Z-up to Y-up turn, Blender's +Y becomes Quick Look's -Z.
        ground = Gf.Vec3d(-cx * s, -floor * s, cy * s)

        root = stage.GetDefaultPrim()
        xform = UsdGeom.Xformable(root)
        xform.ClearXformOpOrder()
        op = xform.AddTransformOp()
        matrices = [compose(c, s, ground) for c in comp]
        if all(m == matrices[0] for m in matrices):
            op.Set(matrices[0])
        else:
            for t, m in zip(frames, matrices):
                op.Set(m, Usd.TimeCode(t))

        for name in strip:
            child = root.GetChild(name)
            if child:
                stage.RemovePrim(child.GetPath())

        if cut is not None:
            trim_samples(stage, cut)

        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetTimeCodesPerSecond(fps)
        stage.SetFramesPerSecond(fps)
        stage.SetStartTimeCode(frames[0])
        stage.SetEndTimeCode(frames[-1])
        stage.GetRootLayer().Save()

        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst)):
            raise SystemExit(f'{src}: could not write {dst}')

        return {
            'source': str(src), 'output': str(dst),
            'scale': s, 'raw_height': raw_height,
            'frames': (frames[0], frames[-1]), 'fps': fps,
            'seconds': (frames[-1] - frames[0]) / fps,
            'trimmed_flyaway_at': cut,
            'stripped': list(strip),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def trim_samples(stage, cut):
    """Drop time samples past the cut so the file cannot play the trailing motion."""
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            times = attr.GetTimeSamples()
            if not times:
                continue
            late = [t for t in times if t > cut]
            if not late:
                continue
            keep = attr.Get(Usd.TimeCode(cut))
            for t in late:
                attr.ClearAtTime(Usd.TimeCode(t))
            if keep is not None:
                attr.Set(keep, Usd.TimeCode(cut))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--height', type=float, default=1.0)
    p.add_argument('--drift', type=float, default=0.0)
    p.add_argument('--anchor', choices=['start', 'end'], default='start')
    p.add_argument('--keep-flyaway', action='store_true')
    p.add_argument('--strip', action='append', default=[])
    a = p.parse_args()
    report = rebuild(a.src, a.dst, a.height, a.drift, a.anchor,
                     a.keep_flyaway, a.strip)
    for k, v in report.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
