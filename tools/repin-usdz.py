"""Re-pin a rebuilt USDZ so it cancels travel from the right node.

rebuild-usdz.py cancels horizontal drift using the skeleton's Root joint. That
is only right when Root carries the travel. In char3 the travel lives on the
Armature *object* (the SkelRoot's own transform) and the Root joint is the
pivot for the head spin -- pinning it swung the whole character around its
hips and dragged the head around a ~55 cm circle on the floor.

This keeps every existing root-transform sample and adds, in world space, the
horizontal offset that holds the chosen prim's origin where it was on the
first frame. Nothing else in the file changes.

    python tools/repin-usdz.py char3.usdz out.usdz --prim /root/Armature
"""
import argparse, shutil, tempfile, zipfile
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdUtils

def main():
    p = argparse.ArgumentParser()
    p.add_argument('src'); p.add_argument('dst')
    p.add_argument('--prim', default='/root/Armature')
    a = p.parse_args()
    work = Path(tempfile.mkdtemp(prefix='repin-'))
    try:
        with zipfile.ZipFile(a.src) as z:
            z.extractall(work); layer = work / z.infolist()[0].filename
        stage = Usd.Stage.Open(str(layer))
        root = stage.GetDefaultPrim()
        op = UsdGeom.Xformable(root).GetOrderedXformOps()[0]
        assert op.GetOpType() == UsdGeom.XformOp.TypeTransform, 'expected one transform op on the root'
        target = stage.GetPrimAtPath(a.prim)
        times = set(op.GetTimeSamples())
        for o in UsdGeom.Xformable(target).GetOrderedXformOps():
            times |= set(o.GetTimeSamples())
        times = sorted(times)
        # Evaluate everything before writing anything.
        orig = {t: op.Get(Usd.TimeCode(t)) for t in times}
        xf = UsdGeom.XformCache()
        pos = {}
        for t in times:
            xf.SetTime(Usd.TimeCode(t))
            pos[t] = xf.GetLocalToWorldTransform(target).ExtractTranslation()
        ref = pos[times[0]]
        op.GetAttr().Clear()
        for t in times:
            d = pos[t] - ref
            fix = Gf.Matrix4d(1.0); fix.SetTranslate(Gf.Vec3d(-d[0], 0.0, -d[2]))
            op.Set(orig[t] * fix, Usd.TimeCode(t))
        stage.GetRootLayer().Save()
        dst = Path(a.dst); dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): dst.unlink()
        assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst))
        print(f'  {len(times)} samples re-pinned to {a.prim}; wrote {dst}')
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == '__main__':
    main()
