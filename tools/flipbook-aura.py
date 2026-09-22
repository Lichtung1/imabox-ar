"""Turn char5's point-cached aura into something AR Quick Look can play.

Blender exports the aura as ONE mesh whose points (and, 15 times, whose
topology) change every frame. RealityKit does not play point caches or
changing topology, so Quick Look showed the first shape frozen -- and because
the export also lost the aura's hide/show keys and wrote the material fully
opaque, iPhone got a solid white spiky blob on top of the character from the
first frame to the last.

This replaces it with a flipbook: one small mesh per source frame, each
switched on for exactly its own frame by a stepped scale key (transform
animation is what Quick Look plays reliably). The aura's own
translate/rotate/scale animation is kept as-is. The material becomes
emissive white at --opacity, double-sided, matching the Android look.

    python tools/flipbook-aura.py char5.usdz out.usdz --first 74 --last 232
"""
import argparse, shutil, tempfile, zipfile
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt

OFF = 1e-4      # effectively invisible: a speck at the aura centre, inside the body
STEP = 0.01     # frames; makes each switch a step rather than a one-frame grow

def main():
    p = argparse.ArgumentParser()
    p.add_argument('src'); p.add_argument('dst')
    p.add_argument('--mesh', default='/root/aura/Sphere_001')
    p.add_argument('--first', type=int, default=74, help='first visible frame (Android: 3.042 s)')
    p.add_argument('--last', type=int, default=232, help='last visible frame (Android: 9.625 s)')
    p.add_argument('--every', type=int, default=1, help='keep every Nth frame (2 = 12 fps flicker, half the size)')
    p.add_argument('--opacity', type=float, default=0.35)
    a = p.parse_args()
    work = Path(tempfile.mkdtemp(prefix='aura-'))
    try:
        with zipfile.ZipFile(a.src) as z:
            z.extractall(work); layer = work / z.infolist()[0].filename
        stage = Usd.Stage.Open(str(layer))
        src = stage.GetPrimAtPath(a.mesh)
        mesh = UsdGeom.Mesh(src)
        parent = src.GetParent().GetPath()
        mat = UsdShade.MaterialBindingAPI(src).GetDirectBinding().GetMaterial()
        start, end = stage.GetStartTimeCode(), stage.GetEndTimeCode()
        frames = list(range(a.first, a.last + 1, a.every))
        counts = mesh.GetFaceVertexCountsAttr().Get()
        shells = []
        for f in frames:
            t = Usd.TimeCode(f)
            pts = mesh.GetPointsAttr().Get(t)
            idx = mesh.GetFaceVertexIndicesAttr().Get(t)
            m = UsdGeom.Mesh.Define(stage, parent.AppendChild(f'Aura_{f:03d}'))
            m.CreatePointsAttr(pts)
            m.CreateFaceVertexCountsAttr(counts)
            m.CreateFaceVertexIndicesAttr(idx)
            m.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(pts))
            m.CreateDoubleSidedAttr(True)
            m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
            UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)
            shells.append((f, m))
        stage.RemovePrim(src.GetPath())
        # One stepped visibility window per shell.
        for i, (f, m) in enumerate(shells):
            until = shells[i + 1][0] if i + 1 < len(shells) else a.last + 1
            op = m.AddScaleOp()
            keys = [(start, OFF), (f - STEP, OFF), (f, 1.0), (until - STEP, 1.0), (until, OFF), (end, OFF)]
            for t, s in keys:
                if start <= t <= end:
                    op.Set(Gf.Vec3f(s, s, s), Usd.TimeCode(t))
        # Emissive, see-through, unlit-looking: Quick Look has no additive
        # blending, so this is the closest match to Android's additive glow.
        for prim in Usd.PrimRange(mat.GetPrim()):
            sh = UsdShade.Shader(prim)
            if not sh or sh.GetIdAttr().Get() != 'UsdPreviewSurface':
                continue
            for name, typ, val in [('diffuseColor', Sdf.ValueTypeNames.Color3f, Gf.Vec3f(0, 0, 0)),
                                   ('emissiveColor', Sdf.ValueTypeNames.Color3f, Gf.Vec3f(1, 1, 1)),
                                   ('opacity', Sdf.ValueTypeNames.Float, a.opacity),
                                   ('roughness', Sdf.ValueTypeNames.Float, 1.0),
                                   ('metallic', Sdf.ValueTypeNames.Float, 0.0),
                                   ('clearcoat', Sdf.ValueTypeNames.Float, 0.0)]:
                sh.CreateInput(name, typ).Set(val)
        stage.GetRootLayer().Save()
        dst = Path(a.dst); dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): dst.unlink()
        assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst))
        print(f'  {len(shells)} aura frames {frames[0]}..{frames[-1]}, opacity {a.opacity}; wrote {dst} '
              f'({dst.stat().st_size/1e6:.1f} MB)')
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == '__main__':
    main()
