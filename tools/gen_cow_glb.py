#!/usr/bin/env python3
"""
Generates assets/mobs/cow.glb - a blocky Minecraft-style Holstein cow with a skeleton and animations.

Run from anywhere:   python3 tools/gen_cow_glb.py      (needs numpy + Pillow)

Conventions (identical to tools/make_pig_glb.py / pig.glb, so Pig-style AI code works unchanged):
  - units: metres (1 px of the vanilla model = 1/16 block, then * SCALE), origin = centre between the
    hooves on the ground (feet at y = 0)
  - "forward" (head direction) = +Z, left/right = +-X, up = +Y; yaw = atan2(dir.x, dir.z)
  - bones: Root, Body, Head, LegFL, LegFR, LegBL, LegBR (Root is the only skeleton root, no wrappers),
    every vertex is rigidly bound to exactly one bone (weight 1)
  - animations: "Idle" (3 s head bob), "Walk" (1 s loop, diagonal leg pairs swing)
  - texture: embedded 64x64 PNG, material baseColorTexture, NEAREST sampler. V is standard glTF
    (top-down), the PNG is NOT flipped (the engine loads glTF images with flip_vertically=false).
"""
import json, math, struct, os, io
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, 'assets', 'mobs', 'cow.glb')
TEX_W, TEX_H = 64, 64
SCALE = 0.92                 # vanilla cow is ~1.4 tall/1.6 long incl. head; this gives ~1.3 at the back
PX = SCALE / 16.0

# ---------------------------------------------------------------------------------------------
# Geometry. Modelled in Minecraft model space (px; y DOWN, forward = -z, ground at y = 24), then
# converted: x_out = x, y_out = 24 - y, z_out = -z (180 deg rotation about X: not a mirror).
# ---------------------------------------------------------------------------------------------
def to_out(p):
    x, y, z = p
    return np.array([x, 24.0 - y, -z]) * PX

def rot_x(p, angle):
    x, y, z = p
    c, s = math.cos(angle), math.sin(angle)
    return np.array([x, y * c - z * s, y * s + z * c])

