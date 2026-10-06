#!/usr/bin/env python3
"""Перерисовывает атлас OptiCraft: у каждого блока — своя подходящая текстура.
Запуск из корня проекта:  python3 tools/gen_atlas.py
Пишет assets/texture/texture_atlas.png и assets/atlases/blocks_main.atlas.json,
обновляет секции "texture" в assets/blocks.json.
"""
import json
import math
import os
import random
import re
import sys
from PIL import Image

S = 16
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."


# ----------------------------------------------------------------------------- утилиты
def hx(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def pal(*colors):
    return [hx(c) for c in colors]


def shade(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))), c[3])


def new():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def put(img, x, y, c):
    if 0 <= x < S and 0 <= y < S:
        img.putpixel((x, y), c)


def vnoise(seed, cells):
    """Тайлящийся value-noise: значение в (x, y) пикселях, оборачивается по краям."""
    r = random.Random(seed)
    g = [[r.random() for _ in range(cells)] for _ in range(cells)]

    def f(x, y):
        fx = x / S * cells
        fy = y / S * cells
        x0, y0 = int(fx) % cells, int(fy) % cells
        x1, y1 = (x0 + 1) % cells, (y0 + 1) % cells
        tx, ty = fx - int(fx), fy - int(fy)
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = g[y0][x0] * (1 - tx) + g[y0][x1] * tx
        b = g[y1][x0] * (1 - tx) + g[y1][x1] * tx
        return a * (1 - ty) + b * ty
    return f


def blotchy(palette, seed, cells=4, jitter=0.4):
    img = new()
    n = vnoise(seed, cells)
    r = random.Random(seed * 7 + 1)
    for y in range(S):
        for x in range(S):
            v = (n(x, y) - 0.2) / 0.6
            v = v * (1 - jitter) + r.random() * jitter
            v = max(0.0, min(0.999, v))
            img.putpixel((x, y), palette[int(v * len(palette))])
    return img


def speckle(img, seed, color, count, only_opaque=True):
    r = random.Random(seed)
    for _ in range(count):
        x, y = r.randrange(S), r.randrange(S)
        if not only_opaque or img.getpixel((x, y))[3] > 0:
            img.putpixel((x, y), color)


def border(img, color, inset=0):
    for i in range(inset, S - inset):
        for (x, y) in ((i, inset), (i, S - 1 - inset), (inset, i), (S - 1 - inset, i)):
            img.putpixel((x, y), color)


def grain(palette, seed, cluster=0.38, weights=None):
    """Зерно как в Minecraft: попиксельный случайный выбор из близких тонов, но часть пикселей
    копирует соседа слева/сверху — получаются мелкие кластеры, а не "шум телевизора"."""
    img = new()
    r = random.Random(seed)
    idx = [[0] * S for _ in range(S)]
    for y in range(S):
        for x in range(S):
            p = r.random()
            if p < cluster and x > 0:
                i = idx[y][x - 1]
            elif p < cluster * 2 and y > 0:
                i = idx[y - 1][x]
            elif weights:
                i = r.choices(range(len(palette)), weights)[0]
            else:
                i = r.randrange(len(palette))
            idx[y][x] = i
            img.putpixel((x, y), palette[i])
    return img


def cobble(seed, light="#8a8a8a", mid="#787878", dark="#5c5c5c", edge="#4a4a4a", cells=9):
    r = random.Random(seed)
    sites = [(r.uniform(0, S), r.uniform(0, S)) for _ in range(cells)]
    tone = [shade(hx(mid), r.uniform(0.9, 1.12)) for _ in sites]
    img = new()
    for y in range(S):
        for x in range(S):
            best, second, bi = 1e9, 1e9, 0
            for i, (sx, sy) in enumerate(sites):
                for ox in (-S, 0, S):
                    for oy in (-S, 0, S):
                        d = math.hypot(x - sx - ox, y - sy - oy)
                        if d < best:
                            second, best, bi = best, d, i
                        elif d < second:
                            second = d
            if second - best < 1.1:
                c = hx(edge)
            else:
                c = tone[bi]
                if r.random() < 0.25:
                    c = shade(c, r.choice((0.9, 1.1)))
                if y < 3 and r.random() < 0.3:
                    c = hx(light)
            img.putpixel((x, y), c)
    return img


# ----------------------------------------------------------------------------- камень и земля
def stone(seed=11, colors=None, cracks=True):
    colors = colors or pal("#7d7d7d", "#858585", "#767676", "#8f8f8f", "#6e6e6e")
    img = grain(colors, seed, 0.42, [3, 3, 3, 2, 2])
    if cracks:
        r = random.Random(seed + 5)
        dark = shade(colors[-1], 0.85)
        for _ in range(4):
            x, y = r.randrange(1, 15), r.randrange(1, 15)
            for _ in range(2):
                img.putpixel((x % S, y % S), dark)
                x += r.choice((-1, 1))
    return img


