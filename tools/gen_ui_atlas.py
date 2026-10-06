#!/usr/bin/env python3
"""Рисует атлас ИНТЕРФЕЙСА OptiCraft (отдельный от атласа блоков).

Источник правды для интерфейса --- готовый assets/texture/ui_atlas.png; скрипт воспроизводит его побитно
и нужен для добавления новых спрайтов.

Запуск из корня проекта:  python3 tools/gen_ui_atlas.py
Пишет:
    assets/texture/ui_atlas.png
    assets/atlases/ui_main.atlas.json   (Atlas_Registry подхватывает его сам, имя атласа "ui_main")

Что внутри (имена спрайтов — это контракт с src/hud/Hud.cpp):
    font_<код Unicode>        глиф шрифта: ASCII, русская кириллица, Ё/ё (ширина обрезана по факту, высота ячейки 9)
    white                     2x2 белый квадрат — им рисуются все залитые прямоугольники
    panel / panel_dark        9-slice рамки (инвентарь — светлая, меню — тёмная)
    btn / btn_hover / btn_off 9-slice кнопки
    field / field_focus       9-slice поле ввода текста
    row / row_sel             строка списка миров
    tooltip                   подсказка у курсора
    slot                      слот инвентаря 18x18
    hotbar / hotbar_sel       хотбар 182x22 и рамка выбранного слота 24x24
    heart_*, food_*           сердца и куриные ножки 9x9
    arrow_empty/full, flame_empty/full   прогресс крафта/плавки
    logo, bg_tile, world_icon, player, crosshair, scroll_*, slider_*
"""
import json
import os
import random
import sys

from PIL import Image

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
ATLAS_SIZE = 512


# ----------------------------------------------------------------------------- утилиты
def hx(c, a=255):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


def shade(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))), c[3])


def new(w, h, fill=(0, 0, 0, 0)):
    return Image.new("RGBA", (w, h), fill)


