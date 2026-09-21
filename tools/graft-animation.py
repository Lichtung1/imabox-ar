"""Copy a rig's animation out of a GLB and into a USDZ that lost it.

char3.usdz shipped with correct meshes, skeleton, materials and textures but
no UsdSkelAnimation at all, and with its rest pose frozen on the last frame of
the launch-into-the-sky motion -- so on iPhone it is a static model floating
about four metres up. char3.glb has the animation the Android path already
plays, on a rig whose joint names match the USD skeleton one for one.

    python tools/graft-animation.py char3.usdz char3.glb build/raw/char3.usdz

Blender's glTF exporter absorbs its Z-up-to-Y-up conversion into the Root
joint and leaves every joint below it untouched, so all but the root copy
across verbatim. That is not an assumption: char4 ships with both a GLB and a
working USDZ, and comparing them joint by joint shows exact agreement below
the root. Run with --check <char>.usdz <char>.glb to re-do that comparison.

The result is still Blender-shaped -- run tools/rebuild-usdz.py on it after.
"""

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from glb_anim import Glb, pose  # noqa: E402

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, UsdUtils, Vt  # noqa: E402

FPS = 24.0
# Blender's glTF exporter writes this on the root joint to turn its Z-up rig
# into glTF's Y-up. Undoing it puts the root back in the USD file's frame.
YUP_FIX = np.array([0.7071067811865476, 0.0, 0.0, 0.7071067811865476])  # x,y,z,w


def usd_to_glb_name(joint_path):
    """'Root/Frame/Body_Lower' -> 'Body.Lower' (USD paths cannot hold dots)."""
    return joint_path.split('/')[-1].replace('_', '.')


def resolve_names(glb, joints):
    """Map each USD joint path to a GLB node index, tolerating dot/underscore."""
    out = {}
    for j in joints:
        leaf = j.split('/')[-1]
        for candidate in (leaf, leaf.replace('_', '.'), leaf.replace('.', '_')):
            if candidate in glb.by_name:
                out[j] = glb.by_name[candidate]
                break
        else:
            raise SystemExit(f'no GLB node matches joint {j!r}')
    return out