def box_faces(u0, v0, ox, oy, oz, w, h, d):
    """6 faces like vanilla ModelBox: (name, 4 corners, 4 uv px). Corner 0 = (umin,vmin), 1 = (umax,vmin), 3 = (umin,vmax)."""
    x0, x1, y0, y1, z0, z1 = ox, ox + w, oy, oy + h, oz, oz + d
    return [
        ('+x', [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
         [(u0 + d + w, v0 + d), (u0 + d + w + d, v0 + d), (u0 + d + w + d, v0 + d + h), (u0 + d + w, v0 + d + h)]),
        ('-x', [(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)],
         [(u0, v0 + d), (u0 + d, v0 + d), (u0 + d, v0 + d + h), (u0, v0 + d + h)]),
        ('top', [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
         [(u0 + d, v0), (u0 + d + w, v0), (u0 + d + w, v0 + d), (u0 + d, v0 + d)]),
        ('bottom', [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
         [(u0 + d + w, v0), (u0 + d + 2 * w, v0), (u0 + d + 2 * w, v0 + d), (u0 + d + w, v0 + d)]),
        ('front', [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
         [(u0 + d, v0 + d), (u0 + d + w, v0 + d), (u0 + d + w, v0 + d + h), (u0 + d, v0 + d + h)]),
        ('back', [(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)],
         [(u0 + d + w + d, v0 + d), (u0 + 2 * d + 2 * w, v0 + d), (u0 + 2 * d + 2 * w, v0 + d + h), (u0 + d + w + d, v0 + d + h)]),
    ]

WHITE = (238, 238, 236, 255)
BLACK = (34, 32, 34, 255)
PINK = (236, 160, 160, 255)
PINK_DARK = (150, 84, 94, 255)
HOOF = (58, 50, 46, 255)
TAN = (216, 190, 140, 255)
EYE = (20, 16, 18, 255)

def hash01(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h &= 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFF) / 65535.0

def holstein(w, seed, cell=4.0, thresh=0.58):
    """Blocky patches that are a function of the 3D surface point -> continuous across box edges."""
    ix, iy, iz = (int(math.floor(c / cell)) for c in w)
    return BLACK if hash01(ix, iy, iz, seed) > thresh else WHITE

# Each part: name, bone, (u0, v0), (ox,oy,oz,w,h,d), transform (local mc -> model mc), color_fn(q_local, w_model)
BODY_PIVOT = np.array([0.0, 5.0, 2.0])
HEAD_PIVOT = np.array([0.0, 4.0, -8.0])
LEG_PIVOTS = {'LegFL': (4, 12, -6), 'LegFR': (-4, 12, -6), 'LegBL': (4, 12, 7), 'LegBR': (-4, 12, 7)}

def body_color(q, w):
    return holstein(w, 11)

def head_color(q, w):
    # eyes on both sides, near the front, just below the top
    if abs(abs(q[0]) - 4.0) < 0.01 and abs(q[2] - (-5.5)) < 0.01 and abs(q[1] - (-1.5)) < 0.01:
        return EYE
    return holstein(w, 23, thresh=0.62)

def snout_color(q, w):
    if abs(q[2] - (-8.0)) < 0.01 and abs(abs(q[0]) - 1.5) < 0.01 and abs(q[1] - 1.5) < 0.01:
        return PINK_DARK
    return PINK

def horn_color(q, w):
    return TAN

def tail_color(q, w):
    return BLACK if q[1] > 9.0 else WHITE

def udder_color(q, w):
    return PINK

def make_leg_color(seed):
    def f(q, w):
        if q[1] > 9.99:      # last 2 px of the 12 px leg = hoof
            return HOOF
        return holstein(w, seed, cell=3.0, thresh=0.6)
    return f

def parts():
    P = []
    P.append(('Body', 'Body', (18, 4), (-6, -10, -7, 12, 18, 10),
              lambda p: rot_x(p, math.pi / 2) + BODY_PIVOT, body_color))
    P.append(('Head', 'Head', (0, 0), (-4, -4, -6, 8, 8, 6), lambda p: p + HEAD_PIVOT, head_color))
    P.append(('Snout', 'Head', (0, 32), (-3, 0, -8, 6, 3, 2), lambda p: p + HEAD_PIVOT, snout_color))
    P.append(('HornL', 'Head', (0, 40), (3, -6, -4, 2, 3, 2), lambda p: p + HEAD_PIVOT, horn_color))
    P.append(('HornR', 'Head', (0, 40), (-5, -6, -4, 2, 3, 2), lambda p: p + HEAD_PIVOT, horn_color))
    for i, (bone, piv) in enumerate(LEG_PIVOTS.items()):
        pv = np.array(piv, dtype=float)
        P.append((bone, bone, (0, 16), (-2, 0, -2, 4, 12, 4), lambda p, pv=pv: p + pv, make_leg_color(31 + i)))
    # short tail hanging from the rump (x centred, rear end of the body is z = +10)
    P.append(('Tail', 'Body', (16, 40), (-1, 3, 10, 2, 9, 2), lambda p: p, tail_color))
    # small udder under the belly, rear half (belly is y = 12)
    P.append(('Udder', 'Body', (24, 52), (-2, 12, 3, 4, 2, 5), lambda p: p, udder_color))
    return P

BONES = [
    ('Root', -1, (0, 24, 0)),
    ('Body', 0, (0, 17, 2)),
    ('Head', 0, (0, 4, -8)),
    ('LegFL', 0, LEG_PIVOTS['LegFL']),
    ('LegFR', 0, LEG_PIVOTS['LegFR']),
    ('LegBL', 0, LEG_PIVOTS['LegBL']),
    ('LegBR', 0, LEG_PIVOTS['LegBR']),
]
BONE_INDEX = {b[0]: i for i, b in enumerate(BONES)}
PIVOT_OUT = [to_out(np.array(b[2], dtype=float)) for b in BONES]


def build_mesh_and_texture():
    pos, nrm, uv, joint, idx = [], [], [], [], []
    img = Image.new('RGBA', (TEX_W, TEX_H), (255, 0, 255, 255))   # unused texels = magenta (debug)
    px = img.load()
    for name, bone, (u0, v0), (ox, oy, oz, w, h, d), tf, color_fn in parts():
        center_out = to_out((tf(np.array([ox, oy, oz], float)) + tf(np.array([ox + w, oy + h, oz + d], float))) / 2.0)
        for fname, corners, uvs in box_faces(u0, v0, ox, oy, oz, w, h, d):
            q = [np.array(c, float) for c in corners]          # box-local mc
            m = [tf(c) for c in q]                              # model mc
            # ---- paint texels of this face ----
            umin, umax = min(a for a, _ in uvs), max(a for a, _ in uvs)
            vmin, vmax = min(b for _, b in uvs), max(b for _, b in uvs)
            fw, fh = umax - umin, vmax - vmin
            for j in range(fh):
                for i in range(fw):
                    s, t = (i + 0.5) / fw, (j + 0.5) / fh
                    ql = q[0] + s * (q[1] - q[0]) + t * (q[3] - q[0])
                    wm = m[0] + s * (m[1] - m[0]) + t * (m[3] - m[0])
                    px[umin + i, vmin + j] = color_fn(ql, wm)
            # ---- geometry ----
            out = [to_out(p) for p in m]
            n = np.cross(out[1] - out[0], out[3] - out[0])
            if np.dot(n, sum(out) / 4.0 - center_out) < 0:      # make sure winding faces outward
                out = [out[0], out[3], out[2], out[1]]
                uvs = [uvs[0], uvs[3], uvs[2], uvs[1]]
                n = np.cross(out[1] - out[0], out[3] - out[0])
            n = n / np.linalg.norm(n)
            base = len(pos)
            for p, (u, v) in zip(out, uvs):
                pos.append(p); nrm.append(n)
                uv.append((u / TEX_W, v / TEX_H))               # standard glTF V (top-down), PNG not flipped
                joint.append(BONE_INDEX[bone])
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    buf = io.BytesIO(); img.save(buf, 'PNG')
    return pos, nrm, uv, joint, idx, buf.getvalue(), img


# ---------------------------------------------------------------------------------------------
# Animations: {name: (duration, {bone: {'rotation'/'translation': [(t, value), ...]}})}
# Rotation = X euler in degrees (positive = leg/nose swings forward-down, same sign as the pig).
# First and last key equal -> seamless loop. Translations are offsets from the rest pose, in metres.
# ---------------------------------------------------------------------------------------------
def qx(deg):
    a = math.radians(deg) / 2.0
    return (math.sin(a), 0.0, 0.0, math.cos(a))          # glTF order: x, y, z, w

def anim_idle():
    d = 3.0
    return d, {
        'Head': {'rotation': [(0, qx(0)), (d / 2, qx(5)), (d, qx(0))]},
        'Body': {'translation': [(0, (0, 0, 0)), (d / 2, (0, 0.006, 0)), (d, (0, 0, 0))]},
    }

def anim_walk():
    d, amp = 1.0, 30.0
    t = [0, d / 4, d / 2, 3 * d / 4, d]
    a = [(t[0], qx(amp)), (t[1], qx(0)), (t[2], qx(-amp)), (t[3], qx(0)), (t[4], qx(amp))]
    b = [(t[0], qx(-amp)), (t[1], qx(0)), (t[2], qx(amp)), (t[3], qx(0)), (t[4], qx(-amp))]
    bob = [(0, (0, 0.0, 0)), (d / 4, (0, 0.02, 0)), (d / 2, (0, 0.0, 0)), (3 * d / 4, (0, 0.02, 0)), (d, (0, 0.0, 0))]
    return d, {
        'LegFL': {'rotation': a}, 'LegBR': {'rotation': a},
        'LegFR': {'rotation': b}, 'LegBL': {'rotation': b},
        'Body': {'translation': bob},
        'Head': {'rotation': [(0, qx(3)), (d / 2, qx(-3)), (d, qx(3))]},
    }

ANIMATIONS = {'Idle': anim_idle(), 'Walk': anim_walk()}

# ---------------------------------------------------------------------------------------------
# GLB packing
# ---------------------------------------------------------------------------------------------
class Buf:
    def __init__(self): self.data = bytearray(); self.views = []; self.accessors = []
    def add_view(self, raw, target=None):
        while len(self.data) % 4: self.data.append(0)
        view = {'buffer': 0, 'byteOffset': len(self.data), 'byteLength': len(raw)}
        if target: view['target'] = target
        self.data += raw; self.views.append(view); return len(self.views) - 1
    def add_accessor(self, arr, ctype, atype, target=None, minmax=False):
        v = self.add_view(np.ascontiguousarray(arr).tobytes(), target)
        acc = {'bufferView': v, 'componentType': ctype, 'count': int(arr.shape[0]), 'type': atype}
        if minmax:
            acc['min'] = [float(x) for x in np.min(arr, axis=0)]; acc['max'] = [float(x) for x in np.max(arr, axis=0)]
        self.accessors.append(acc); return len(self.accessors) - 1

def build():
    pos, nrm, uv, joint, idx, png, _ = build_mesh_and_texture()
    P = np.array(pos, dtype=np.float32); N = np.array(nrm, dtype=np.float32); U = np.array(uv, dtype=np.float32)
    J = np.zeros((len(joint), 4), dtype=np.uint16); J[:, 0] = joint
    W = np.zeros((len(joint), 4), dtype=np.float32); W[:, 0] = 1.0
    I = np.array(idx, dtype=np.uint16)

    buf = Buf()
    a_pos = buf.add_accessor(P, 5126, 'VEC3', 34962, minmax=True)
    a_nrm = buf.add_accessor(N, 5126, 'VEC3', 34962)
    a_uv = buf.add_accessor(U, 5126, 'VEC2', 34962)
    a_j = buf.add_accessor(J, 5123, 'VEC4', 34962)
    a_w = buf.add_accessor(W, 5126, 'VEC4', 34962)
    a_i = buf.add_accessor(I, 5123, 'SCALAR', 34963)

    # inverse bind matrices = translate(-world pivot), column-major
    ibm = np.zeros((len(BONES), 4, 4), dtype=np.float32)
    for i, piv in enumerate(PIVOT_OUT):
        m = np.eye(4, dtype=np.float32); m[:3, 3] = -piv; ibm[i] = m.T
    a_ibm = buf.add_accessor(ibm.reshape(len(BONES), 16), 5126, 'MAT4')

    # nodes: 0 = skinned mesh, 1.. = bones (skeleton root = node 1)
    nodes = [{'name': 'Cow', 'mesh': 0, 'skin': 0}]
    for i, (name, parent, _) in enumerate(BONES):
        rest = PIVOT_OUT[i] - (PIVOT_OUT[parent] if parent >= 0 else 0)
        nodes.append({'name': name, 'translation': [float(x) for x in rest]})
    for i, (name, parent, _) in enumerate(BONES):
        if parent >= 0:
            nodes[1 + parent].setdefault('children', []).append(1 + i)
    joints = [1 + i for i in range(len(BONES))]

    animations = []
    for name, (dur, tracks) in ANIMATIONS.items():
        samplers, channels = [], []
        for bone, paths in tracks.items():
            bi = BONE_INDEX[bone]
            rest = PIVOT_OUT[bi] - (PIVOT_OUT[BONES[bi][1]] if BONES[bi][1] >= 0 else 0)
            for path, keys in paths.items():
                times = np.array([k[0] for k in keys], dtype=np.float32)
                if path == 'rotation':
                    vals = np.array([k[1] for k in keys], dtype=np.float32); atype = 'VEC4'
                else:
                    vals = np.array([rest + np.array(k[1]) for k in keys], dtype=np.float32); atype = 'VEC3'
                t_acc = buf.add_accessor(times.reshape(-1, 1), 5126, 'SCALAR', minmax=True)
                v_acc = buf.add_accessor(vals, 5126, atype)
                samplers.append({'input': t_acc, 'output': v_acc, 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': 1 + bi, 'path': path}})
        animations.append({'name': name, 'samplers': samplers, 'channels': channels})

    img_view = buf.add_view(png)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'OptiCraft tools/gen_cow_glb.py'},
        'scene': 0, 'scenes': [{'nodes': [0, 1]}],
        'nodes': nodes,
        'meshes': [{'name': 'Cow', 'primitives': [{'attributes': {'POSITION': a_pos, 'NORMAL': a_nrm, 'TEXCOORD_0': a_uv,
                                                                   'JOINTS_0': a_j, 'WEIGHTS_0': a_w}, 'indices': a_i, 'material': 0, 'mode': 4}]}],
        'skins': [{'joints': joints, 'skeleton': 1, 'inverseBindMatrices': a_ibm}],
        'materials': [{'name': 'M_Cow', 'doubleSided': True,
                       'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0}}],
        'textures': [{'sampler': 0, 'source': 0}],
        'samplers': [{'magFilter': 9728, 'minFilter': 9728, 'wrapS': 10497, 'wrapT': 10497}],
        'images': [{'name': 'cow_albedo', 'bufferView': img_view, 'mimeType': 'image/png'}],
        'animations': animations,
        'accessors': buf.accessors, 'bufferViews': buf.views,
        'buffers': [{'byteLength': len(buf.data)}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    binb = bytes(buf.data)
    while len(binb) % 4: binb += b'\0'
    total = 12 + 8 + len(js) + 8 + len(binb)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, total))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(binb), b'BIN\0')); f.write(binb)
    print(f'{OUT_PATH}: {len(P)} verts, {len(I)//3} tris, {len(BONES)} bones, animations: {", ".join(ANIMATIONS)}; {total} bytes')
    print('bounds (m): min', P.min(0).round(3), 'max', P.max(0).round(3))

if __name__ == '__main__':
    build()