def dirt():
    img = grain(pal("#866043", "#79553a", "#6b4a31", "#94704e", "#5c3f29"), 21, 0.4)
    speckle(img, 22, hx("#a39c93"), 3)
    speckle(img, 23, hx("#4a331f"), 5)
    return img


def grass_top():
    return grain(pal("#5da13b", "#68ad44", "#559632", "#74b84d", "#4c8a2c"), 31, 0.42)


def grass_side():
    img = dirt()
    r = random.Random(33)
    g = pal("#5da13b", "#68ad44", "#559632", "#74b84d")
    for x in range(S):
        depth = 2 + (1 if r.random() < 0.55 else 0) + (1 if r.random() < 0.25 else 0)
        for y in range(depth):
            c = r.choice(g)
            if y == depth - 1 and depth > 2:
                c = shade(c, 0.86)
            img.putpixel((x, y), c)
    return img


def sand():
    img = grain(pal("#dbd3a0", "#e4dcae", "#d2c994", "#ebe4b9", "#cfc58c"), 41, 0.4)
    speckle(img, 42, hx("#bfb47c"), 4)
    return img


def red_sand():
    img = grain(pal("#b5532a", "#c0602f", "#a84a24", "#c96c38", "#9d4220"), 43, 0.4)
    speckle(img, 44, hx("#8a3a1c"), 4)
    return img


def gravel():
    img = grain(pal("#8b8784", "#999491", "#7c7875", "#a6a19d", "#6f6b69"), 45, 0.35)
    r = random.Random(46)
    for _ in range(9):  # отдельные камешки: тёмный пиксель + светлый блик рядом
        x, y = r.randrange(1, S - 1), r.randrange(1, S - 1)
        img.putpixel((x, y), hx("#5e5a58"))
        img.putpixel((x + 1, y), hx("#b9b4b0"))
    return img


def snow_block():
    img = grain(pal("#f6f9fc", "#eef3f8", "#e4ecf4", "#fbfdff"), 47, 0.45, [4, 3, 2, 3])
    speckle(img, 48, hx("#cfdceb"), 5)
    return img


def mud():
    img = grain(pal("#3b2c22", "#463427", "#4f3b2c", "#33261d"), 51, 0.4)
    speckle(img, 52, hx("#6f5a47"), 5)
    return img


def mossy_stone():
    img = stone(61, cracks=False)
    n = vnoise(62, 4)
    r = random.Random(63)
    greens = pal("#3f7a2a", "#4f8e35", "#5f9e42", "#2f6421")
    for y in range(S):
        for x in range(S):
            if n(x, y) > 0.56:
                img.putpixel((x, y), r.choice(greens))
    return img


def deep_stone():
    img = blotchy(pal("#2e3038", "#383a44", "#42444f", "#262830", "#4a4c58"), 71, 4, 0.5)
    speckle(img, 72, hx("#1a1b20"), 6)
    return img


def lava_stone():
    img = blotchy(pal("#2b2222", "#352a29", "#3f3231", "#231b1b"), 81, 4, 0.5)
    r = random.Random(82)
    for _ in range(3):
        x, y = r.randrange(S), r.randrange(S)
        for _ in range(r.randrange(7, 12)):
            for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                px, py = (x + dx) % S, (y + dy) % S
                if img.getpixel((px, py))[0] < 120:
                    img.putpixel((px, py), hx("#8a2c10"))
            img.putpixel((x % S, y % S), r.choice(pal("#ff7a1a", "#ff9a26", "#ffb02e")))
            x += r.choice((-1, 0, 1, 1))
            y += r.choice((-1, 0, 1))
    return img


def wet_stone():
    img = blotchy(pal("#4a5560", "#55616d", "#5f6c79", "#414b55"), 91, 4, 0.5)
    n = vnoise(92, 3)
    for y in range(S):
        for x in range(S):
            if n(x, y) > 0.6:
                img.putpixel((x, y), hx("#38424b"))
    speckle(img, 93, hx("#8fb4c9"), 6)
    speckle(img, 94, hx("#b9dcec"), 2)
    return img


def cloud_stone():
    img = blotchy(pal("#f4f8ff", "#e6eefb", "#d5e2f6", "#ffffff", "#c8d8f0"), 101, 3, 0.3)
    speckle(img, 102, hx("#bfb6ea"), 4)
    return img


def ice():
    img = grain(pal("#96bdf5", "#a4c8fa", "#8db4ee", "#b3d3fc"), 111, 0.5)
    r = random.Random(112)
    for y in range(S):
        for x in range(S):
            if (x + y) % 8 == 0 and r.random() < 0.7:
                img.putpixel((x, y), hx("#d8ebff"))
    return img


def slime_block():
    img = new()
    for y in range(S):
        for x in range(S):
            d = min(x, y, S - 1 - x, S - 1 - y)
            c = hx("#3a8f2a") if d == 0 else hx("#5cc040") if d == 1 else hx("#7bde52")
            img.putpixel((x, y), c)
    speckle(img, 121, hx("#a6f57f"), 8)
    for (x, y) in ((4, 4), (5, 4), (4, 5)):
        img.putpixel((x, y), hx("#dfffc9"))
    return img


