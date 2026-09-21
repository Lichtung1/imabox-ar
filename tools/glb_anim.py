"""Minimal glTF/GLB animation reader, enough to move a rig into UsdSkel.

Only what this project needs: node hierarchy, static TRS, and the sampled
TRS channels of a named animation. No meshes, no materials.
"""

import json
import struct
from pathlib import Path

import numpy as np

COMPONENT = {5120: 'i1', 5121: 'u1', 5122: 'i2', 5123: 'u2', 5125: 'u4', 5126: 'f4'}
COUNT = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class Glb:
    def __init__(self, path):
        raw = Path(path).read_bytes()
        json_len = struct.unpack('<I', raw[12:16])[0]
        self.json = json.loads(raw[20:20 + json_len])
        rest = raw[20 + json_len:]
        bin_len = struct.unpack('<I', rest[0:4])[0]
        self.bin = rest[8:8 + bin_len]
        self.nodes = self.json['nodes']
        self.by_name = {n.get('name'): i for i, n in enumerate(self.nodes)}
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                self.parent[c] = i

    def accessor(self, index):
        acc = self.json['accessors'][index]
        view = self.json['bufferViews'][acc['bufferView']]
        start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        n = acc['count'] * COUNT[acc['type']]
        dtype = np.dtype('<' + COMPONENT[acc['componentType']])
        data = np.frombuffer(self.bin, dtype=dtype, count=n, offset=start)
        return data.reshape(acc['count'], COUNT[acc['type']]).astype(np.float64)

    def static_trs(self, index):
        n = self.nodes[index]
        return (np.array(n.get('translation', [0, 0, 0]), float),
                np.array(n.get('rotation', [0, 0, 0, 1]), float),
                np.array(n.get('scale', [1, 1, 1]), float))

    def channels(self, animation_name):
        """{node index: {'translation'|'rotation'|'scale': (times, values)}}"""
        anim = next(a for a in self.json['animations']
                    if a.get('name') == animation_name)
        out = {}
        for ch in anim['channels']:
            sampler = anim['samplers'][ch['sampler']]
            node = ch['target']['node']
            out.setdefault(node, {})[ch['target']['path']] = (
                self.accessor(sampler['input'])[:, 0],
                self.accessor(sampler['output']),
            )
        return out

    def duration(self, animation_name):
        anim = next(a for a in self.json['animations']
                    if a.get('name') == animation_name)
        return max(float(self.accessor(s['input'])[:, 0].max())
                   for s in anim['samplers'])


def sample_vec(track, t, fallback):
    if track is None:
        return fallback
    times, values = track
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = int(np.searchsorted(times, t)) - 1
    span = times[i + 1] - times[i]
    a = 0.0 if span <= 0 else (t - times[i]) / span
    return values[i] * (1 - a) + values[i + 1] * a


def sample_quat(track, t, fallback):
    """Shortest-arc slerp; glTF quaternions are (x, y, z, w)."""
    if track is None:
        return fallback
    times, values = track
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = int(np.searchsorted(times, t)) - 1
    span = times[i + 1] - times[i]
    a = 0.0 if span <= 0 else (t - times[i]) / span
    q0, q1 = values[i], values[i + 1]
    dot = float(np.dot(q0, q1))
    if dot < 0:
        q1, dot = -q1, -dot
    if dot > 0.9995:
        q = q0 * (1 - a) + q1 * a
    else:
        theta = np.arccos(np.clip(dot, -1, 1))
        s = np.sin(theta)
        q = q0 * (np.sin((1 - a) * theta) / s) + q1 * (np.sin(a * theta) / s)
    n = np.linalg.norm(q)
    return q / n if n else q


def pose(glb, channels, node, t):
    """Local translation, rotation (x,y,z,w) and scale of one node at time t."""
    st, sr, ss = glb.static_trs(node)
    tracks = channels.get(node, {})
    return (sample_vec(tracks.get('translation'), t, st),
            sample_quat(tracks.get('rotation'), t, sr),
            sample_vec(tracks.get('scale'), t, ss))