def quat_mul(a, b):
    """Hamilton product of (x, y, z, w) quaternions."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def root_local(t, q):
    """Undo the exporter's Y-up conversion on the root joint.

    Both halves were read off char1, char2 and char4, which ship a GLB and a
    working USDZ of the same take: the translation turns by a quarter turn
    about X, and the rotation takes the fix on the left. `--check` re-derives
    this and reports 13/13 joints when it holds.
    """
    return np.array([t[0], -t[2], t[1]]), quat_mul(YUP_FIX, q)


def graft(usdz, glb_path, dst, clip='ArmatureAction'):
    glb = Glb(glb_path)
    channels = glb.channels(clip)
    duration = glb.duration(clip)
    frames = list(range(1, int(round(duration * FPS)) + 2))

    work = Path(tempfile.mkdtemp(prefix='graft-'))
    try:
        with zipfile.ZipFile(usdz) as z:
            z.extractall(work)
            layer = work / z.infolist()[0].filename

        stage = Usd.Stage.Open(str(layer))
        skel_prim = next(p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton))
        skel = UsdSkel.Skeleton(skel_prim)
        joints = list(skel.GetJointsAttr().Get())
        nodes = resolve_names(glb, joints)

        anim_path = skel_prim.GetPath().AppendChild(clip)
        anim = UsdSkel.Animation.Define(stage, anim_path)
        anim.CreateJointsAttr().Set(Vt.TokenArray([str(j) for j in joints]))
        t_attr = anim.CreateTranslationsAttr()
        r_attr = anim.CreateRotationsAttr()
        s_attr = anim.CreateScalesAttr()

        first_pose = None
        for f in frames:
            secs = f / FPS
            ts, rs, ss = [], [], []
            for index, j in enumerate(joints):
                t, q, s = pose(glb, channels, nodes[j], secs)
                if index == 0:
                    t, q = root_local(t, q)
                ts.append(Gf.Vec3f(*[float(x) for x in t]))
                rs.append(Gf.Quatf(float(q[3]), Gf.Vec3f(float(q[0]), float(q[1]), float(q[2]))))
                ss.append(Gf.Vec3h(*[float(x) for x in s]))
            t_attr.Set(Vt_f3(ts), Usd.TimeCode(f))
            r_attr.Set(Vt_q(rs), Usd.TimeCode(f))
            s_attr.Set(Vt_h3(ss), Usd.TimeCode(f))
            if first_pose is None:
                first_pose = (ts, rs, ss)

        UsdSkel.BindingAPI.Apply(skel_prim).CreateAnimationSourceRel().SetTargets([anim_path])

        # The shipped rest pose is the final frame of the launch motion. Nothing
        # should fall back to it now that every joint is animated, but leaving it
        # in place would keep that pose one relationship away from being used.
        skel.CreateRestTransformsAttr().Set([
            UsdSkel.MakeTransform(t, r, s)
            for t, r, s in zip(*first_pose)
        ])

        # Blender parks the whole rig where it happened to sit in the scene.
        arm = skel_prim.GetParent()
        for op in UsdGeom.Xformable(arm).GetOrderedXformOps():
            if op.GetOpName() == 'xformOp:translate':
                v = op.Get() or Gf.Vec3d(0, 0, 0)
                op.Set(Gf.Vec3d(0.0, 0.0, v[2]))

        stage.SetTimeCodesPerSecond(FPS)
        stage.SetFramesPerSecond(FPS)
        stage.SetStartTimeCode(frames[0])
        stage.SetEndTimeCode(frames[-1])
        stage.GetRootLayer().Save()

        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst)):
            raise SystemExit(f'could not write {dst}')
        print(f'  grafted {clip} ({duration:.2f}s, {len(frames)} frames, '
              f'{len(joints)} joints) into {dst}')
    finally:
        shutil.rmtree(work, ignore_errors=True)


def Vt_f3(values):
    from pxr import Vt
    return Vt.Vec3fArray(values)


def Vt_h3(values):
    from pxr import Vt
    return Vt.Vec3hArray(values)


def Vt_q(values):
    from pxr import Vt
    return Vt.QuatfArray(values)


def check(usdz, glb_path, clip='ArmatureAction'):
    """Compare a USDZ that already has animation against its GLB."""
    glb = Glb(glb_path)
    channels = glb.channels(clip)
    stage = Usd.Stage.Open(usdz)
    anim = UsdSkel.Animation(next(p for p in stage.Traverse()
                                  if p.IsA(UsdSkel.Animation)))
    joints = list(anim.GetJointsAttr().Get())
    nodes = resolve_names(glb, joints)
    samples = anim.GetTranslationsAttr().GetTimeSamples()
    print(f'{usdz}: {len(joints)} joints, {len(samples)} samples '
          f'{samples[0]:.0f}..{samples[-1]:.0f}')
    for frame in (samples[0], samples[len(samples) // 8]):
        T = anim.GetTranslationsAttr().Get(Usd.TimeCode(frame))
        R = anim.GetRotationsAttr().Get(Usd.TimeCode(frame))
        secs = frame / FPS
        agree = 0
        for i, j in enumerate(joints):
            t, q, _ = pose(glb, channels, nodes[j], secs)
            if i == 0:
                t, q = root_local(t, q)
            ut = np.array(list(T[i]))
            uq = np.array([R[i].GetImaginary()[0], R[i].GetImaginary()[1],
                           R[i].GetImaginary()[2], R[i].GetReal()])
            ok_t = np.allclose(ut, t, atol=3e-3)
            ok_q = (np.allclose(uq, q, atol=3e-3) or np.allclose(uq, -q, atol=3e-3))
            agree += ok_t and ok_q
        print(f'  frame {frame:.0f} (t={secs:.3f}s): {agree}/{len(joints)} joints match')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', nargs=2, metavar=('USDZ', 'GLB'))
    p.add_argument('args', nargs='*')
    a = p.parse_args()
    if a.check:
        check(a.check[0], a.check[1])
    else:
        graft(a.args[0], a.args[1], a.args[2])