def sun_stone():
    img = blotchy(pal("#f5c33b", "#f8d052", "#fbdc6b", "#f0b02a"), 131, 3, 0.3)
    for y in range(S):
        for x in range(S):
            dx, dy = x - 7.5, y - 7.5
            d = max(abs(dx), abs(dy))
            eu = math.hypot(dx, dy)
            if eu < 2.6:
                img.putpixel((x, y), hx("#fff6c2"))
            elif eu < 3.8:
                img.putpixel((x, y), hx("#ffe680"))
            elif (abs(abs(dx) - abs(dy)) < 0.6 or min(abs(dx), abs(dy)) < 0.6) and eu < 7:
                img.putpixel((x, y), hx("#ffe98a"))
            if d >= 7:
                img.putpixel((x, y), hx("#d99a1e"))
    return img


def water():
    img = grain(pal("#2d4ee0", "#3358ea", "#2946d6", "#3a63f0"), 141, 0.5)
    r = random.Random(142)
    for _ in range(4):
        x, y = r.randrange(S), r.randrange(S)
        img.putpixel((x, y), hx("#6f8cff"))
        img.putpixel(((x + 1) % S, y), hx("#6f8cff"))
    return img


def ore(seed, ore_colors, count=5):
    img = stone(seed, cracks=False)
    r = random.Random(seed + 200)
    for _ in range(count):
        cx, cy = r.randrange(2, 14), r.randrange(2, 14)
        cells = [(0, 0)]
        for _ in range(r.randrange(2, 4)):
            dx, dy = r.choice((1, -1, 0, 0)), r.choice((0, 0, 1, -1))
            cells.append((cells[-1][0] + dx, cells[-1][1] + dy))
        for (dx, dy) in cells:
            x, y = cx + dx, cy + dy
            if 0 <= x < S and 0 <= y < S:
                img.putpixel((x, y), r.choice(ore_colors))
    return img


# ----------------------------------------------------------------------------- дерево
def log_side(bark, groove, seed, drips=None):
    img = new()
    r = random.Random(seed)
    x = 0
    strips = []
    while x < S:
        w = r.choice((2, 3, 3))
        strips.append((x, min(S, x + w), r.choice(bark)))
        x += w
    for (x0, x1, tone) in strips:
        for x in range(x0, x1):
            for y in range(S):
                c = tone
                if r.random() < 0.2:
                    c = shade(tone, r.choice((0.88, 1.12)))
                if x == x0:
                    c = groove
                img.putpixel((x, y), c)
    for _ in range(6):
        put(img, r.randrange(S), r.randrange(S), shade(bark[0], 1.25))
    if drips:
        for _ in range(3):
            x, y0 = r.randrange(S), r.randrange(0, 6)
            for k in range(r.randrange(3, 7)):
                put(img, x, y0 + k, r.choice(drips))
    return img


def birch_side(seed=181):
    img = log_side(pal("#e8e6dc", "#f2f0e8", "#d9d6ca"), hx("#c4c1b4"), seed)
    r = random.Random(seed + 1)
    for _ in range(6):  # характерные тёмные пятна коры
        x, y = r.randrange(1, 15), r.randrange(1, 15)
        for k in range(r.choice((1, 2, 2, 3))):
            put(img, x + k, y, hx("#2b2b2b"))
    return img


def log_top(bark, rings, seed):
    img = new()
    r = random.Random(seed)
    for y in range(S):
        for x in range(S):
            d = max(abs(x - 7.5), abs(y - 7.5))
            if d > 5.6:
                c = r.choice(bark)
            else:
                band = int(d + 0.3)
                c = rings[band % 2]
                if r.random() < 0.15:
                    c = shade(c, 0.92)
            img.putpixel((x, y), c)
    for (x, y) in ((7, 7), (8, 7), (7, 8), (8, 8)):
        img.putpixel((x, y), shade(rings[1], 0.8))
    return img


def planks(tones, seed):
    img = new()
    r = random.Random(seed)
    dark = shade(tones[1], 0.72)
    light = shade(tones[1], 1.12)
    for b in range(4):
        base = r.choice(tones)
        joint = (b * 9 + 5 + seed) % S
        for y in range(b * 4, b * 4 + 4):
            for x in range(S):
                c = base
                if r.random() < 0.22:
                    c = shade(base, r.choice((0.92, 0.95, 1.06)))
                if y % 4 == 3:
                    c = dark
                elif y % 4 == 0:
                    c = shade(c, 1.06)
                if x == joint:
                    c = dark
                img.putpixel((x, y), c)
        for _ in range(2):  # тёмные волокна
            gx, gy = r.randrange(1, 14), b * 4 + r.randrange(0, 3)
            img.putpixel((gx, gy), dark)
            img.putpixel((gx + 1, gy), dark)
    return img


