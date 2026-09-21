"""Give an empty USD material a real emissive shader.

Blender's USD exporter only translates Principled BSDF. char5's aura is a bare
Emission shader, so it exported as a Material prim containing nothing at all --
and a mesh bound to an empty material renders as flat default white, which is
why the aura shows up as a solid ball covering the character in Quick Look.

    python tools/fix-glow-material.py char5.usdz out.usdz --material Aura

Quick Look has no additive blending, so the closest honest stand-in for a glow
is an emissive surface with opacity below 1: it lights up and you can see the
character through it. --opacity and --color tune that.

This writes a material that was missing. It is not a substitute for exporting
the real one from the .blend, where the aura's look actually lives.
"""

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdShade, UsdUtils


def empty_materials(stage):
    """Material prims that contain no shader, and so render as default white."""
    out = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Material):
            continue
        if not any(UsdShade.Shader(p) for p in Usd.PrimRange(prim) if p != prim):
            out.append(prim)
    return out


def author_glow(stage, material_prim, color, opacity, strength):
    material = UsdShade.Material(material_prim)
    shader = UsdShade.Shader.Define(stage, material_prim.GetPath().AppendChild('Emission'))
    shader.CreateIdAttr('UsdPreviewSurface')
    rgb = Gf.Vec3f(*[c * strength for c in color])
    shader.CreateInput('emissiveColor', Sdf.ValueTypeNames.Color3f).Set(rgb)
    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(opacity)
    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1.0)
    shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput('useSpecularWorkflow', Sdf.ValueTypeNames.Int).Set(0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    return rgb


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--material', action='append', default=[],
                   help='material name to fix; default is every empty one')
    p.add_argument('--color', default='1,1,1')
    p.add_argument('--opacity', type=float, default=0.45)
    p.add_argument('--strength', type=float, default=1.0)
    a = p.parse_args()
    color = tuple(float(x) for x in a.color.split(','))

    work = Path(tempfile.mkdtemp(prefix='glow-'))
    try:
        with zipfile.ZipFile(a.src) as z:
            z.extractall(work)
            layer = work / z.infolist()[0].filename
        stage = Usd.Stage.Open(str(layer))

        targets = [m for m in empty_materials(stage)
                   if not a.material or m.GetName() in a.material]
        if not targets:
            raise SystemExit(f'{a.src}: no empty material to fix')
        for prim in targets:
            rgb = author_glow(stage, prim, color, a.opacity, a.strength)
            print(f'  {prim.GetName()}: emissive {tuple(round(c, 2) for c in rgb)} '
                  f'at opacity {a.opacity}')
        stage.GetRootLayer().Save()

        dst = Path(a.dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst)):
            raise SystemExit(f'could not write {dst}')
        print(f'  wrote {dst}')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
