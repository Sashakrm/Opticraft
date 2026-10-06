#!/usr/bin/env python3
"""
Собирает assets/mobs/pig.glb — свинья в стиле Minecraft со скелетом и анимациями.

Запуск из корня проекта:   python3 tools/make_pig_glb.py      (нужен только numpy)

Почему генератор, а не правка старого файла: исходный minecraft_pig.glb (Sketchfab, FBX->glTF) был
внутренне противоречив — вершины разных частей лежали в разных единицах, а inverseBindMatrices не
совпадали с костями (загрузчик ругался «bind-pose sanity check»), из-за чего свинья рисовалась
огромным боксом без ног. Здесь модель собрана заново: те же размеры, что у ванильной свиньи
(1 пиксель = 1/16 блока), метры, начало координат — центр между копытами на земле, «вперёд» = +Z
(так её поворачивает Pig.cpp), каждая часть тела жёстко привязана к своей кости.

Текстура — assets/mobs/pig.png (64x32, раскладка ванильной свиньи, перевёрнутая по вертикали —
ровно как была вшита в исходный файл).
Автор исходной модели/текстуры: None_Yaroslav (Sketchfab), CC-BY-4.0:
https://sketchfab.com/3d-models/minecraft-pig-1c0aa700b8a94af6ae2c62b36eed190b
"""
import json, math, struct, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_PATH = os.path.join(ROOT, 'assets', 'mobs', 'pig.png')
OUT_PATH = os.path.join(ROOT, 'assets', 'mobs', 'pig.glb')
TEX_W, TEX_H = 64, 32
PX = 1.0 / 16.0

# ----------------------------------------------------------------------------------------------
# Геометрия. Считаем в «модельных» координатах Minecraft (x, y вниз, z вперёд = -z), потом
# переводим в наши: x_out = x, y_out = 24 - y, z_out = -z (поворот на 180° вокруг X — не зеркало,
# порядок вершин не переворачивается), умножаем на PX -> метры.
# ----------------------------------------------------------------------------------------------
def to_out(p):
    x, y, z = p
    return np.array([x, 24.0 - y, -z]) * PX

def rot_x(p, angle):
    x, y, z = p
    c, s = math.cos(angle), math.sin(angle)
    return np.array([x, y * c - z * s, y * s + z * c])