def leaves(colors, seed, hole=0.07):
    img = new()
    n = vnoise(seed, 4)
    r = random.Random(seed + 9)
    for y in range(S):
        for x in range(S):
            if r.random() < hole:
                continue
            v = (n(x, y) - 0.2) / 0.6 * 0.6 + r.random() * 0.4
            v = max(0.0, min(0.999, v))
            img.putpixel((x, y), colors[int(v * len(colors))])
    return img


# ----------------------------------------------------------------------------- флора
def blades(seed, n, hmin, hmax, dark, light, tip=None):
    img = new()
    r = random.Random(seed)
    xs = r.sample(range(1, 15), n)
    for x0 in xs:
        h = r.randrange(hmin, hmax + 1)
        lean = r.choice((-2, -1, 0, 1, 2)) / max(1, h)
        for k in range(h):
            t = k / max(1, h - 1)
            x = round(x0 + lean * k * 2)
            y = S - 1 - k
            c = tuple(int(dark[i] + (light[i] - dark[i]) * t) for i in range(3)) + (255,)
            put(img, x, y, c)
            if k < 2 and r.random() < 0.5:
                put(img, x + 1, y, shade(c, 0.9))
        if tip:
            put(img, round(x0 + lean * h * 2), S - h - 1, tip)
    return img


def tall_grass(seed=301):
    return blades(seed, 7, 6, 12, hx("#3f7d28"), hx("#8fcf58"))


def tall_grass_dense(seed=302):
    return blades(seed, 10, 8, 14, hx("#2f6a22"), hx("#79c04a"))


def slime_grass():
    return blades(303, 8, 6, 12, hx("#3fc02c"), hx("#98f36e"), tip=hx("#d6ffbf"))


