"""Procedural, tileable textures for Borso Simulator HD.
Run inside Blender (uses numpy + bpy to save PNGs into docs/textures/)."""
import os
import numpy as np
import bpy

ROOT = r"C:\Coding\borso-simulator"
OUT = os.path.join(ROOT, "docs", "textures")
os.makedirs(OUT, exist_ok=True)


def fnoise(h, w, sigma, seed):
    """Periodic gaussian-filtered noise in [0,1]."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((h, w)))
    ky = np.fft.fftfreq(h)[:, None]
    kx = np.fft.fftfreq(w)[None, :]
    f *= np.exp(-2 * np.pi ** 2 * sigma ** 2 * (kx ** 2 + ky ** 2))
    n = np.real(np.fft.ifft2(f))
    n -= n.min()
    return n / (n.max() + 1e-9)


def save(name, rgb):
    """rgb: (h, w, 3) float in [0,1], row 0 = top of the image."""
    h, w, _ = rgb.shape
    img = bpy.data.images.get(name) or bpy.data.images.new(name, w, h, alpha=False)
    if tuple(img.size) != (w, h):
        img.scale(w, h)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(rgba[::-1].ravel())  # blender rows go bottom -> top
    img.filepath_raw = os.path.join(OUT, name + ".png")
    img.file_format = 'PNG'
    img.save()
    return img


def gray(v):
    return np.repeat(v[..., None], 3, axis=2)


def tex_grass():
    n = 256
    v = 0.86 + 0.10 * (fnoise(n, n, 7, 1) - 0.5) + 0.08 * (fnoise(n, n, 1.2, 2) - 0.5)
    rng = np.random.default_rng(3)
    for _ in range(2600):  # little blades
        x, y, l = rng.integers(0, n), rng.integers(0, n), rng.integers(2, 6)
        c = rng.uniform(-0.12, 0.10)
        for k in range(l):
            v[(y - k) % n, (x + (k // 3)) % n] += c
    rgb = gray(v)
    rgb[..., 0] *= 1.0 + 0.04 * (fnoise(n, n, 10, 4) - 0.5)
    rgb[..., 2] *= 0.97
    return save("grass", rgb)


def tex_asphalt(name, main):
    h, w = 512, 128
    v = 0.36 + 0.09 * (fnoise(h, w, 0.8, 10) - 0.5) + 0.07 * (fnoise(h, w, 9, 11) - 0.5)
    u = (np.arange(w) + 0.5) / w
    track = np.exp(-((u - 0.27) / 0.07) ** 2) + np.exp(-((u - 0.73) / 0.07) ** 2)
    v -= 0.035 * track[None, :]
    rgb = gray(v)
    rgb[..., 2] *= 1.03
    line = np.array([0.93, 0.92, 0.86])
    for a, b in ((0.04, 0.075), (0.925, 0.96)):
        m = (u >= a) & (u <= b)
        rgb[:, m] = line * (0.92 + 0.08 * fnoise(h, w, 1, 12)[:, m, None])
    if main:  # dashed centre line: 4.5 m painted every 9 m
        m = (u >= 0.485) & (u <= 0.515)
        rgb[: h // 2, m] = line
    return save(name, rgb)


def tex_cobble():
    n, s = 256, 16
    rng = np.random.default_rng(20)
    yy, xx = np.mgrid[0:n, 0:n]
    row = yy // s
    off = (row % 2) * (s // 2)
    col = ((xx + off) // s) % (n // s)
    lx = ((xx + off) % s) - s / 2 + 0.5
    ly = (yy % s) - s / 2 + 0.5
    d = np.maximum(np.abs(lx), np.abs(ly)) / (s / 2)
    bright = rng.uniform(0.78, 1.0, (n // s, n // s))[row % (n // s), col]
    stone = bright * (1 - 0.25 * np.clip((d - 0.55) / 0.35, 0, 1)) * (0.94 + 0.12 * fnoise(n, n, 1, 21))
    v = np.where(d > 0.86, 0.42, stone)
    rgb = gray(v)
    rgb[..., 0] *= 1.03
    rgb[..., 2] *= 0.95
    return save("cobble", rgb)


def tex_plaster():
    n = 256
    v = 0.92 + 0.07 * (fnoise(n, n, 22, 30) - 0.5) + 0.035 * (fnoise(n, n, 1.5, 31) - 0.5)
    stains = fnoise(n, n, 10, 32)
    v -= 0.06 * np.clip((stains - 0.7) / 0.3, 0, 1)
    return save("plaster", gray(v))


def tex_stone():
    n = 256
    rng = np.random.default_rng(40)
    v = np.zeros((n, n))
    y = 0
    while y < n:
        rh = int(rng.integers(18, 34)) if n - y > 40 else n - y
        x0 = int(rng.integers(0, 30))
        x = x0
        while x < x0 + n:
            bw = min(int(rng.integers(26, 60)), x0 + n - x)
            if x0 + n - x - bw < 14:  # avoid slivers at the wrap-around
                bw = x0 + n - x
            b = rng.uniform(0.74, 0.95)
            ys, xs = np.mgrid[y:y + rh, x:x + bw]
            ly = (ys - y) / rh
            lx = (xs - x) / bw
            edge = np.minimum(np.minimum(ly, 1 - ly) * rh, np.minimum(lx, 1 - lx) * bw)
            edge = edge + 2.0 * (fnoise(rh, bw, 1.5, int(b * 1e6)) - 0.5)
            val = np.where(edge < 1.6, 0.56, b * (1 - 0.22 * np.clip((7 - edge) / 7, 0, 1)))
            v[ys % n, xs % n] = val
            x += bw
        y += rh
    v *= 0.9 + 0.2 * fnoise(n, n, 1.2, 41)
    rgb = gray(v)
    rgb[..., 0] *= 1.02
    return save("stone", rgb)


def tex_roof():
    """Coppi veneti: alternating convex/concave clay channels, staggered overlapping rows."""
    n, cw, rh = 256, 16, 32
    rng = np.random.default_rng(50)
    yy, xx = np.mgrid[0:n, 0:n]
    colx = xx // cw
    lx = (xx % cw + 0.5) / cw
    convex = (colx % 2 == 0)
    yoff = np.where(convex, 0, rh // 2)
    yy2 = (yy + yoff) % n
    rowi = yy2 // rh
    ly = (yy2 % rh + 0.5) / rh
    s = np.sin(lx * np.pi)
    prof = np.where(convex, 0.58 + 0.42 * s ** 0.6, 0.78 - 0.28 * s)
    edge = np.where(convex, 0.80 + 0.12 * s, 0.86 - 0.06 * s)  # rounded lower lip of each tile
    lip = np.where(ly > edge, 0.62, 1.0) * (1 - 0.25 * np.clip((ly - (edge - 0.12)) / 0.12, 0, 1) * (ly <= edge))
    key = rowi * 97 + colx
    tint = rng.uniform(0.84, 1.06, 4096)[key % 4096]
    warm = rng.uniform(-0.01, 0.08, 4096)[(key * 7 + 3) % 4096]
    v = prof * lip * tint * (0.93 + 0.12 * fnoise(n, n, 1, 51))
    rgb = gray(v)
    rgb[..., 0] *= 1 + warm
    rgb[..., 1] *= 1 + warm * 0.3
    rgb[..., 2] *= 1 - warm
    return save("roof", rgb)


def tex_wood():
    n, pw = 256, 32
    yy, xx = np.mgrid[0:n, 0:n]
    rng = np.random.default_rng(60)
    plank = xx // pw
    b = rng.uniform(0.78, 1.0, n // pw)[plank]
    grain = fnoise(n, n * 1, 1.0, 61)
    grain = np.roll(grain, 0, 0)
    g2 = fnoise(n, n, 6, 62)
    v = b * (0.86 + 0.14 * grain[:, :] * 0.6 + 0.1 * g2)
    v = np.where((xx % pw) < 2, 0.35, v)
    rgb = gray(v)
    rgb[..., 0] *= 1.04
    rgb[..., 2] *= 0.92
    return save("wood", rgb)


def tex_window():
    """Window with stone frame, white mullions and dark glass; plus emissive mask."""
    h, w = 256, 128
    yy, xx = np.mgrid[0:h, 0:w]
    u = (xx + 0.5) / w
    v = 1 - (yy + 0.5) / h  # v up
    fr = 0.13  # stone frame (u) ; vertical equivalent in v
    frv = fr * w / h
    frame = (u < fr) | (u > 1 - fr) | (v < frv) | (v > 1 - frv)
    mull = (np.abs(u - 0.5) < 0.035) | (np.abs(v - 0.62) < 0.018)
    inner = (u > fr + 0.035) & (u < 1 - fr - 0.035) & (v > frv + 0.017) & (v < 1 - frv - 0.017)
    glass = inner & ~mull
    rgb = np.zeros((h, w, 3))
    stone = np.array([0.93, 0.91, 0.86]) * (0.92 + 0.12 * fnoise(h, w, 1.5, 70))[..., None]
    rgb[:] = np.array([0.96, 0.96, 0.94])  # white wooden casement
    rgb[frame] = stone[frame]
    refl = (0.16 + 0.22 * np.clip(v * 1.4 - (u * 0.6), 0, 1))[..., None]
    gl = np.concatenate([refl * 0.85, refl * 0.95, refl * 1.15], axis=2)
    rgb[glass] = gl[glass]
    save("window", rgb)
    em = np.zeros((h, w, 3))
    warm = np.array([1.0, 0.78, 0.45]) * (0.85 + 0.15 * (1 - v))[..., None]
    em[glass] = warm[glass]
    return save("window_em", em)


def tex_detail():
    """Left half: louvered shutter (scuro). Right half: panelled door. Grayscale, tinted by vertex colour."""
    n = 256
    rgb = np.ones((n, n, 3))
    yy, xx = np.mgrid[0:n, 0:n]
    # shutter: u 0..0.5
    sx = xx[:, :128] / 128.0
    sy = yy[:, :128] / 256.0
    border = (sx < 0.08) | (sx > 0.92) | (sy < 0.04) | (sy > 0.96)
    slat = ((sy * 32) % 1.0)
    sh = np.where(border, 0.92, 0.72 + 0.28 * slat)
    sh = np.where((np.abs(sy - 0.5) < 0.02) & ~border, 0.92, sh)
    rgb[:, :128] = gray(sh * (0.95 + 0.08 * fnoise(n, 128, 1, 80)))
    # door: u 0.5..1
    dx = (xx[:, 128:] - 128) / 128.0
    dy = yy[:, 128:] / 256.0
    d = np.full(dx.shape, 0.9)
    for (x0, x1, y0, y1) in ((0.14, 0.46, 0.08, 0.46), (0.54, 0.86, 0.08, 0.46), (0.14, 0.46, 0.54, 0.92), (0.54, 0.86, 0.54, 0.92)):
        inside = (dx > x0) & (dx < x1) & (dy > y0) & (dy < y1)
        e = np.minimum(np.minimum(dx - x0, x1 - dx), np.minimum(dy - y0, y1 - dy))
        d = np.where(inside, np.where(e < 0.025, 0.62, 0.78), d)
    d = np.where((np.abs(dx - 0.5) < 0.012), 0.55, d)
    knob = ((dx - 0.42) ** 2 * 4 + (dy - 0.52) ** 2) < 0.0006
    d = np.where(knob, 1.0, d)
    grain = 0.92 + 0.1 * fnoise(n, 128, 1.0, 81)
    drgb = gray(d * grain)
    drgb[knob] = [1.0, 0.85, 0.4]
    rgb[:, 128:] = drgb
    return save("detail", rgb)


def tex_tile():
    """Ceramic floor tiles (4x4 per texture) with grout and slight per-tile variation."""
    n, t = 256, 64
    rng = np.random.default_rng(90)
    yy, xx = np.mgrid[0:n, 0:n]
    ti, tj = yy // t, xx // t
    lx, ly = (xx % t) / t, (yy % t) / t
    e = np.minimum(np.minimum(lx, 1 - lx), np.minimum(ly, 1 - ly))
    b = rng.uniform(0.9, 1.0, (n // t, n // t))[ti, tj]
    v = np.where(e < 0.035, 0.55, b * (0.97 + 0.05 * fnoise(n, n, 2, 91)) * (1 - 0.08 * np.clip((0.12 - e) / 0.12, 0, 1)))
    hl = np.clip(1 - np.hypot(lx - 0.3, ly - 0.3) * 2.2, 0, 1) * 0.05  # glaze highlight
    return save("tile", gray(np.clip(v + hl * (e >= 0.035), 0, 1)))


def build_all():
    tex_grass(); tex_asphalt("asphalt_main", True); tex_asphalt("asphalt_small", False)
    tex_cobble(); tex_plaster(); tex_stone(); tex_roof(); tex_wood(); tex_window(); tex_detail(); tex_tile()
    return sorted(os.listdir(OUT))