def box_faces(u0, v0, ox, oy, oz, w, h, d, skip=()):
    """6 граней бокса как ванильный ModelBox: [(4 угла (x,y,z), 4 uv в пикселях, имя)]."""
    x0, x1, y0, y1, z0, z1 = ox, ox + w, oy, oy + h, oz, oz + d
    faces = []
    # +x: u растёт с +z
    faces.append(('+x', [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
                  [(u0 + d + w, v0 + d), (u0 + d + w + d, v0 + d), (u0 + d + w + d, v0 + d + h), (u0 + d + w, v0 + d + h)]))
    # -x: u растёт с -z
    faces.append(('-x', [(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)],
                  [(u0, v0 + d), (u0 + d, v0 + d), (u0 + d, v0 + d + h), (u0, v0 + d + h)]))
    # верх (y min): u растёт с +x, v растёт к -z
    faces.append(('top', [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
                  [(u0 + d, v0), (u0 + d + w, v0), (u0 + d + w, v0 + d), (u0 + d, v0 + d)]))
    # низ (y max): u растёт с +x, v растёт к +z
    faces.append(('bottom', [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                  [(u0 + d + w, v0), (u0 + d + 2 * w, v0), (u0 + d + 2 * w, v0 + d), (u0 + d + w, v0 + d)]))
    # перед (z min): u растёт с +x
    faces.append(('front', [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                  [(u0 + d, v0 + d), (u0 + d + w, v0 + d), (u0 + d + w, v0 + d + h), (u0 + d, v0 + d + h)]))
    # зад (z max): u растёт с -x
    faces.append(('back', [(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)],
                  [(u0 + d + w + d, v0 + d), (u0 + 2 * d + 2 * w, v0 + d), (u0 + 2 * d + 2 * w, v0 + d + h), (u0 + d + w + d, v0 + d + h)]))
    return [f for f in faces if f[0] not in skip]

class Mesh:
    def __init__(self):
        self.pos, self.nrm, self.uv, self.joint, self.idx = [], [], [], [], []

    def add_face(self, corners_out, uvs_px, joint):
        c = [np.array(p) for p in corners_out]
        n = np.cross(c[1] - c[0], c[3] - c[0])
        n = n / np.linalg.norm(n)
        base = len(self.pos)
        for p, (u, v) in zip(c, uvs_px):
            self.pos.append(p); self.nrm.append(n)
            # Текстура в файле перевёрнута по вертикали относительно ванильной: v_gltf = 1 - v/H
            self.uv.append((u / TEX_W, 1.0 - v / TEX_H)); self.joint.append(joint)
        self.idx += [base, base + 1, base + 2, base, base + 2, base + 3]

def outward_check(face_corners_out, center_out):
    c = [np.array(p) for p in face_corners_out]
    n = np.cross(c[1] - c[0], c[3] - c[0])
    fc = sum(c) / 4.0
    return np.dot(n, fc - center_out) > 0

def add_box(mesh, joint, u0, v0, box, transform, skip=()):
    ox, oy, oz, w, h, d = box
    pts = [transform(np.array(p, dtype=float)) for p in
           [(ox, oy, oz), (ox + w, oy + h, oz + d)]]
    center_mc = (pts[0] + pts[1]) / 2.0
    center_out = to_out(center_mc)
    for name, corners, uvs in box_faces(u0, v0, ox, oy, oz, w, h, d, skip):
        out = [to_out(transform(np.array(p, dtype=float))) for p in corners]
        if not outward_check(out, center_out):
            # Поворот вокруг X у тела (+90°) не зеркалит, но на всякий случай гарантируем вид снаружи.
            out = [out[0], out[3], out[2], out[1]]
            uvs = [uvs[0], uvs[3], uvs[2], uvs[1]]
        mesh.add_face(out, uvs, joint)

# Кости: (имя, родитель, позиция точки вращения в модельных px MC)
BONES = [
    ('Root',  -1, (0, 24, 0)),      # на земле между копытами (y_mc = 24 -> y_out = 0)
    ('Body',   0, (0, 11, 2)),
    ('Head',   0, (0, 12, -6)),
    ('LegFL',  0, (3, 18, -5)),
    ('LegFR',  0, (-3, 18, -5)),
    ('LegBL',  0, (3, 18, 7)),
    ('LegBR',  0, (-3, 18, 7)),
]
BONE_INDEX = {b[0]: i for i, b in enumerate(BONES)}
PIVOT_OUT = [to_out(np.array(b[2], dtype=float)) for b in BONES]

def build_mesh():
    m = Mesh()
    # Тело: бокс (-5,-10,-7, 10x16x8), поворот +90° вокруг X, точка (0,11,2). UV (28,8).
    body_pivot = np.array([0.0, 11.0, 2.0])
    add_box(m, BONE_INDEX['Body'], 28, 8, (-5, -10, -7, 10, 16, 8),
            lambda p: rot_x(p, math.pi / 2) + body_pivot)
    # Голова: бокс (-4,-4,-8, 8x8x8) в (0,12,-6). UV (0,0).
    head_pivot = np.array([0.0, 12.0, -6.0])
    add_box(m, BONE_INDEX['Head'], 0, 0, (-4, -4, -8, 8, 8, 8), lambda p: p + head_pivot)
    # Пятачок: бокс (-2,0,-9, 4x3x1) в системе головы. UV (16,16). Задняя грань спрятана в голове.
    add_box(m, BONE_INDEX['Head'], 16, 16, (-2, 0, -9, 4, 3, 1), lambda p: p + head_pivot, skip=('back',))
    # Ноги: бокс (-2,0,-2, 4x6x4), UV (0,16).
    for name, piv in (('LegFL', (3, 18, -5)), ('LegFR', (-3, 18, -5)), ('LegBL', (3, 18, 7)), ('LegBR', (-3, 18, 7))):
        pv = np.array(piv, dtype=float)
        add_box(m, BONE_INDEX[name], 0, 16, (-2, 0, -2, 4, 6, 4), lambda p, pv=pv: p + pv)
    return m

# ----------------------------------------------------------------------------------------------
# Анимации: {имя: (длительность, {кость: {'rotation'/'translation': [(t, value), ...]}})}
# Вращение — эйлер X в градусах (положительный = вперёд-вниз: нос/лапа уходят вниз), смещения — метры.
# Ключи в t=0 и t=duration одинаковы -> клип зацикливается без скачка.
# ----------------------------------------------------------------------------------------------
def qx(deg):
    a = math.radians(deg) / 2.0
    return (math.sin(a), 0.0, 0.0, math.cos(a))          # glTF: x, y, z, w

def qxz(deg_x, deg_z):
    ax, az = math.radians(deg_x) / 2.0, math.radians(deg_z) / 2.0
    qx_ = (math.sin(ax), 0, 0, math.cos(ax)); qz_ = (0, 0, math.sin(az), math.cos(az))
    x1, y1, z1, w1 = qx_; x2, y2, z2, w2 = qz_          # q = qx * qz
    return (w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2)

def anim_idle():
    d = 3.0
    return d, {
        'Head': {'rotation': [(0, qx(0)), (d / 2, qx(4)), (d, qx(0))]},
        'Body': {'translation': [(0, (0, 0, 0)), (d / 2, (0, 0.006, 0)), (d, (0, 0, 0))]},
    }

def anim_walk():
    d, amp = 0.7, 32.0
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

def anim_eat():
    # Голова опущена к земле, три «клевка» рылом.
    d = 1.8
    down, up = 58.0, 46.0
    return d, {
        'Head': {'rotation': [(0, qx(0)), (0.25, qx(down)), (0.55, qx(up)), (0.8, qx(down)), (1.05, qx(up)),
                              (1.3, qx(down)), (1.55, qx(down - 10)), (d, qx(0))]},
        'Body': {'translation': [(0, (0, 0, 0)), (0.25, (0, -0.01, 0)), (1.55, (0, -0.01, 0)), (d, (0, 0, 0))]},
    }

def anim_sleep():
    # Лежит на брюхе: тело опущено до земли, ноги вытянуты горизонтально, голова на земле.
    d = 4.0
    drop = -0.30
    def pose(dy):
        return (0, dy, 0)
    return d, {
        'Body': {'translation': [(0, pose(drop)), (d / 2, pose(drop + 0.008)), (d, pose(drop))]},
        'Head': {'translation': [(0, (0, drop, 0)), (d, (0, drop, 0))],
                 'rotation': [(0, qx(22)), (d / 2, qx(25)), (d, qx(22))]},
        'LegFL': {'translation': [(0, (0, drop, 0)), (d, (0, drop, 0))], 'rotation': [(0, qx(-88)), (d, qx(-88))]},
        'LegFR': {'translation': [(0, (0, drop, 0)), (d, (0, drop, 0))], 'rotation': [(0, qx(-88)), (d, qx(-88))]},
        'LegBL': {'translation': [(0, (0, drop, 0)), (d, (0, drop, 0))], 'rotation': [(0, qx(88)), (d, qx(88))]},
        'LegBR': {'translation': [(0, (0, drop, 0)), (d, (0, drop, 0))], 'rotation': [(0, qx(88)), (d, qx(88))]},
    }

def anim_happy():
    # Подпрыгивает на месте и мотает головой.
    d = 0.9
    hop = [(0, (0, 0, 0)), (0.2, (0, 0.16, 0)), (0.4, (0, 0, 0)), (0.6, (0, 0.16, 0)), (0.8, (0, 0, 0)), (d, (0, 0, 0))]
    swing = [(0, qx(0)), (0.2, qx(-18)), (0.4, qx(0)), (0.6, qx(-18)), (0.8, qx(0)), (d, qx(0))]
    return d, {
        'Root': {'translation': hop},
        'Head': {'rotation': [(0, qxz(0, 0)), (0.2, qxz(0, 14)), (0.4, qxz(0, -14)), (0.6, qxz(0, 14)), (0.8, qxz(0, -14)), (d, qxz(0, 0))]},
        'LegFL': {'rotation': swing}, 'LegFR': {'rotation': swing},
    }

ANIMATIONS = {'Idle': anim_idle(), 'Walk': anim_walk(), 'Eat': anim_eat(), 'Sleep': anim_sleep(), 'Happy': anim_happy()}

# ----------------------------------------------------------------------------------------------
# Упаковка в GLB
# ----------------------------------------------------------------------------------------------
class Buf:
    def __init__(self): self.data = bytearray(); self.views = []; self.accessors = []
    def add_view(self, raw, target=None):
        while len(self.data) % 4: self.data.append(0)
        view = {'buffer': 0, 'byteOffset': len(self.data), 'byteLength': len(raw)}
        if target: view['target'] = target
        self.data += raw; self.views.append(view); return len(self.views) - 1
    def add_accessor(self, arr, ctype, atype, target=None, minmax=False):
        raw = np.ascontiguousarray(arr).tobytes()
        v = self.add_view(raw, target)
        acc = {'bufferView': v, 'componentType': ctype, 'count': int(arr.shape[0]), 'type': atype}
        if minmax:
            acc['min'] = [float(x) for x in np.min(arr, axis=0)]; acc['max'] = [float(x) for x in np.max(arr, axis=0)]
        self.accessors.append(acc); return len(self.accessors) - 1

def build():
    mesh = build_mesh()
    P = np.array(mesh.pos, dtype=np.float32); N = np.array(mesh.nrm, dtype=np.float32)
    U = np.array(mesh.uv, dtype=np.float32)
    J = np.zeros((len(mesh.joint), 4), dtype=np.uint16); J[:, 0] = mesh.joint
    W = np.zeros((len(mesh.joint), 4), dtype=np.float32); W[:, 0] = 1.0
    I = np.array(mesh.idx, dtype=np.uint16)

    buf = Buf()
    a_pos = buf.add_accessor(P, 5126, 'VEC3', 34962, minmax=True)
    a_nrm = buf.add_accessor(N, 5126, 'VEC3', 34962)
    a_uv = buf.add_accessor(U, 5126, 'VEC2', 34962)
    a_j = buf.add_accessor(J, 5123, 'VEC4', 34962)
    a_w = buf.add_accessor(W, 5126, 'VEC4', 34962)
    a_i = buf.add_accessor(I, 5123, 'SCALAR', 34963)

    # Обратные bind-матрицы: у каждой кости — сдвиг на минус её мировую позицию (glTF: column-major).
    ibm = np.zeros((len(BONES), 4, 4), dtype=np.float32)
    for i, piv in enumerate(PIVOT_OUT):
        m = np.eye(4, dtype=np.float32); m[:3, 3] = -piv; ibm[i] = m.T
    a_ibm = buf.add_accessor(ibm.reshape(len(BONES), 16), 5126, 'MAT4')

    # Узлы: 0 — меш со скином, 1.. — кости. Корень скелета = узел 1.
    nodes = [{'name': 'Pig', 'mesh': 0, 'skin': 0}]
    for i, (name, parent, _) in enumerate(BONES):
        piv = PIVOT_OUT[i] - (PIVOT_OUT[parent] if parent >= 0 else 0)
        nodes.append({'name': name, 'translation': [float(x) for x in piv]})
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
                else:  # translation задаётся смещением ОТ позы покоя
                    vals = np.array([rest + np.array(k[1]) for k in keys], dtype=np.float32); atype = 'VEC3'
                t_acc = buf.add_accessor(times.reshape(-1, 1), 5126, 'SCALAR', minmax=True)
                v_acc = buf.add_accessor(vals, 5126, atype)
                samplers.append({'input': t_acc, 'output': v_acc, 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': 1 + bi, 'path': path}})
        animations.append({'name': name, 'samplers': samplers, 'channels': channels})

    png = open(TEX_PATH, 'rb').read()
    img_view = buf.add_view(png)

    gltf = {
        'asset': {'version': '2.0', 'generator': 'OptiCraft tools/make_pig_glb.py',
                  'extras': {'license': 'CC-BY-4.0 (texture)', 'author': 'None_Yaroslav (Sketchfab)',
                             'source': 'https://sketchfab.com/3d-models/minecraft-pig-1c0aa700b8a94af6ae2c62b36eed190b'}},
        'scene': 0, 'scenes': [{'nodes': [0, 1]}],
        'nodes': nodes,
        'meshes': [{'name': 'Pig', 'primitives': [{'attributes': {'POSITION': a_pos, 'NORMAL': a_nrm, 'TEXCOORD_0': a_uv,
                                                                   'JOINTS_0': a_j, 'WEIGHTS_0': a_w}, 'indices': a_i, 'material': 0, 'mode': 4}]}],
        'skins': [{'joints': joints, 'skeleton': 1, 'inverseBindMatrices': a_ibm}],
        'materials': [{'name': 'M_Pig', 'doubleSided': True,
                       'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0}}],
        'textures': [{'sampler': 0, 'source': 0}],
        'samplers': [{'magFilter': 9728, 'minFilter': 9728, 'wrapS': 10497, 'wrapT': 10497}],
        'images': [{'bufferView': img_view, 'mimeType': 'image/png'}],
        'animations': animations,
        'accessors': buf.accessors, 'bufferViews': buf.views,
        'buffers': [{'byteLength': len(buf.data)}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    binb = bytes(buf.data)
    while len(binb) % 4: binb += b'\0'
    total = 12 + 8 + len(js) + 8 + len(binb)
    with open(OUT_PATH, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, total))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(binb), b'BIN\0')); f.write(binb)
    print(f'{OUT_PATH}: {len(P)} вершин, {len(I)//3} треугольников, {len(BONES)} костей, анимации: {", ".join(ANIMATIONS)}; {total} байт')
    print('габариты (м): min', P.min(0).round(3), 'max', P.max(0).round(3))

if __name__ == '__main__':
    build()