def fern():
    img = new()
    stem = hx("#2f6b2a")
    a, b = hx("#3f8a34"), hx("#68b34a")
    for y in range(3, 16):
        put(img, 8 if y > 8 else 7 + (y % 2 == 0) * 0 + 1, y, stem)
    for i, y in enumerate((13, 11, 9, 7, 5)):
        ln = max(2, 6 - i)
        for k in range(1, ln + 1):
            c = a if k < ln else b
            put(img, 8 - k, y - k // 2, c)
            put(img, 8 + k, y - k // 2, c)
    put(img, 8, 2, b)
    put(img, 8, 3, b)
    return img


def rose():
    img = new()
    stem, leaf = hx("#3b7a2a"), hx("#4f9a38")
    for y in range(7, 16):
        put(img, 8, y, stem)
    for (x, y) in ((7, 12), (6, 11), (9, 10), (10, 9)):
        put(img, x, y, leaf)
    reds = pal("#d9202e", "#e8323f", "#b3131f")
    r = random.Random(311)
    for y in range(2, 9):
        for x in range(5, 12):
            if math.hypot(x - 8, y - 5) <= 2.8:
                put(img, x, y, r.choice(reds))
    for (x, y) in ((8, 5), (7, 5), (8, 4)):
        put(img, x, y, hx("#8e0d18"))
    put(img, 7, 3, hx("#ff7a84"))
    return img


def flower():
    img = new()
    stem, leaf = hx("#3b7a2a"), hx("#4f9a38")
    for y in range(7, 16):
        put(img, 8, y, stem)
    for (x, y) in ((9, 13), (10, 12), (7, 11), (6, 10)):
        put(img, x, y, leaf)
    petal = hx("#f4f4ff")
    for (dx, dy) in ((0, -3), (0, 3), (-3, 0), (3, 0), (-2, -2), (2, -2), (-2, 2), (2, 2),
                     (0, -2), (0, 2), (-2, 0), (2, 0)):
        put(img, 8 + dx, 5 + dy, petal)
    for (dx, dy) in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
        put(img, 8 + dx, 5 + dy, hx("#ffc82e"))
    return img


def moss():
    img = new()
    n = vnoise(321, 4)
    r = random.Random(322)
    greens = pal("#2f6b34", "#3f8a44", "#58a85a", "#3a7a3e")
    for x in range(S):
        h = 3 + int(n(x, 3) * 5) + r.randrange(0, 2)
        for k in range(h):
            y = S - 1 - k
            c = r.choice(greens)
            if k == h - 1:
                c = hx("#7cc47a")
            put(img, x, y, c)
    for (x, y) in ((3, 8), (11, 7), (7, 9)):
        for k in range(r.randrange(2, 4)):
            put(img, x, y + k, greens[0])
    return img


def mushroom():
    img = new()
    reds = pal("#d0342c", "#e04a3c", "#b12a24")
    r = random.Random(331)

    def shroom(cx, cy, rx, ry, stem_h):
        for y in range(cy - ry, cy + 1):
            for x in range(cx - rx, cx + rx + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.05:
                    put(img, x, y, r.choice(reds))
        for k in range(stem_h):
            put(img, cx, cy + 1 + k, hx("#e8dcc0"))
            put(img, cx - 1, cy + 1 + k, hx("#cfc3a6"))
    shroom(6, 8, 4, 3, 6)
    shroom(12, 12, 3, 2, 3)
    for (x, y) in ((5, 6), (7, 7), (4, 8), (11, 11)):
        put(img, x, y, hx("#fff5e6"))
    return img


def hanging(seed, colors, count, minlen, maxlen, sway=True):
    img = new()
    r = random.Random(seed)
    for x0 in r.sample(range(1, 15), count):
        length = r.randrange(minlen, maxlen + 1)
        x = x0
        for y in range(length):
            put(img, x, y, r.choice(colors))
            if sway and y % 4 == 3:
                x += r.choice((-1, 1))
    return img


def root():
    img = hanging(341, pal("#5b3f26", "#6e4c2e", "#7d5a38"), 5, 6, 15)
    for (x, y) in ((4, 7), (5, 8), (11, 5), (12, 6)):
        put(img, x, y, hx("#7d5a38"))
    return img


def cave_vine():
    img = new()
    r = random.Random(351)
    greens = pal("#2f6b34", "#3f8a44", "#58a85a")
    for x0 in (3, 8, 12):
        x = x0
        for y in range(r.randrange(9, 16)):
            put(img, x, y, greens[0])
            if y % 3 == 2:
                put(img, x + 1, y, greens[1])
                put(img, x - 1, y - 1, greens[2])
            if y % 5 == 4:
                x += r.choice((-1, 1))
    return img


def glow_berry():
    img = new()
    stem, leaf = hx("#3f8a44"), hx("#58a85a")
    x = 8
    for y in range(0, 16):
        put(img, x, y, stem)
        if y % 5 == 4:
            x += 1 if x < 9 else -1
    for (x, y) in ((6, 3), (10, 6), (5, 11)):
        put(img, x, y, leaf)
    for (bx, by) in ((5, 8), (11, 10), (7, 13)):
        for (dx, dy) in ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):
            put(img, bx + dx, by + dy, hx("#ffb020"))
        put(img, bx, by, hx("#fff07a"))
        put(img, bx, by - 2, stem)
    return img


def cave_crystal():
    img = new()
    dark, light = hx("#5b3fd0"), hx("#8f7bff")

    def spike(cx, top, half):
        for y in range(top, S):
            w = half * (y - top) / max(1, (S - 1 - top)) + 0.5
            for x in range(int(cx - w), int(cx + w) + 1):
                if abs(x - cx) <= w:
                    put(img, x, y, dark if x < cx else light)
            put(img, cx, y, hx("#c9beff"))
        put(img, cx, top, hx("#ffffff"))
    spike(4, 7, 2.2)
    spike(12, 6, 2.4)
    spike(8, 2, 3.0)
    for (x, y) in ((7, 6), (8, 9), (3, 11), (12, 10)):
        put(img, x, y, hx("#e6e0ff"))
    return img


# ----------------------------------------------------------------------------- станки
def crafting_top():
    img = planks(pal("#b8945a", "#c19c60", "#ad8a52"), 401)
    dark = hx("#3d2a14")
    for i in (1, 5, 10, 14):
        for k in range(1, 15):
            put(img, i, k, dark)
            put(img, k, i, dark)
    return img


def crafting_side():
    """Боковая грань верстака: доски с полосой сверху и висящими инструментами."""
    img = planks(pal("#a98a55", "#b39560", "#9c7f4e"), 402)
    trim = hx("#5a3d1e")
    for x in range(S):
        for y in range(0, 2):
            put(img, x, y, trim)
    handle, metal, mdark = hx("#6b4a2a"), hx("#c9ced4"), hx("#7c828a")
    for y in range(5, 15):
        put(img, 3, y, handle)
        put(img, 12, y, handle)
    for x in range(1, 6):
        put(img, x, 5, metal)
        put(img, x, 6, mdark)
    for x in range(10, 15):
        put(img, x, 5, metal)
    for y in range(6, 9):
        put(img, 14, y, metal)
    return img


def crafting_front():
    """Лицо верстака: молоток и пила на досках."""
    img = planks(pal("#a98a55", "#b39560", "#9c7f4e"), 403)
    trim = hx("#5a3d1e")
    for x in range(S):
        for y in range(0, 3):
            put(img, x, y, trim)
    handle, metal, mdark = hx("#6b4a2a"), hx("#c9ced4"), hx("#7c828a")
    for y in range(6, 14):
        put(img, 4, y, handle)
    for x in range(2, 7):
        put(img, x, 5, metal)
        put(img, x, 6, mdark)
    for x in range(9, 14):
        put(img, x, 7, metal)
        put(img, x, 8, metal)
        if x % 2 == 0:
            put(img, x, 9, mdark)
    for (x, y) in ((13, 6), (14, 6), (14, 7), (14, 8), (13, 9)):
        put(img, x, y, handle)
    return img


def chest_top():
    img = planks(pal("#a98a55", "#b39560", "#9c7f4e"), 411)
    border(img, hx("#3e2a12"))
    border(img, hx("#7a5f37"), 1)
    return img


def chest_side():
    img = planks(pal("#a98a55", "#b39560", "#9c7f4e"), 412)
    border(img, hx("#3e2a12"))
    for x in range(1, 15):
        put(img, x, 5, hx("#3e2a12"))
    return img


def chest_front():
    img = chest_side()
    for y in range(4, 9):
        for x in (7, 8):
            put(img, x, y, hx("#c8ccd2"))
    put(img, 7, 8, hx("#555a60"))
    put(img, 8, 8, hx("#555a60"))
    put(img, 7, 4, hx("#eef0f2"))
    return img


def furnace_top():
    img = cobble(421)
    border(img, hx("#4a4a4a"))
    for x in range(4, 12):
        for y in range(4, 12):
            put(img, x, y, hx("#3a3a3a") if (x in (4, 11) or y in (4, 11)) else hx("#2a2a2a"))
    return img


def furnace_side():
    img = cobble(422)
    border(img, hx("#4a4a4a"))
    return img


def _furnace_face(lit):
    img = cobble(422)
    border(img, hx("#4a4a4a"))
    for x in range(3, 13):
        put(img, x, 2, hx("#3d3d3d"))          # верхняя балка
    for y in range(3, 8):
        for x in range(4, 12):
            put(img, x, y, hx("#1c1c1c"))      # топка
    for x in range(4, 12):
        put(img, x, 8, hx("#3d3d3d"))
    for y in range(9, 14):
        for x in range(4, 12):
            put(img, x, y, hx("#252525") if (x + y) % 2 else hx("#141414"))  # поддувало
    for x in range(4, 12, 2):
        put(img, x, 12, hx("#5c5c5c"))
    if lit:
        for x in range(5, 11):
            put(img, x, 6, hx("#ff9a1f"))
            put(img, x, 7, hx("#ffcf4a") if x in (7, 8) else hx("#ff7a12"))
        for (x, y) in ((6, 5), (8, 4), (9, 5), (7, 5), (8, 5)):
            put(img, x, y, hx("#ff8a1f"))
        put(img, 8, 4, hx("#ffd15a"))
        for x in range(5, 11):
            put(img, x, 10, hx("#ff7a12") if x % 2 else hx("#c9480c"))
    return img


def furnace_front():
    return _furnace_face(False)


def furnace_front_on():
    return _furnace_face(True)


# ----------------------------------------------------------------------------- предметы
def _rot(x, y, ang):
    c, s = math.cos(ang), math.sin(ang)
    return x * c - y * s, x * s + y * c


def chop(body, fat, outline, grill=False):
    img = new()
    r = random.Random(501)
    ang = math.radians(-35)
    inside = {}
    for y in range(S):
        for x in range(S):
            u, v = _rot(x - 8.5, y - 7.5, ang)
            if (u / 6.4) ** 2 + (v / 4.2) ** 2 <= 1.0:
                inside[(x, y)] = v
    for (x, y), v in inside.items():
        edge = any((x + dx, y + dy) not in inside for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if edge:
            c = outline
        elif v < -2.2:
            c = fat
        else:
            c = r.choice(body)
        if grill and not edge and (x + y) % 5 == 0 and v >= -2.2:
            c = hx("#5a2c1c")
        img.putpixel((x, y), c)
    return img


def raw_porkchop():
    img = chop(pal("#ee8f98", "#f29ea6", "#e8838d"), hx("#f9c4c9"), hx("#8a3a48"))
    for (x, y) in ((2, 12), (3, 12), (2, 13), (3, 13), (4, 11)):
        put(img, x, y, hx("#efe6d0"))
    return img


def cooked_porkchop():
    img = chop(pal("#a8583a", "#b8683f", "#9a4a30"), hx("#d99a5a"), hx("#5c2b1a"), grill=True)
    for (x, y) in ((2, 12), (3, 12), (2, 13), (3, 13), (4, 11)):
        put(img, x, y, hx("#e0d2b0"))
    return img


def charcoal():
    img = new()
    n = vnoise(511, 4)
    r = random.Random(512)
    pts = {}
    for y in range(S):
        for x in range(S):
            d = math.hypot((x - 7.5) / 5.6, (y - 8.5) / 4.6)
            if d + (n(x, y) - 0.5) * 0.5 <= 1.0:
                pts[(x, y)] = True
    for (x, y) in pts:
        edge = any((x + dx, y + dy) not in pts for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        c = hx("#151517") if edge else r.choice(pal("#2a2a2e", "#38383e", "#1f1f22"))
        img.putpixel((x, y), c)
    for (x, y) in ((6, 7), (9, 9), (7, 10), (10, 7)):
        if (x, y) in pts:
            put(img, x, y, hx("#5e5e66"))
    return img


# ----------------------------------------------------------------------------- набор спрайтов
W = {
    "oak":     dict(planks=pal("#b8945a", "#c19c60", "#ad8a52"),
                    bark=pal("#5a4527", "#6b5230", "#4a381f"), groove=hx("#3a2c15"),
                    rings=pal("#b8945a", "#a68048"),
                    leaves=pal("#3f7a2a", "#4f8e35", "#2f6421", "#5c9e3e")),
    "birch":   dict(planks=pal("#d8c791", "#e0d09a", "#cfbe88"),
                    rings=pal("#d8c791", "#c9b77f"), bark_top=pal("#e8e6dc", "#d9d6ca"),
                    leaves=pal("#6f9a3c", "#80ad49", "#5f8a33", "#8fbc55")),
    "spruce":  dict(planks=pal("#6b4a2a", "#785433", "#5d3f23"),
                    bark=pal("#3d2a17", "#4a3320", "#31200f"), groove=hx("#22160a"),
                    rings=pal("#6b4a2a", "#5a3d21"),
                    leaves=pal("#2a5238", "#33613f", "#22452f", "#3b6e48")),
    "jungle":  dict(planks=pal("#a0724a", "#ab7c52", "#946842"),
                    bark=pal("#4e3f1c", "#5d4b25", "#3f3116"), groove=hx("#2b2110"),
                    rings=pal("#a0724a", "#8c6240"),
                    leaves=pal("#2e8f1f", "#3aa628", "#237a17", "#4cbc35")),
    "acacia":  dict(planks=pal("#c0663a", "#cc7042", "#b05c33"),
                    bark=pal("#6b6259", "#7a7067", "#5b534b"), groove=hx("#3e3831"),
                    rings=pal("#c0663a", "#a8552f"),
                    leaves=pal("#7a9a2a", "#8cae34", "#6a8822", "#9dbf42")),
}


def build():
    s = {}
    s["air"] = new()
    s["stone"] = stone()
    s["dirt"] = dirt()
    s["grass_top"] = grass_top()
    s["grass_side"] = grass_side()
    s["sand"] = sand()
    s["mud"] = mud()
    s["mossy_stone"] = mossy_stone()
    s["deep_stone"] = deep_stone()
    s["lava_stone"] = lava_stone()
    s["wet_stone"] = wet_stone()
    s["cloud_stone"] = cloud_stone()
    s["ice"] = ice()
    s["slime_block"] = slime_block()
    s["sun_stone"] = sun_stone()
    s["water"] = water()
    s["iron_ore"] = ore(601, pal("#d8b090", "#c99a76", "#e8c8ac"))
    s["gold_ore"] = ore(602, pal("#ffd23a", "#f5b81f", "#fff07a"))
    s["rare_mineral"] = ore(603, pal("#3fd0c9", "#7ff0e6", "#1b8f95", "#d5fffb"), 6)

    for i, name in enumerate(("oak", "birch", "spruce", "jungle", "acacia")):
        w = W[name]
        s[name + "_planks"] = planks(w["planks"], 700 + i)
        s[name + "_leaves"] = leaves(w["leaves"], 710 + i)
        if name == "birch":
            s["birch_log_side"] = birch_side()
            s["birch_log_top"] = log_top(w["bark_top"], w["rings"], 720 + i)
        else:
            s[name + "_log_side"] = log_side(w["bark"], w["groove"], 730 + i)
            s[name + "_log_top"] = log_top(w["bark"], w["rings"], 720 + i)

    s["slimewood_log_side"] = log_side(pal("#4b6b2a", "#5a7c33", "#3c5a20"), hx("#2b4315"), 741,
                                       drips=pal("#7ee858", "#a6f57f"))
    s["slimewood_log_top"] = log_top(pal("#4b6b2a", "#5a7c33"), pal("#b9d46a", "#9dbb52"), 742)
    s["slimewood_leaves"] = leaves(pal("#4fd67a", "#63e58c", "#3fbf68", "#7af0a0"), 743, 0.12)

    s["tall_grass"] = tall_grass()
    s["tall_grass_dense"] = tall_grass_dense()
    s["slime_grass"] = slime_grass()
    s["fern"] = fern()
    s["rose"] = rose()
    s["flower"] = flower()
    s["moss"] = moss()
    s["mushroom"] = mushroom()
    s["root"] = root()
    s["cave_vine"] = cave_vine()
    s["glow_berry"] = glow_berry()
    s["cave_crystal"] = cave_crystal()

    s["crafting_top"] = crafting_top()
    s["crafting_side"] = crafting_side()
    s["crafting_front"] = crafting_front()
    s["chest_top"] = chest_top()
    s["chest_side"] = chest_side()
    s["chest_front"] = chest_front()
    s["furnace_top"] = furnace_top()
    s["furnace_side"] = furnace_side()
    s["furnace_front"] = furnace_front()
    s["furnace_front_on"] = furnace_front_on()

    s["item_raw_porkchop"] = raw_porkchop()
    s["item_cooked_porkchop"] = cooked_porkchop()
    s["item_charcoal"] = charcoal()

    # Добавлены в КОНЕЦ, чтобы не сдвигать позиции уже существующих спрайтов в атласе.
    s["red_sand"] = red_sand()
    s["gravel"] = gravel()
    s["snow_block"] = snow_block()
    return s


# id -> описание блока: texture {top,side,bottom[,front]}, orientation, active_texture
def mapping():
    def all3(n):
        return {"top": n, "side": n, "bottom": n}

    def log(n):
        return {"texture": {"top": n + "_log_top", "side": n + "_log_side", "bottom": n + "_log_top"},
                "orientation": "axis"}

    def plain(n):
        return {"texture": all3(n)}

    m = {
        0: plain("air"), 1: {"texture": {"top": "grass_top", "side": "grass_side", "bottom": "dirt"}},
        2: plain("dirt"), 3: plain("stone"), 4: plain("sand"), 5: log("oak"), 6: plain("oak_leaves"),
        7: plain("water"), 9: plain("rose"), 10: plain("tall_grass"), 11: plain("sun_stone"),
        12: plain("red_sand"), 13: plain("gravel"), 14: plain("snow_block"), 15: log("birch"),
        16: plain("birch_planks"), 17: plain("birch_leaves"), 18: log("spruce"),
        19: plain("spruce_planks"), 20: plain("spruce_leaves"), 21: log("jungle"),
        22: plain("jungle_planks"), 23: plain("jungle_leaves"), 24: log("acacia"),
        25: plain("acacia_planks"), 26: plain("acacia_leaves"), 27: log("slimewood"),
        28: plain("slimewood_leaves"), 29: plain("tall_grass_dense"), 30: plain("fern"),
        31: plain("flower"), 32: plain("moss"), 33: plain("mushroom"), 34: plain("root"),
        35: plain("glow_berry"), 36: plain("mossy_stone"), 37: plain("iron_ore"),
        38: plain("gold_ore"), 39: plain("rare_mineral"), 40: plain("cave_crystal"),
        41: plain("slime_grass"), 42: plain("slime_block"), 43: plain("deep_stone"),
        44: plain("lava_stone"), 45: plain("cave_vine"), 46: plain("mud"), 47: plain("wet_stone"),
        48: plain("cloud_stone"), 49: plain("ice"),
        50: {"texture": {"top": "chest_top", "side": "chest_side", "bottom": "oak_planks",
                         "front": "chest_front"}, "orientation": "facing"},
        51: {"texture": {"top": "crafting_top", "side": "crafting_side", "bottom": "oak_planks",
                         "front": "crafting_front"}, "orientation": "facing"},
        52: {"texture": {"top": "furnace_top", "side": "furnace_side", "bottom": "furnace_top",
                         "front": "furnace_front"},
             "orientation": "facing",
             "active_texture": {"front": "furnace_front_on"}},
        53: plain("item_raw_porkchop"), 54: plain("item_cooked_porkchop"), 55: plain("item_charcoal"),
        # Oak Log / Oak Planks / Oak Leaves раньше сидели на id 12/13/14 и затирали Red Sand /
        # Gravel / Snow Block, на которые ссылается генератор мира (Block_Types.h).
        56: log("oak"), 57: plain("oak_planks"), 58: plain("oak_leaves"),
    }
    return m


def main():
    sprites = build()
    atlas_path = os.path.join(ROOT, "assets/texture/texture_atlas.png")
    old = Image.open(atlas_path)
    atlas = Image.new("RGBA", old.size, (0, 0, 0, 0))
    per_row = old.size[0] // S
    manifest = {"name": "blocks_main", "texture": "../texture/texture_atlas.png", "sprites": {}}
    for i, (name, img) in enumerate(sprites.items()):
        x, y = (i % per_row) * S, (i // per_row) * S
        atlas.paste(img, (x, y))
        manifest["sprites"][name] = {"x": x, "y": y, "w": S, "h": S}
    atlas.save(atlas_path)
    with open(os.path.join(ROOT, "assets/atlases/blocks_main.atlas.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    # blocks.json: обновляем "texture" (+ "orientation", "active_texture") у каждого блока
    bpath = os.path.join(ROOT, "assets/blocks.json")
    data = json.loads(open(bpath, encoding="utf-8").read())
    m = mapping()
    n = 0
    for b in data["blocks"]:
        d = m[b["id"]]
        tex = {"atlas": "blocks_main"}
        tex.update(d["texture"])
        b["texture"] = tex
        b.pop("orientation", None)
        b.pop("active_texture", None)
        if "orientation" in d:
            b["orientation"] = d["orientation"]
        if "active_texture" in d:
            act = {"atlas": "blocks_main"}
            act.update(d["active_texture"])
            b["active_texture"] = act
        n += 1
    open(bpath, "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False))

    # превью для проверки
    names = list(sprites.keys())
    cols = 12
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 20 + 4, rows * 20 + 4), (255, 0, 255, 255))
    for i, n_ in enumerate(names):
        sheet.alpha_composite(sprites[n_], ((i % cols) * 20 + 4, (i // cols) * 20 + 4))
    sheet.resize((sheet.width * 6, sheet.height * 6), Image.NEAREST).save("/tmp/preview.png")
    print("sprites:", len(names), "blocks patched:", n)


if __name__ == "__main__":
    main()
