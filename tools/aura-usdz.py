"""Give char5's aura (Imabox 04's power-up) a calm look that AR Quick Look can play.

Blender exports the aura as ONE mesh whose points (and 15 times, its topology)
change every frame. RealityKit does not play point caches or changing
topology. The export had also lost the aura's hide/show keys and wrote the
material fully opaque, so iPhone showed a solid white blob for the whole clip.

v14 swapped in one exported shape per frame. That played, but a new random
spiky shape 24 times a second read as strobing light on iPhone, where Android
blends smoothly between them.

This version keeps a few of the artist's own aura shapes (from the fully
powered-up part of the clip), layers them faintly, and moves them only with
smooth transform animation, which Quick Look plays reliably. Each layer turns
slowly around the vertical axis at its own speed and direction and breathes
gently in size. Nothing switches or flashes. The layers show on the same frames
as on Android (74 to 232) and inherit the aura's own grow/shrink animation.

    python tools/aura-usdz.py char5_source.usdz out.usdz

The source must still contain the original point-cached mesh
(/root/aura/Sphere_001), as Blender exported it.
"""
import argparse
import math
import shutil
import tempfile
import zipfile
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt

OFF = 1e-4    # hidden: a speck at the aura centre, inside the body
STEP = 0.01   # frames; makes show/hide a clean step

# (source frame, degrees per frame, pulse period in frames, pulse phase)
LAYERS = [(112, 3.0, 36, 0.0), (160, -2.2, 44, 0.33), (204, 1.6, 52, 0.66)]
PULSE = 0.05  # +/- 5% breathing


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src'); p.add_argument('dst')
    p.add_argument('--mesh', default='/root/aura/Sphere_001')
    p.add_argument('--first', type=int, default=74, help='first visible frame (Android: 3.042 s)')
    p.add_argument('--last', type=int, default=232, help='last visible frame (Android: 9.625 s)')
    p.add_argument('--opacity', type=float, default=0.12, help='per layer; three layers overlap')
    a = p.parse_args()
    work = Path(tempfile.mkdtemp(prefix='aura-'))
    try:
        with zipfile.ZipFile(a.src) as z:
            z.extractall(work); layer = work / z.infolist()[0].filename
        stage = Usd.Stage.Open(str(layer))
        src = stage.GetPrimAtPath(a.mesh)
        if not src:
            raise SystemExit(f'{a.src}: no {a.mesh}; start from the Blender export, not a rebuilt file')
        mesh = UsdGeom.Mesh(src)
        parent = src.GetParent().GetPath()
        mat = UsdShade.MaterialBindingAPI(src).GetDirectBinding().GetMaterial()
        start, end = int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode())
        counts = mesh.GetFaceVertexCountsAttr().Get()

        for n, (frame, speed, period, phase) in enumerate(LAYERS):
            t = Usd.TimeCode(frame)
            pts = mesh.GetPointsAttr().Get(t)
            # Centre the shape on its own origin so it turns in place.
            c = sum((Gf.Vec3d(q) for q in pts), Gf.Vec3d(0)) / len(pts)
            local = Vt.Vec3fArray([Gf.Vec3f(Gf.Vec3d(q) - c) for q in pts])
            shell = UsdGeom.Mesh.Define(stage, parent.AppendChild(f'Aura_{"ABC"[n]}'))
            shell.CreatePointsAttr(local)
            shell.CreateFaceVertexCountsAttr(counts)
            shell.CreateFaceVertexIndicesAttr(mesh.GetFaceVertexIndicesAttr().Get(t))
            shell.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(local))
            shell.CreateDoubleSidedAttr(True)
            shell.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
            UsdShade.MaterialBindingAPI.Apply(shell.GetPrim()).Bind(mat)

            shell.AddTranslateOp().Set(Gf.Vec3d(c))
            rot = shell.AddRotateZOp()
            scl = shell.AddScaleOp()
            s_off = Gf.Vec3f(OFF)
            scl.Set(s_off, Usd.TimeCode(start))
            scl.Set(s_off, Usd.TimeCode(a.first - STEP))
            for f in range(a.first, a.last + 1):
                rot.Set(speed * (f - a.first) + 120.0 * n, Usd.TimeCode(f))
                k = 1.0 + PULSE * math.sin(2 * math.pi * ((f - a.first) / period + phase))
                scl.Set(Gf.Vec3f(k), Usd.TimeCode(f))
            scl.Set(Gf.Vec3f(1.0 + PULSE * math.sin(2 * math.pi * ((a.last + 1 - STEP - a.first) / period + phase))),
                    Usd.TimeCode(a.last + 1 - STEP))
            scl.Set(s_off, Usd.TimeCode(a.last + 1))
            scl.Set(s_off, Usd.TimeCode(end))
        stage.RemovePrim(src.GetPath())

        # Emissive and faint. Quick Look has no additive blending, so a
        # see-through emissive surface is the closest match to Android's glow.
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
        print(f'  {len(LAYERS)} aura layers, frames {a.first}..{a.last}, opacity {a.opacity} each; '
              f'wrote {dst} ({dst.stat().st_size / 1e6:.1f} MB)')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