def put(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def rect(img, x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put(img, xx, yy, c)


def frame(img, x, y, w, h, c):
    for i in range(w):
        put(img, x + i, y, c)
        put(img, x + i, y + h - 1, c)
    for j in range(h):
        put(img, x, y + j, c)
        put(img, x + w - 1, y + j, c)


def noise_fill(img, x, y, w, h, base, amp, seed):
    r = random.Random(seed)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            f = 1.0 + (r.random() - 0.5) * amp
            put(img, xx, yy, shade(base, f))


def round_corners(img):
    """Срезает угловые пиксели — рамки получаются слегка скруглёнными."""
    w, h = img.size
    for (x, y) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        put(img, x, y, (0, 0, 0, 0))


# ----------------------------------------------------------------------------- шрифт
# 5x7, строчные — x-height 5 (строки 2..6), выносные элементы g j p q y уходят на строки 7..8.
F = {}


def glyph(ch, *rows):
    F[ch] = list(rows)


# цифры
glyph("0", ".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###.")
glyph("1", ".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###")
glyph("2", ".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####")
glyph("3", ".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###.")
glyph("4", "...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#.")
glyph("5", "#####", "#....", "####.", "....#", "....#", "#...#", ".###.")
glyph("6", ".###.", "#....", "#....", "####.", "#...#", "#...#", ".###.")
glyph("7", "#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#...")
glyph("8", ".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###.")
glyph("9", ".###.", "#...#", "#...#", ".####", "....#", "....#", ".###.")
# прописные
glyph("A", ".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#")
glyph("B", "####.", "#...#", "#...#", "####.", "#...#", "#...#", "####.")
glyph("C", ".###.", "#...#", "#....", "#....", "#....", "#...#", ".###.")
glyph("D", "####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####.")
glyph("E", "#####", "#....", "#....", "####.", "#....", "#....", "#####")
glyph("F", "#####", "#....", "#....", "####.", "#....", "#....", "#....")
glyph("G", ".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###.")
glyph("H", "#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#")
glyph("I", "###", ".#.", ".#.", ".#.", ".#.", ".#.", "###")
glyph("J", "..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##..")
glyph("K", "#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#")
glyph("L", "#....", "#....", "#....", "#....", "#....", "#....", "#####")
glyph("M", "#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#")
glyph("N", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#")
glyph("O", ".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###.")
glyph("P", "####.", "#...#", "#...#", "####.", "#....", "#....", "#....")
glyph("Q", ".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#")
glyph("R", "####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#")
glyph("S", ".####", "#....", "#....", ".###.", "....#", "....#", "####.")
glyph("T", "#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#..")
glyph("U", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###.")
glyph("V", "#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#..")
glyph("W", "#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#")
glyph("X", "#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#")
glyph("Y", "#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#..")
glyph("Z", "#####", "....#", "...#.", "..#..", ".#...", "#....", "#####")
# строчные
glyph("a", ".....", ".....", ".###.", "....#", ".####", "#...#", ".####")
glyph("b", "#....", "#....", "#.##.", "##..#", "#...#", "##..#", "#.##.")
glyph("c", ".....", ".....", ".###.", "#...#", "#....", "#...#", ".###.")
glyph("d", "....#", "....#", ".##.#", "#..##", "#...#", "#..##", ".##.#")
glyph("e", ".....", ".....", ".###.", "#...#", "#####", "#....", ".###.")
glyph("f", "..##.", ".#...", "####.", ".#...", ".#...", ".#...", ".#...")
glyph("g", ".....", ".....", ".####", "#...#", "#...#", ".####", "....#", "#...#", ".###.")
glyph("h", "#....", "#....", "#.##.", "##..#", "#...#", "#...#", "#...#")
glyph("i", "#", ".", "#", "#", "#", "#", "#")
glyph("j", "..#", "...", "..#", "..#", "..#", "..#", "..#", "#.#", ".#.")
glyph("k", "#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#.")
glyph("l", "#", "#", "#", "#", "#", "#", "#")
glyph("m", ".....", ".....", "##.#.", "#.#.#", "#.#.#", "#...#", "#...#")
glyph("n", ".....", ".....", "#.##.", "##..#", "#...#", "#...#", "#...#")
glyph("o", ".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###.")
glyph("p", ".....", ".....", "#.##.", "##..#", "#...#", "##..#", "#.##.", "#....", "#....")
glyph("q", ".....", ".....", ".##.#", "#..##", "#...#", "#..##", ".##.#", "....#", "....#")
glyph("r", ".....", ".....", "#.##.", "##..#", "#....", "#....", "#....")
glyph("s", ".....", ".....", ".####", "#....", ".###.", "....#", "####.")
glyph("t", ".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##.")
glyph("u", ".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#")
glyph("v", ".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#..")
glyph("w", ".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#.")
glyph("x", ".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#")
glyph("y", ".....", ".....", "#...#", "#...#", "#...#", ".####", "....#", "#...#", ".###.")
glyph("z", ".....", ".....", "#####", "...#.", "..#..", ".#...", "#####")
# знаки
glyph(".", ".", ".", ".", ".", ".", ".", "#")
glyph(",", ".", ".", ".", ".", ".", "#", "#")
glyph(":", ".", "#", ".", ".", ".", "#", ".")
glyph(";", ".", "#", ".", ".", ".", "#", "#")
glyph("!", "#", "#", "#", "#", "#", ".", "#")
glyph("?", ".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#..")
glyph("-", ".", ".", ".", "###", ".", ".", ".")
glyph("_", ".", ".", ".", ".", ".", ".", ".", "#####")
glyph("+", ".", ".", ".#.", "###", ".#.", ".", ".")
glyph("=", ".", ".", "###", ".", "###", ".", ".")
glyph("/", "....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#....")
glyph("\\", "#....", ".#...", ".#...", "..#..", "...#.", "...#.", "....#")
glyph("(", ".#", "#.", "#.", "#.", "#.", "#.", ".#")
glyph(")", "#.", ".#", ".#", ".#", ".#", ".#", "#.")
glyph("[", "##", "#.", "#.", "#.", "#.", "#.", "##")
glyph("]", "##", ".#", ".#", ".#", ".#", ".#", "##")
glyph("{", "..#", ".#.", ".#.", "#..", ".#.", ".#.", "..#")
glyph("}", "#..", ".#.", ".#.", "..#", ".#.", ".#.", "#..")
glyph("<", ".", ".", "..#", ".#.", "#..", ".#.", "..#")
glyph(">", ".", ".", "#..", ".#.", "..#", ".#.", "#..")
glyph("*", ".", "#.#.#", ".###.", "#####", ".###.", "#.#.#", ".")
glyph("%", "##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##")
glyph("#", ".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#.")
glyph('"', "#.#", "#.#")
glyph("'", "#", "#")
glyph("|", "#", "#", "#", "#", "#", "#", "#", "#", "#")
glyph("~", ".", ".", ".", ".##.#", "#.##.", ".", ".")
glyph("@", ".###.", "#...#", "#.###", "#.#.#", "#.###", "#....", ".###.")
glyph("$", "..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#..")
glyph("&", ".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#")
glyph("^", ".#.", "#.#")
glyph("`", "#.", ".#")

# русская кириллица. Буквы, совпадающие по начертанию с латинскими, берутся оттуда.
def same_as(cyr, lat):
    F[cyr] = list(F[lat])


for _c, _l in zip("АВЕКМНОРСТХ", "ABEKMHOPCTX"):
    same_as(_c, _l)
for _c, _l in zip("аеорсх", "aeopcx"):
    same_as(_c, _l)
same_as("у", "y")

glyph("Б", "#####", "#....", "#....", "####.", "#...#", "#...#", "####.")
glyph("Г", "#####", "#....", "#....", "#....", "#....", "#....", "#....")
glyph("Д", ".####", ".#..#", ".#..#", ".#..#", ".#..#", "#####", "#...#")
glyph("Ж", "#.#.#", "#.#.#", ".###.", "..#..", ".###.", "#.#.#", "#.#.#")
glyph("З", ".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###.")
glyph("И", "#...#", "#...#", "#..##", "#.#.#", "##..#", "#...#", "#...#")
glyph("Й", ".#.#.", "#...#", "#..##", "#.#.#", "##..#", "#...#", "#...#")
glyph("Л", "..###", ".#..#", "#...#", "#...#", "#...#", "#...#", "#...#")
glyph("П", "#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#")
glyph("У", "#...#", "#...#", "#...#", ".####", "....#", "...#.", "###..")
glyph("Ф", "..#..", ".###.", "#.#.#", "#.#.#", "#.#.#", ".###.", "..#..")
glyph("Ц", "#..#.", "#..#.", "#..#.", "#..#.", "#..#.", "#####", "....#")
glyph("Ч", "#...#", "#...#", "#...#", ".####", "....#", "....#", "....#")
glyph("Ш", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#####")
glyph("Щ", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#####", "....#")
glyph("Ъ", "##...", ".#...", ".#...", ".###.", ".#..#", ".#..#", ".###.")
glyph("Ы", "#...#", "#...#", "#...#", "###.#", "#..##", "#..##", "###.#")
glyph("Ь", "#....", "#....", "#....", "####.", "#...#", "#...#", "####.")
glyph("Э", ".###.", "#...#", "....#", ".####", "....#", "#...#", ".###.")
glyph("Ю", "#..#.", "#.#.#", "#.#.#", "###.#", "#.#.#", "#.#.#", "#..#.")
glyph("Я", ".####", "#...#", "#...#", ".####", ".#..#", "#...#", "#...#")
glyph("Ё", ".#.#.", "#####", "#....", "####.", "#....", "#....", "#####")

glyph("б", "...##", "..#..", ".#...", "####.", "#...#", "#...#", ".###.")
glyph("в", ".....", ".....", "####.", "#...#", "####.", "#...#", "####.")
glyph("г", ".....", ".....", "####.", "#....", "#....", "#....", "#....")
glyph("д", ".....", ".....", "..###", ".#..#", ".#..#", "#####", "#...#")
glyph("ё", ".#.#.", ".....", ".###.", "#...#", "#####", "#....", ".###.")
glyph("ж", ".....", ".....", "#.#.#", ".###.", "..#..", ".###.", "#.#.#")
glyph("з", ".....", ".....", "####.", "....#", "..##.", "....#", "####.")
glyph("и", ".....", ".....", "#...#", "#..##", "#.#.#", "##..#", "#...#")
glyph("й", ".#.#.", ".....", "#...#", "#..##", "#.#.#", "##..#", "#...#")
glyph("к", ".....", ".....", "#..#.", "#.#..", "##...", "#.#..", "#..#.")
glyph("л", ".....", ".....", "..###", ".#..#", "#...#", "#...#", "#...#")
glyph("м", ".....", ".....", "#...#", "##.##", "#.#.#", "#...#", "#...#")
glyph("н", ".....", ".....", "#...#", "#...#", "#####", "#...#", "#...#")
glyph("п", ".....", ".....", "#####", "#...#", "#...#", "#...#", "#...#")
glyph("т", ".....", ".....", "#####", "..#..", "..#..", "..#..", "..#..")
glyph("ф", "..#..", "..#..", ".###.", "#.#.#", "#.#.#", "#.#.#", ".###.", "..#..", "..#..")
glyph("ц", ".....", ".....", "#..#.", "#..#.", "#..#.", "#####", "....#")
glyph("ч", ".....", ".....", "#...#", "#...#", ".####", "....#", "....#")
glyph("ш", ".....", ".....", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#####")
glyph("щ", ".....", ".....", "#.#.#", "#.#.#", "#.#.#", "#####", "....#")
glyph("ъ", ".....", ".....", "##...", ".#...", ".###.", ".#..#", ".###.")
glyph("ы", ".....", ".....", "#...#", "#...#", "###.#", "#..##", "###.#")
glyph("ь", ".....", ".....", "#....", "#....", "####.", "#...#", "####.")
glyph("э", ".....", ".....", "####.", "....#", ".####", "....#", "####.")
glyph("ю", ".....", ".....", "#..#.", "#.#.#", "###.#", "#.#.#", "#..#.")
glyph("я", ".....", ".....", ".####", "#...#", ".####", ".#..#", "#...#")


def font_sprites():
    out = {}
    for ch, rows in F.items():
        w = max(len(r) for r in rows)
        img = new(w, 9)
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c == "#":
                    put(img, x, y, (255, 255, 255, 255))
        out["font_%d" % ord(ch)] = img
    return out


# ----------------------------------------------------------------------------- рамки
def bevel_panel(size, outline, light, base, dark, seed, noise=0.05, corners=True, light_w=2, dark_w=2):
    img = new(size, size)
    noise_fill(img, 0, 0, size, size, base, noise, seed)
    # внутренняя фаска: подсветка сверху-слева, тень снизу-справа
    for i in range(1, 1 + light_w):
        for k in range(i, size - i):
            put(img, k, i, light)
            put(img, i, k, light)
    for i in range(1, 1 + dark_w):
        for k in range(i, size - i):
            put(img, k, size - 1 - i, dark)
            put(img, size - 1 - i, k, dark)
    frame(img, 0, 0, size, size, outline)
    if corners:
        round_corners(img)
    return img


def make_panel():
    # светлая рамка инвентаря
    return bevel_panel(16, hx("#14130f"), hx("#fbf9f2"), hx("#c4c0b6"), hx("#7a7569"), 11, 0.035)


def make_panel_dark():
    return bevel_panel(16, hx("#07080a"), hx("#4a525b"), hx("#2b3036"), hx("#14171b"), 12, 0.07, light_w=1, dark_w=1)


def make_button(top, mid, bottom, outline, hi=None):
    """16x20: верхняя фаска, толстая нижняя тень (как у кнопок Minecraft)."""
    w, h = 16, 20
    img = new(w, h)
    rect(img, 0, 0, w, h, mid)
    r = random.Random(77)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            put(img, x, y, shade(mid, 1.0 + (r.random() - 0.5) * 0.05))
    for x in range(1, w - 1):
        put(img, x, 1, top)
        put(img, x, h - 2, bottom)
        put(img, x, h - 3, shade(bottom, 1.12))
    for y in range(1, h - 2):
        put(img, 1, y, top)
        put(img, w - 2, y, shade(bottom, 1.18))
    frame(img, 0, 0, w, h, outline)
    if hi:
        frame(img, 0, 0, w, h, hi)
        frame(img, 1, 1, w - 2, h - 2, shade(hi, 0.8))
    round_corners(img)
    return img


def make_field(focus=False):
    img = new(16, 16)
    rect(img, 0, 0, 16, 16, hx("#0a0b0d"))
    rect(img, 2, 2, 12, 12, hx("#17191c"))
    frame(img, 0, 0, 16, 16, hx("#bfd18c") if focus else hx("#7b828a"))
    frame(img, 1, 1, 14, 14, hx("#000000"))
    return img


def make_row(sel=False):
    img = new(16, 16)
    rect(img, 0, 0, 16, 16, hx("#000000", 150))
    if sel:
        rect(img, 0, 0, 16, 16, hx("#2b3328", 220))
        frame(img, 0, 0, 16, 16, hx("#bfd18c"))
        frame(img, 1, 1, 14, 14, hx("#000000"))
    else:
        frame(img, 0, 0, 16, 16, hx("#3a3f45", 200))
    return img


def make_tooltip():
    img = new(12, 12)
    rect(img, 0, 0, 12, 12, hx("#120a1e", 238))
    frame(img, 1, 1, 10, 10, hx("#3a1f6b"))
    frame(img, 2, 2, 8, 8, hx("#27124a"))
    rect(img, 3, 3, 6, 6, hx("#120a1e", 238))
    for (x, y) in ((0, 0), (11, 0), (0, 11), (11, 11)):
        put(img, x, y, (0, 0, 0, 0))
    return img


def make_slot():
    """18x18 слот: тёмное углубление с фаской, как в инвентаре Minecraft."""
    img = new(18, 18)
    rect(img, 0, 0, 18, 18, hx("#8a867c"))
    rect(img, 1, 1, 16, 16, hx("#8b8b8b"))
    for i in range(18):
        put(img, i, 0, hx("#373737"))
        put(img, 0, i, hx("#373737"))
        put(img, i, 17, hx("#ffffff"))
        put(img, 17, i, hx("#ffffff"))
    put(img, 17, 0, hx("#8b8b8b"))
    put(img, 0, 17, hx("#8b8b8b"))
    for i in range(1, 17):
        put(img, i, 1, hx("#555555")) if False else None
    return img


def make_hotbar():
    w, h = 182, 22
    img = new(w, h)
    rect(img, 0, 0, w, h, hx("#1a1c1f", 215))
    frame(img, 0, 0, w, h, hx("#050505"))
    frame(img, 1, 1, w - 2, h - 2, hx("#5b6168"))
    # слоты 16x16 с ячейкой 20 px: x = 3 + 20 i
    for i in range(9):
        x = 3 + i * 20
        rect(img, x - 1, 2, 18, 18, hx("#0b0c0d", 190))
        frame(img, x - 1, 2, 18, 18, hx("#3b4046", 230))
    return img


def make_hotbar_sel():
    img = new(24, 24)
    frame(img, 0, 0, 24, 24, hx("#050505"))
    frame(img, 1, 1, 22, 22, hx("#f4f1e4"))
    frame(img, 2, 2, 20, 20, hx("#bfd18c"))
    frame(img, 3, 3, 18, 18, hx("#050505", 0))
    for (x, y) in ((0, 0), (23, 0), (0, 23), (23, 23)):
        put(img, x, y, (0, 0, 0, 0))
    return img


# ----------------------------------------------------------------------------- сердца и еда
HEART = [
    ".XX...XX.",
    "XXXX.XXXX",
    "XXXXXXXXX",
    "XXXXXXXXX",
    "XXXXXXXXX",
    ".XXXXXXX.",
    "..XXXXX..",
    "...XXX...",
    "....X....",
]


def heart(kind):
    """kind: 'bg' (пустой контейнер), 'full', 'half', 'flash' (белая вспышка контейнера)."""
    img = new(9, 9)
    outline = hx("#1a0505")
    for y, row in enumerate(HEART):
        for x, c in enumerate(row):
            if c != "X":
                continue
            put(img, x, y, outline)
    # внутренность
    def inner(x, y):
        if not (0 <= y < 9 and 0 <= x < 9):
            return False
        return HEART[y][x] == "X"

    for y in range(9):
        for x in range(9):
            if not inner(x, y):
                continue
            edge = not (inner(x - 1, y) and inner(x + 1, y) and inner(x, y - 1) and inner(x, y + 1))
            if edge:
                continue
            if kind == "bg":
                put(img, x, y, hx("#3a2a2a"))
            elif kind == "flash":
                put(img, x, y, hx("#ffffff"))
            else:
                left = x <= 3
                filled = kind == "full" or (kind == "half" and left)
                if filled:
                    c = hx("#e5232b")
                    if y >= 5:
                        c = hx("#b3121c")
                    put(img, x, y, c)
                else:
                    put(img, x, y, hx("#3a2a2a"))
    if kind in ("full", "half"):
        put(img, 2, 2, hx("#ffd0d0"))
        put(img, 3, 1, hx("#ff8d8d"))
        put(img, 1, 2, hx("#ff8d8d"))
        if kind == "full":
            pass
    if kind == "flash":
        for y in range(9):
            for x in range(9):
                if inner(x, y) and (x + y) % 5 == 0:
                    put(img, x, y, hx("#ffd7d7"))
    return img


def drumstick(kind):
    """Куриная ножка 9x9: мясо справа-сверху, косточка слева-снизу."""
    mask = [
        "....XXX..",
        "...XXXXX.",
        "..XXXXXXX",
        "..XXXXXXX",
        "..XXXXXX.",
        ".XXXXXX..",
        "XXXXX....",
        "XX.XX....",
        ".XX......",
    ]
    meat = {(x, y) for y in range(0, 6) for x in range(2, 9) if mask[y][x] == "X"}
    bone = {(x, y) for y in range(9) for x in range(9) if mask[y][x] == "X"} - meat
    img = new(9, 9)
    outline = hx("#240f05")
    allpx = meat | bone

    def inside(x, y):
        return (x, y) in allpx

    for (x, y) in allpx:
        put(img, x, y, outline)
    for (x, y) in allpx:
        edge = not (inside(x - 1, y) and inside(x + 1, y) and inside(x, y - 1) and inside(x, y + 1))
        if edge:
            continue
        if kind == "bg":
            put(img, x, y, hx("#33261c"))
            continue
        if kind == "flash":
            put(img, x, y, hx("#fff2dd"))
            continue
        filled = kind == "full" or (kind == "half" and (x + (8 - y)) >= 8 - 1 and x >= 4)
        if kind == "half":
            filled = x >= 4
        if (x, y) in meat:
            c = hx("#c8742a") if (x + y) % 3 else hx("#d98a3a")
            if y <= 2:
                c = hx("#eba95a")
            put(img, x, y, c if filled else hx("#33261c"))
        else:
            put(img, x, y, hx("#f3efe4") if filled else hx("#33261c"))
    # корочка/блик
    if kind in ("full", "half"):
        if kind == "full" or True:
            put(img, 5, 1, hx("#ffdc9a")) if kind == "full" else None
    # кость: два бугорка
    return img


# ----------------------------------------------------------------------------- прогресс
def arrow(full):
    w, h = 22, 15
    img = new(w, h)
    body = hx("#ffffff") if full else hx("#8b8b8b")
    shadow = hx("#c9d99a") if full else hx("#555555")
    rect(img, 0, 5, 16, 5, body)
    for i in range(8):
        rect(img, 14 + i // 1, 0 + i, 1, 15 - 2 * i if False else max(0, 15 - 2 * i), body) if False else None
    # наконечник: треугольник
    for i in range(8):
        x = 14 + i
        half = 7 - i
        rect(img, x, 7 - half, 1, half * 2 + 1, body)
    rect(img, 0, 9, 16, 1, shadow)
    return img


def flame(full):
    img = new(14, 14)
    shape = [
        "......X.......",
        "......XX......",
        ".....XXX......",
        ".....XXXX.....",
        "....XXXXX..X..",
        "...XXXXXXX.XX.",
        "..XXXXXXXXXXX.",
        "..XXXXXXXXXXX.",
        ".XXXXXXXXXXXXX",
        ".XXXXXXXXXXXXX",
        ".XXXXXXXXXXXXX",
        "..XXXXXXXXXXX.",
        "..XXXXXXXXXX..",
        "...XXXXXXXX...",
    ]
    for y, row in enumerate(shape):
        for x, c in enumerate(row):
            if c != "X":
                continue
            if full:
                col = hx("#ff6a1a")
                if y > 5:
                    col = hx("#ffa21f")
                if y > 9 and 3 < x < 10:
                    col = hx("#ffe27a")
            else:
                col = hx("#4a4a4a")
            put(img, x, y, col)
    return img


# ----------------------------------------------------------------------------- прочее
def crosshair():
    img = new(15, 15)
    for i in range(15):
        if abs(i - 7) > 1:
            put(img, i, 7, hx("#ffffff"))
            put(img, 7, i, hx("#ffffff"))
    return img


def scroll_knob():
    img = new(6, 8)
    rect(img, 0, 0, 6, 8, hx("#808890"))
    frame(img, 0, 0, 6, 8, hx("#000000"))
    for i in range(1, 5):
        put(img, i, 1, hx("#c9d0d6"))
    return img


def scroll_track():
    img = new(6, 8)
    rect(img, 0, 0, 6, 8, hx("#000000", 200))
    return img


def bg_tile():
    """Тёмная земляная плитка для фона меню."""
    img = new(16, 16)
    r = random.Random(5)
    pal = [hx(c) for c in ("#3b2c20", "#43332a", "#352718", "#4a382b", "#2f2218")]
    for y in range(16):
        for x in range(16):
            put(img, x, y, r.choice(pal))
    for _ in range(14):
        put(img, r.randrange(16), r.randrange(16), hx("#5b5b5b"))
    for _ in range(6):
        put(img, r.randrange(16), r.randrange(16), hx("#262626"))
    return img


def world_icon():
    """32x32 иконка мира по умолчанию: небо, солнце, холмы, трава."""
    img = new(32, 32)
    for y in range(32):
        t = y / 31.0
        c = (int(95 + 90 * t), int(160 + 60 * t), int(235 + 10 * t), 255)
        for x in range(32):
            put(img, x, y, c)
    for (x, y) in ((24, 6), (25, 6), (24, 7), (25, 7), (23, 6), (26, 6), (24, 5), (25, 8), (24, 8), (23, 7), (26, 7), (25, 5)):
        put(img, x, y, hx("#fff3a0"))
    for (x, y) in ((24, 6), (25, 6), (24, 7), (25, 7)):
        put(img, x, y, hx("#ffffff"))
    # облако
    for (x, y) in ((6, 8), (7, 8), (8, 8), (9, 8), (7, 7), (8, 7), (9, 7), (5, 9), (6, 9), (7, 9), (8, 9), (9, 9), (10, 9)):
        put(img, x, y, hx("#ffffff"))
    # холмы
    r = random.Random(3)
    for x in range(32):
        top = 19 + int(3 * (1 if (x // 6) % 2 == 0 else 0) + (x % 6 if (x // 6) % 2 else 0) * 0)
        top = 18 + abs(((x + 4) % 20) - 10) // 3
        for y in range(top, 32):
            if y == top:
                c = hx("#7fbf4a")
            elif y < top + 3:
                c = hx("#5aa032") if (x + y) % 3 else hx("#69ae3b")
            elif y < top + 9:
                c = hx("#8a5a34") if (x * 7 + y * 3) % 5 else hx("#7a4c2b")
            else:
                c = hx("#7d7d7d") if (x + y) % 4 else hx("#6f6f6f")
            put(img, x, y, c)
    frame(img, 0, 0, 32, 32, hx("#000000"))
    return img


def player_figure():
    """Фигурка игрока 16x32 (вид спереди) для окна инвентаря."""
    img = new(16, 32)
    skin, skin_d = hx("#e8b98f"), hx("#c99569")
    hair, hair_d = hx("#4a2f1a"), hx("#33200f")
    shirt, shirt_d = hx("#86b84a"), hx("#5f8d31")
    pants, pants_d = hx("#3c4f8a"), hx("#2b3a68")
    boots = hx("#3a2c22")
    out = hx("#0e0e0e")

    def box(x, y, w, h, c, d=None):
        rect(img, x, y, w, h, c)
        if d:
            rect(img, x + w - 1, y, 1, h, d)
            rect(img, x, y + h - 1, w, 1, d)

    # голова 8x8 (x 4..11, y 0..7)
    box(4, 0, 8, 8, skin, skin_d)
    rect(img, 4, 0, 8, 3, hair)
    rect(img, 4, 3, 1, 2, hair)
    rect(img, 11, 3, 1, 2, hair_d)
    rect(img, 4, 2, 8, 1, hair_d)
    put(img, 6, 4, hx("#ffffff"))
    put(img, 9, 4, hx("#ffffff"))
    put(img, 7, 4, hx("#2a5aa0"))
    put(img, 10, 4, hx("#2a5aa0"))
    rect(img, 7, 6, 2, 1, hx("#a8664a"))
    # тело 8x12 (y 8..19), руки по 4 (x 0..3 и 12..15)
    box(4, 8, 8, 12, shirt, shirt_d)
    rect(img, 6, 8, 4, 1, skin_d)
    box(0, 8, 4, 12, shirt, shirt_d)
    box(12, 8, 4, 12, shirt, shirt_d)
    rect(img, 0, 17, 4, 3, skin)
    rect(img, 12, 17, 4, 3, skin)
    # ноги (y 20..31)
    box(4, 20, 4, 12, pants, pants_d)
    box(8, 20, 4, 12, pants, pants_d)
    rect(img, 4, 28, 4, 4, boots)
    rect(img, 8, 28, 4, 4, boots)
    # контур
    solid = {(x, y) for y in range(32) for x in range(16) if img.getpixel((x, y))[3] > 0}
    for (x, y) in solid:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in solid:
                put(img, nx, ny, out) if 0 <= nx < 16 and 0 <= ny < 32 else None
    return img


def logo():
    """Логотип OPTICRAFT: каменные блоки-буквы с фаской и тенью."""
    text = "OPTICRAFT"
    cell = 4              # размер «большого пикселя»
    gap = 1               # промежуток между буквами в большых пикселях
    letters = []
    total_w = 0
    for ch in text:
        rows = F[ch]
        w = max(len(r) for r in rows)
        letters.append((ch, rows, w))
        total_w += w + gap
    total_w -= gap
    W = total_w * cell + 6
    H = 7 * cell + 6
    img = new(W, H)
    shadow = new(W, H)
    r = random.Random(21)
    cx = 0
    for idx, (ch, rows, w) in enumerate(letters):
        green = idx >= 4
        base = hx("#7aa843") if green else hx("#9a9a9e")
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c != "#":
                    continue
                px = (cx + x) * cell
                py = y * cell
                col = shade(base, 0.93 + r.random() * 0.14)
                # блок cell x cell с фаской
                rect(img, px, py, cell, cell, col)
                for k in range(cell):
                    put(img, px + k, py, shade(col, 1.25))
                    put(img, px, py + k, shade(col, 1.18))
                    put(img, px + k, py + cell - 1, shade(col, 0.62))
                    put(img, px + cell - 1, py + k, shade(col, 0.68))
                if r.random() < 0.18:
                    put(img, px + 2, py + 2, shade(col, 0.82))
        cx += w + gap
    # тень и контур
    solid = {(x, y) for y in range(H) for x in range(W) if img.getpixel((x, y))[3] > 0}
    out = new(W + 4, H + 5)
    for (x, y) in solid:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                put(out, x + 1 + dx, y + 1 + dy, hx("#111418"))
        put(out, x + 3, y + 3, hx("#000000", 120))
        put(out, x + 2, y + 3, hx("#000000", 120))
        put(out, x + 3, y + 2, hx("#000000", 120))
    for (x, y) in solid:
        put(out, x + 1, y + 1, img.getpixel((x, y)))
    return out


def make_slider_track():
    img = new(16, 20)
    rect(img, 0, 0, 16, 20, hx("#000000"))
    rect(img, 1, 1, 14, 18, hx("#25282c"))
    frame(img, 0, 0, 16, 20, hx("#000000"))
    frame(img, 1, 1, 14, 18, hx("#5b6168"))
    round_corners(img)
    return img


def make_knob(hover=False):
    return make_button(hx("#d5dbe0"), hx("#9aa3ab"), hx("#4c535a"), hx("#000000"), hx("#bfd18c") if hover else None)


# ----------------------------------------------------------------------------- упаковка
def build():
    s = {}
    s["white"] = new(2, 2, (255, 255, 255, 255))
    s.update(font_sprites())
    s["panel"] = make_panel()
    s["panel_dark"] = make_panel_dark()
    s["btn"] = make_button(hx("#a7aeb5"), hx("#6f767d"), hx("#3b4046"), hx("#000000"))
    s["btn_hover"] = make_button(hx("#c9d8a2"), hx("#7f9060"), hx("#46512f"), hx("#000000"), hx("#e8f2c4"))
    s["btn_off"] = make_button(hx("#5b6066"), hx("#43474c"), hx("#2c2f33"), hx("#000000"))
    s["field"] = make_field(False)
    s["field_focus"] = make_field(True)
    s["row"] = make_row(False)
    s["row_sel"] = make_row(True)
    s["tooltip"] = make_tooltip()
    s["slot"] = make_slot()
    s["hotbar"] = make_hotbar()
    s["hotbar_sel"] = make_hotbar_sel()
    for k in ("bg", "full", "half", "flash"):
        s["heart_" + k] = heart(k)
        s["food_" + k] = drumstick(k)
    s["arrow_empty"] = arrow(False)
    s["arrow_full"] = arrow(True)
    s["flame_empty"] = flame(False)
    s["flame_full"] = flame(True)
    s["crosshair"] = crosshair()
    s["scroll_knob"] = scroll_knob()
    s["scroll_track"] = scroll_track()
    s["bg_tile"] = bg_tile()
    s["world_icon"] = world_icon()
    s["player"] = player_figure()
    s["logo"] = logo()
    s["slider_track"] = make_slider_track()
    s["knob"] = make_knob(False)
    s["knob_hover"] = make_knob(True)
    return s


def pack(sprites):
    """Простая полочная упаковка по убыванию высоты."""
    order = sorted(sprites.items(), key=lambda kv: (-kv[1].height, -kv[1].width, kv[0]))
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    manifest = {"name": "ui_main", "texture": "../texture/ui_atlas.png", "sprites": {}}
    x = y = shelf_h = 0
    pad = 1
    for name, img in order:
        w, h = img.size
        if x + w + pad > ATLAS_SIZE:
            x = 0
            y += shelf_h + pad
            shelf_h = 0
        if y + h > ATLAS_SIZE:
            raise SystemExit("ui atlas overflow at " + name)
        atlas.paste(img, (x, y))
        manifest["sprites"][name] = {"x": x, "y": y, "w": w, "h": h}
        x += w + pad
        shelf_h = max(shelf_h, h)
    return atlas, manifest, y + shelf_h


def main():
    sprites = build()
    atlas, manifest, used_h = pack(sprites)
    tex = os.path.join(ROOT, "assets/texture/ui_atlas.png")
    atlas.save(tex)
    with open(os.path.join(ROOT, "assets/atlases/ui_main.atlas.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
        f.write("\n")
    print("ui sprites:", len(sprites), "used height:", used_h)


if __name__ == "__main__":
    main()
