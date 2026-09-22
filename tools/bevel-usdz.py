"""Apply the artist's bevel to the box meshes inside a USDZ.

In each .blend the three body boxes (Left, middle, Right) carry a Bevel
modifier: offset 0.1, 6 segments, angle limit 30 degrees, clamp overlap, on
smooth-shaded faces. The glTF export applies it, which is why Android shows
rounded edges. Blender's USD export wrote the raw 8-corner boxes, so iPhone
showed hard edges.

This rebuilds each box mesh with the same bevel, run by Blender itself (the
`bpy` module), and writes the result back into the USD prim: points, faces,
smooth corner normals, UVs and skin weights (interpolated across the new
geometry by the bevel). Skeleton, bind transforms, animation, materials and
everything else in the file are left alone.

    python tools/bevel-usdz.py char2.usdz out.usdz

Needs: pip install bpy usd-core
"""
import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

import bpy
import numpy as np
from pxr import Sdf, Usd, UsdGeom, UsdSkel, UsdUtils, Vt, Gf

BEVEL = dict(width=0.1, segments=6, limit_method='ANGLE', angle_limit=0.5235987901687622,
             profile=0.5, use_clamp_overlap=True, offset_type='OFFSET', affect='EDGES')
MAX_BOX_POINTS = 100  # the boxes are 32 points; wings (532) and already-bevelled meshes are skipped


def bevel_prim(prim):
    mesh = UsdGeom.Mesh(prim)
    pv = UsdGeom.PrimvarsAPI(prim)
    skel = UsdSkel.BindingAPI(prim)
    pts = np.array(mesh.GetPointsAttr().Get(), dtype=float)
    counts = list(mesh.GetFaceVertexCountsAttr().Get())
    idx = list(mesh.GetFaceVertexIndicesAttr().Get())
    left = mesh.GetOrientationAttr().Get() == UsdGeom.Tokens.leftHanded
    faces, o = [], 0
    for c in counts:
        f = idx[o:o + c]
        faces.append(f[::-1] if left else f)
        o += c
    st = pv.GetPrimvar('st')
    # Blender writes the UV indices as a single time sample, so read at the first frame.
    uv = np.array(st.ComputeFlattened(Usd.TimeCode(prim.GetStage().GetStartTimeCode())), dtype=float)  # one per face corner
    if left:  # keep corners matched to the reversed winding
        out, o = [], 0
        for c in counts:
            out.extend(uv[o:o + c][::-1]); o += c
        uv = np.array(out)
    ji_pv, jw_pv = skel.GetJointIndicesPrimvar(), skel.GetJointWeightsPrimvar()
    size = ji_pv.GetElementSize()
    ji = np.array(ji_pv.Get()).reshape(len(pts), size)
    jw = np.array(jw_pv.Get(), dtype=float).reshape(len(pts), size)

    # Build the Blender mesh.
    me = bpy.data.meshes.new('box')
    me.from_pydata(pts.tolist(), [], faces)
    me.update()
    layer = me.uv_layers.new(name='UVMap')
    for i, loop in enumerate(me.loops):
        layer.data[i].uv = uv[i]
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new('box', me)
    bpy.context.scene.collection.objects.link(ob)
    groups = {}
    for v in range(len(pts)):
        for j, w in zip(ji[v], jw[v]):
            if w <= 0:
                continue
            g = groups.get(int(j)) or ob.vertex_groups.new(name=f'j{int(j)}')
            groups[int(j)] = g
            g.add([v], float(w), 'ADD')
    mod = ob.modifiers.new('Bevel', 'BEVEL')
    for k, v in BEVEL.items():
        setattr(mod, k, v)

    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    em = ev.to_mesh()
    names = {g.index: int(g.name[1:]) for g in ob.vertex_groups}
    new_pts = [tuple(v.co) for v in em.vertices]
    new_counts = [p.loop_total for p in em.polygons]
    new_idx = [em.loops[l].vertex_index for p in em.polygons for l in p.loop_indices]
    normals = [tuple(n.vector) for n in em.corner_normals]
    uvs = [tuple(d.uv) for d in em.uv_layers['UVMap'].data]
    infl = []
    for v in em.vertices:
        pairs = sorted(((names[g.group], g.weight) for g in v.groups if g.weight > 0), key=lambda x: -x[1])
        infl.append(pairs)
    width = max(1, max(len(p) for p in infl))
    out_ji, out_jw = [], []
    for pairs in infl:
        if not pairs:
            raise SystemExit(f'{prim.GetPath()}: bevel produced a vertex with no skin weight')
        total = sum(w for _, w in pairs)
        pairs = pairs + [(0, 0.0)] * (width - len(pairs))
        out_ji += [j for j, _ in pairs]
        out_jw += [w / total for _, w in pairs]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)

    # Write back. Winding is Blender's (right-handed) now.
    mesh.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)
    mesh.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*p) for p in new_pts]))
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(new_counts))
    mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray(new_idx))
    mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*n) for n in normals]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    st.GetAttr().Set(Vt.Vec2fArray([Gf.Vec2f(*u) for u in uvs]))
    st.GetIndicesAttr().Clear()  # flat, one UV per corner, no time samples
    st.SetInterpolation(UsdGeom.Tokens.faceVarying)
    skel.CreateJointIndicesPrimvar(False, width).Set(Vt.IntArray(out_ji))
    skel.CreateJointWeightsPrimvar(False, width).Set(Vt.FloatArray(out_jw))
    mesh.GetExtentAttr().Set(UsdGeom.PointBased.ComputeExtent(Vt.Vec3fArray([Gf.Vec3f(*p) for p in new_pts])))
    return len(pts), len(new_pts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src'); p.add_argument('dst')
    a = p.parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    work = Path(tempfile.mkdtemp(prefix='bevel-'))
    try:
        with zipfile.ZipFile(a.src) as z:
            z.extractall(work); layer = work / z.infolist()[0].filename
        stage = Usd.Stage.Open(str(layer))
        done = []
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh) or not prim.HasAPI(UsdSkel.BindingAPI):
                continue
            if len(UsdGeom.Mesh(prim).GetPointsAttr().Get()) > MAX_BOX_POINTS:
                continue
            before, after = bevel_prim(prim)
            done.append(f'{prim.GetParent().GetName()} {before}->{after}')
        stage.GetRootLayer().Save()
        dst = Path(a.dst); dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): dst.unlink()
        assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(layer)), str(dst))
        print(f'  {a.src}: bevelled {", ".join(done) or "nothing"}; wrote {dst}')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
