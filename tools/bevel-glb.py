"""Apply the artist's bevel to the box meshes inside a GLB.

char5.glb (Imabox 04) was exported without its Bevel modifiers, so its body
boxes have hard edges while the other four characters' are rounded. This
welds each box back into one closed mesh, applies the same bevel the .blend
files use (offset 0.1, 6 segments, 30-degree angle limit, clamp, smooth
shading) with Blender itself, and writes the new vertices, normals, UVs and
skin weights into the GLB in place. Animation, skins, materials, textures
and every other mesh are copied through untouched.

    python tools/bevel-glb.py char5.glb out.glb

Needs: pip install bpy
"""
import argparse
import json
import struct
from pathlib import Path

import bpy  # must come first: it puts bmesh on the path
import bmesh
import numpy as np

BEVEL = dict(width=0.1, segments=6, limit_method='ANGLE', angle_limit=0.5235987901687622,
             profile=0.5, use_clamp_overlap=True, offset_type='OFFSET', affect='EDGES')
BOXES = ('Left', 'middle', 'Right')
DT = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
N = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


class Glb:
    def __init__(self, path):
        raw = Path(path).read_bytes()
        n = struct.unpack('<I', raw[12:16])[0]
        self.j = json.loads(raw[20:20 + n])
        rest = raw[20 + n:]
        self.bin = bytearray(rest[8:8 + struct.unpack('<I', rest[:4])[0]])

    def read(self, i):
        a = self.j['accessors'][i]; bv = self.j['bufferViews'][a['bufferView']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        return np.frombuffer(bytes(self.bin), DT[a['componentType']], a['count'] * N[a['type']], off).reshape(a['count'], -1)

    def add(self, arr, ctype, atype, target=None, minmax=False):
        while len(self.bin) % 4: self.bin.append(0)
        data = np.ascontiguousarray(arr, dtype=DT[ctype]).tobytes()
        bv = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target: bv['target'] = target
        self.bin += data
        self.j['bufferViews'].append(bv)
        acc = {'bufferView': len(self.j['bufferViews']) - 1, 'componentType': ctype,
               'count': len(arr), 'type': atype}
        if minmax:
            acc['min'] = np.asarray(arr).min(0).tolist(); acc['max'] = np.asarray(arr).max(0).tolist()
        self.j['accessors'].append(acc)
        return len(self.j['accessors']) - 1

    def save(self, path):
        while len(self.bin) % 4: self.bin.append(0)
        self.j['buffers'][0]['byteLength'] = len(self.bin)
        js = json.dumps(self.j, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin))
        out += struct.pack('<II', len(js), 0x4E4F534A) + js
        out += struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin)
        Path(path).write_bytes(out)


def bevel(pos, uv, joints, weights, tris):
    # Weld corners that glTF split for normals/UVs, keeping UVs per face corner.
    key = {tuple(np.round(p, 5)): None for p in pos}
    uniq = list(key); lookup = {k: i for i, k in enumerate(uniq)}
    remap = [lookup[tuple(np.round(p, 5))] for p in pos]
    bm = bmesh.new()
    # Create layers before any geometry: adding a layer invalidates element references.
    dl = bm.verts.layers.deform.verify()
    uvl = bm.loops.layers.uv.new('UVMap')
    verts = [bm.verts.new(k) for k in uniq]
    for src, dst in enumerate(remap):
        for j, w in zip(joints[src], weights[src]):
            if w > 0:
                verts[dst][dl][int(j)] = float(w)
    for t in tris:
        f = bm.faces.new([verts[remap[i]] for i in t])
        f.smooth = True
        for loop, i in zip(f.loops, t):
            loop[uvl].uv = (float(uv[i][0]), 1.0 - float(uv[i][1]))  # glTF v is flipped
    bmesh.ops.join_triangles(bm, faces=bm.faces, angle_face_threshold=0.01, angle_shape_threshold=3.2,
                             cmp_uvs=True)
    me = bpy.data.meshes.new('box'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('box', me); bpy.context.scene.collection.objects.link(ob)
    groups = sorted({int(j) for js, ws in zip(joints, weights) for j, w in zip(js, ws) if w > 0})
    for g in range(max(groups) + 1):
        ob.vertex_groups.new(name=f'j{g}')
    mod = ob.modifiers.new('Bevel', 'BEVEL')
    for k, v in BEVEL.items(): setattr(mod, k, v)
    mod2 = ob.modifiers.new('Tri', 'TRIANGULATE')
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); em = ev.to_mesh()
    # glTF wants one vertex per unique (position, normal, uv): emit per corner, then dedupe.
    rows, index = {}, []
    out_pos, out_nrm, out_uv, out_j, out_w = [], [], [], [], []
    for poly in em.polygons:
        for li in poly.loop_indices:
            loop = em.loops[li]; v = em.vertices[loop.vertex_index]
            n = em.corner_normals[li].vector; t = em.uv_layers['UVMap'].data[li].uv
            k = (loop.vertex_index, round(n.x, 5), round(n.y, 5), round(n.z, 5), round(t.x, 6), round(t.y, 6))
            if k not in rows:
                pairs = sorted(((g.group, g.weight) for g in v.groups if g.weight > 0), key=lambda x: -x[1])[:4]
                if not pairs: raise SystemExit('bevel produced a vertex with no skin weight')
                tot = sum(w for _, w in pairs); pairs += [(0, 0.0)] * (4 - len(pairs))
                rows[k] = len(out_pos)
                out_pos.append(tuple(v.co)); out_nrm.append(tuple(n)); out_uv.append((t.x, 1.0 - t.y))
                out_j.append([p[0] for p in pairs]); out_w.append([p[1] / tot for p in pairs])
            index.append(rows[k])
    ev.to_mesh_clear(); bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
    return (np.array(out_pos), np.array(out_nrm), np.array(out_uv), np.array(out_j), np.array(out_w),
            np.array(index))


def main():
    p = argparse.ArgumentParser(); p.add_argument('src'); p.add_argument('dst'); a = p.parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    g = Glb(a.src)
    for node in g.j['nodes']:
        if node.get('name') not in BOXES or 'mesh' not in node:
            continue
        for prim in g.j['meshes'][node['mesh']]['primitives']:
            at = prim['attributes']
            pos, uv = g.read(at['POSITION']), g.read(at['TEXCOORD_0'])
            if len(pos) > 100:
                print(f'  {node["name"]}: already bevelled ({len(pos)} vertices), skipped'); continue
            tris = g.read(prim['indices']).reshape(-1, 3)
            P, Nn, U, J, W, I = bevel(pos, uv, g.read(at['JOINTS_0']), g.read(at['WEIGHTS_0']), tris)
            jtype = 5121 if J.max() < 256 else 5123
            prim['attributes'] = {
                'POSITION': g.add(P, 5126, 'VEC3', 34962, minmax=True),
                'NORMAL': g.add(Nn, 5126, 'VEC3', 34962),
                'TEXCOORD_0': g.add(U, 5126, 'VEC2', 34962),
                'JOINTS_0': g.add(J, jtype, 'VEC4', 34962),
                'WEIGHTS_0': g.add(W, 5126, 'VEC4', 34962),
            }
            prim['indices'] = g.add(I, 5123 if len(P) < 65536 else 5125, 'SCALAR', 34963)
            print(f'  {node["name"]}: {len(pos)} -> {len(P)} vertices')
    # Old box accessors stay in the file unreferenced (a few kB); nothing else moves.
    g.save(a.dst)
    print(f'  wrote {a.dst}')


if __name__ == '__main__':
    main()
