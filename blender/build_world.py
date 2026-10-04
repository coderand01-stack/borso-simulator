"""Borso Simulator HD - world builder.

Reads tools/out/layout.json (dumped from the original game by tools/instrumented.html)
and rebuilds the whole map in Blender with richer low-poly geometry, then it can be
exported to docs/models/world.glb.

Coordinates: everything is generated in GAME space (three.js, Y up) and converted to
Blender space (Z up) only when meshes are created: (x, y, z)game -> (x, -z, y)blender.
The glTF exporter converts back, so the .glb lines up 1:1 with the game's H(x, z).

Run inside Blender:
    g = {}; exec(open(r"C:\\Coding\\borso-simulator\\blender\\build_world.py").read(), g); g['build']()
"""
import bpy, json, math, os
import numpy as np

ROOT = r"C:\Coding\borso-simulator"
TEXDIR = os.path.join(ROOT, "docs", "textures")
L = json.load(open(os.path.join(ROOT, "tools", "out", "layout.json"), encoding="utf-8"))

# ============================================================== terrain height (port of the JS)
GT = dict(cx=-106.0, cz=-345.0, hx=52.0, hz=27.0, f=30.0)


def terrW(x, z):
    x = np.asarray(x, float); z = np.asarray(z, float)
    dx = np.maximum(np.abs(x - GT['cx']) - GT['hx'], 0)
    dz = np.maximum(np.abs(z - GT['cz']) - GT['hz'], 0)
    d = np.hypot(dx, dz)
    s = np.clip(1 - d / GT['f'], 0, 1)
    return np.where(d >= GT['f'], 0.0, s * s * (3 - 2 * s))


def Hbase(x, z):
    x = np.asarray(x, float); z = np.asarray(z, float)
    n = np.sin(x * 0.045 + 1.3) * np.cos(z * 0.05) * 0.6 + np.sin(x * 0.013 - z * 0.021) * 1.2
    t = -45 - z
    H105 = 105 * 0.16 + 105 * 105 * 0.0011
    H215 = H105 + 0.39 * 110 - 110 * 110 * (0.19 / 220)
    d = t - 105
    e = t - 327
    hm = np.where(t <= 105, t * 0.16 + t * t * 0.0011,
         np.where(t <= 215, H105 + 0.39 * d - d * d * (0.19 / 220),
         np.where(t <= 327, H215 + 0.2 * (t - 215), H215 + 0.2 * 112 + 0.2 * e + 0.0035 * e * e)))
    hm = hm + n * np.minimum(1, t / 40) * 3
    k = np.clip((-372 - z) / 200, 0, 1); k2 = np.clip((-372 - z) / 140, 0, 1)
    ks = k * k * (3 - 2 * k); g = k2 * k2 * (3 - 2 * k2)
    extra = (np.sin(x * 0.008) * 60 + np.sin(x * 0.021 + 2) * 25 + np.sin(x * 0.05 + z * 0.03) * 8) * ks
    extra = extra + 170 * np.exp(-((x + 40) ** 2 / 70000 + (z + 640) ** 2 / 50000)) * g
    hm = hm + np.where(z < -372, extra, 0)
    h = np.where(z < -45, hm, n * 0.25)
    tx = x - 300; h = h + np.where(x > 300, tx * 0.3 + tx * tx * 0.004, 0)
    tx = -472 - x; h = h + np.where(x < -472, tx * 0.3 + tx * tx * 0.004, 0)
    tz = z - 250; h = h + np.where(z > 250, tz * 0.12 + np.sin(x * 0.03) * tz * 0.05, 0)
    # (HD) above 500 m the massif flattens into a plateau; the Sacrario stands on a levelled square at the top
    h = np.where(h > 500, 500 + 40 * (1 - np.exp(-np.maximum(h - 500, 0) / 40)), h)
    if SAC['y'] is not None:
        d = np.hypot(x - SAC['x'], z - SAC['z']); t = np.clip((SAC['r1'] - d) / (SAC['r1'] - SAC['r0']), 0, 1)
        h = h + np.where(z < -560, (SAC['y'] - h) * t * t * (3 - 2 * t), 0)
    return h


SAC = dict(x=-40.0, z=-640.0, r0=34.0, r1=52.0, y=None)  # same as SAC in the game (tools/make_hd.py)
SAC['y'] = float(Hbase(SAC['x'], SAC['z']))  # on the crest: seen from the town it stands against the sky


GT['y'] = float(Hbase(GT['cx'], -322))


def H(x, z):
    h = Hbase(x, z)
    x = np.asarray(x, float); z = np.asarray(z, float)
    w = terrW(x, z)
    m = (z < -280) & (z > -410) & (x > -192) & (x < -20) & (w > 0)
    r = np.where(m, h + (GT['y'] - h) * w, h)
    return float(r) if r.ndim == 0 else r


def check_heights():
    s = np.array(L['hsamples'])
    err = np.abs(H(s[:, 0], s[:, 1]) - s[:, 2])
    return float(err.max())


# ============================================================== small helpers
def hx(c):
    c = int(c)
    return ((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0


def mul(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def hr(*k):
    """Deterministic hash -> [0,1)."""
    s = 0.0
    for i, v in enumerate(k):
        s += (float(v) + 0.123) * (12.9898 + i * 78.233)
    return (math.sin(s) * 43758.5453) % 1.0


def norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sc(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def newell(p):
    nx = ny = nz = 0.0
    for i in range(len(p)):
        a = p[i]; b = p[(i + 1) % len(p)]
        nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1])
    return norm((nx, ny, nz))


def centroid(p):
    n = len(p)
    return (sum(q[0] for q in p) / n, sum(q[1] for q in p) / n, sum(q[2] for q in p) / n)


# ============================================================== geometry buffers / chunks
CHUNK = 200.0
X0, Z0 = -700.0, -780.0
NCX, NCZ = 7, 6
UVSCALE = {'M_Plaster': 3.0, 'M_Stone': 2.6, 'M_Roof': 2.2, 'M_Wood': 2.0, 'M_Cobble': 4.0, 'M_Terrain': 8.0}
NO_AO = {'M_Terrain', 'M_RoadMain', 'M_RoadSmall', 'M_Glow', 'M_Window', 'M_WindowLit', 'M_LampGlow', 'M_Cobble'}


class Buf:
    __slots__ = ('P', 'C', 'UV', 'F', 'A')

    def __init__(self):
        self.P = []; self.C = []; self.UV = []; self.F = []; self.A = []


CH = {}


def chunk_of(x, z):
    i = min(NCX - 1, max(0, int((x - X0) // CHUNK)))
    j = min(NCZ - 1, max(0, int((z - Z0) // CHUNK)))
    return i, j


def buf(mat, x, z):
    d = CH.setdefault(chunk_of(x, z), {})
    b = d.get(mat)
    if b is None:
        b = d[mat] = Buf()
    return b


def planar_uv(pts, n, S):
    if abs(n[1]) > 0.85:
        u = (1.0, 0.0, 0.0); v = (0.0, 0.0, -1.0 if n[1] > 0 else 1.0)
    else:
        u = norm((n[2], 0.0, -n[0])); v = cross(n, u)
    return [(dot(p, u) / S, dot(p, v) / S) for p in pts]


def emit(mat, pts, col, uvs=None, center=None, ao=None, jit=0.0, key=None):
    """Emit one polygon (game coords). col: rgb tuple (sRGB 0..1) or list of per-corner tuples."""
    n = newell(pts)
    if center is not None:
        c = centroid(pts)
        if dot(n, (c[0] - center[0], c[1] - center[1], c[2] - center[2])) < 0:
            pts = pts[::-1]; n = sc(n, -1)
            if uvs is not None: uvs = uvs[::-1]
            if isinstance(col, list): col = col[::-1]
    if uvs is None:
        uvs = planar_uv(pts, n, UVSCALE[mat]) if mat in UVSCALE else [(0.0, 0.0)] * len(pts)
    if not isinstance(col, list):
        if jit:
            c0 = centroid(pts)
            col = mul(col, 1 + jit * (hr(c0[0], c0[1], c0[2], key or 0) - 0.5) * 2)
        col = [col] * len(pts)
    c = centroid(pts)
    b = buf(mat, c[0], c[2])
    b.P.extend(pts); b.C.extend(col); b.UV.extend(uvs); b.F.append(len(pts))
    b.A.extend([1 if (ao if ao is not None else mat not in NO_AO) else 0] * len(pts))


# ---------------------------------------------------- primitive library (local, unit, three.js-like)
def _cyl(n, rt, rb, y0=-0.5, y1=0.5):
    top = [(rt * math.sin(i / n * 2 * math.pi), y1, rt * math.cos(i / n * 2 * math.pi)) for i in range(n)]
    bot = [(rb * math.sin(i / n * 2 * math.pi), y0, rb * math.cos(i / n * 2 * math.pi)) for i in range(n)]
    polys = []
    for i in range(n):
        j = (i + 1) % n
        if rt > 1e-6:
            polys.append([bot[i], bot[j], top[j], top[i]])
        else:
            polys.append([bot[i], bot[j], (0, y1, 0)])
    if rt > 1e-6: polys.append(top[::-1])
    polys.append(bot)
    return polys


def _box():
    c = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [[c[i] for i in q] for q in f]


def _ico(detail):
    t = (1 + math.sqrt(5)) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    tris = [[sc(norm(v[a]), 0.5), sc(norm(v[b]), 0.5), sc(norm(v[c]), 0.5)] for a, b, c in f]
    for _ in range(detail):
        nt = []
        for a, b, c in tris:
            ab = sc(norm(add(a, b)), 0.5); bc = sc(norm(add(b, c)), 0.5); ca = sc(norm(add(c, a)), 0.5)
            nt += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
        tris = nt
    return tris


def _orient(polys, center):
    out = []
    for p in polys:
        n = newell(p); c = centroid(p)
        out.append(p[::-1] if dot(n, (c[0] - center[0], c[1] - center[1], c[2] - center[2])) < 0 else p)
    return out


PRIM = {
    'box': _orient(_box(), (0, 0, 0)),
    'cyl': _orient(_cyl(10, .5, .5), (0, 0, 0)),
    'cyl6': _orient(_cyl(6, .5, .5), (0, 0, 0)),
    'cyl8': _orient(_cyl(8, .5, .5), (0, 0, 0)),
    'cone8': _orient(_cyl(7, 0, .5), (0, 0, 0)),
    'sph': _orient(_ico(0), (0, 0, 0)),
    'sph1': _orient(_ico(1), (0, 0, 0)),
    'pyr': _orient([[(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5)],
                    [(-.5, -.5, .5), (.5, -.5, .5), (0, .5, 0)], [(.5, -.5, .5), (.5, -.5, -.5), (0, .5, 0)],
                    [(.5, -.5, -.5), (-.5, -.5, -.5), (0, .5, 0)], [(-.5, -.5, -.5), (-.5, -.5, .5), (0, .5, 0)]], (0, 0, 0)),
    'prism': _orient([[(-.5, 0, .5), (.5, 0, .5), (0, 1, .5)], [(-.5, 0, -.5), (.5, 0, -.5), (0, 1, -.5)],
                      [(-.5, 0, -.5), (.5, 0, -.5), (.5, 0, .5), (-.5, 0, .5)],
                      [(.5, 0, -.5), (0, 1, -.5), (0, 1, .5), (.5, 0, .5)], [(-.5, 0, -.5), (-.5, 0, .5), (0, 1, .5), (0, 1, -.5)]], (0, .35, 0)),
}


def xf(m, p):
    return (m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
            m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
            m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14])


def emit_prim(name, m, mat, col, jit=0.0, skip_bottom=False, grad=None):
    """grad: (ybottom, ytop, kbottom, ktop) vertical colour gradient (foliage light)."""
    det = (m[0] * (m[5] * m[10] - m[6] * m[9]) - m[4] * (m[1] * m[10] - m[2] * m[9]) + m[8] * (m[1] * m[6] - m[2] * m[5]))
    for poly in PRIM[name]:
        if skip_bottom and all(abs(q[1] + 0.5) < 1e-6 for q in poly) and name != 'prism':
            continue
        pts = [xf(m, q) for q in poly]
        if det < 0: pts = pts[::-1]
        c = col
        if jit:
            c0 = centroid(pts); c = mul(col, 1 + jit * (hr(c0[0], c0[1], c0[2]) - 0.5) * 2)
        if grad:
            y0, y1, k0, k1 = grad
            c = [mul(c, k0 + (k1 - k0) * min(1, max(0, (q[1] - y0) / ((y1 - y0) or 1)))) for q in pts]
        emit(mat, pts, c)


def M(x, y, z, ry=0.0, sx=1.0, sy=1.0, sz=1.0, rx=0.0, rz=0.0):
    """three.js Matrix4.compose with Euler(rx, ry, rz, 'YXZ') -> column-major list."""
    c1, s1 = math.cos(rx), math.sin(rx)
    c2, s2 = math.cos(ry), math.sin(ry)
    c3, s3 = math.cos(rz), math.sin(rz)
    # rotation matrix for order YXZ (from three.js Matrix4.makeRotationFromEuler)
    ce, cf, de, df = c2 * c3, c2 * s3, s2 * c3, s2 * s3
    r = [[ce + df * s1, de * s1 - cf, c1 * s2],
         [c1 * s3, c1 * c3, -s1],
         [cf * s1 - de, df + ce * s1, c1 * c2]]
    return [r[0][0] * sx, r[1][0] * sx, r[2][0] * sx, 0, r[0][1] * sy, r[1][1] * sy, r[2][1] * sy, 0,
            r[0][2] * sz, r[1][2] * sz, r[2][2] * sz, 0, x, y, z, 1]


# ---------------------------------------------------- oriented boxes & frames
class Frame:
    """Local frame: origin o, axes ax (right), up (0,1,0), az (front/out)."""

    def __init__(self, o, ry):
        self.o = o; self.c = math.cos(ry); self.s = math.sin(ry); self.ry = ry
        self.ax = (self.c, 0.0, -self.s); self.az = (self.s, 0.0, self.c)

    def p(self, lx, y, lz):
        return (self.o[0] + lx * self.c + lz * self.s, y, self.o[2] - lx * self.s + lz * self.c)


def obox(center, ax, ay, az, hx_, hy_, hz_, mat, col, skip=(), jit=0.0, uvs_front=None):
    """Oriented box. skip: subset of {'+x','-x','+y','-y','+z','-z'}."""
    for sgn, nm, a, b, c, ha, hb, hc in ((1, '+x', ax, ay, az, hx_, hy_, hz_), (-1, '-x', ax, ay, az, hx_, hy_, hz_),
                                         (1, '+y', ay, az, ax, hy_, hz_, hx_), (-1, '-y', ay, az, ax, hy_, hz_, hx_),
                                         (1, '+z', az, ax, ay, hz_, hx_, hy_), (-1, '-z', az, ax, ay, hz_, hx_, hy_)):
        if nm in skip:
            continue
        fc = add(center, sc(a, sgn * ha))
        pts = [add(add(fc, sc(b, -hb)), sc(c, -hc)), add(add(fc, sc(b, hb)), sc(c, -hc)),
               add(add(fc, sc(b, hb)), sc(c, hc)), add(add(fc, sc(b, -hb)), sc(c, hc))]
        uv = uvs_front if (uvs_front is not None and nm == '+z') else None
        if uv is not None:  # front face with explicit uvs: order bl, br, tr, tl seen from outside
            pts = [add(add(fc, sc(ax, -hx_)), sc(ay, -hy_)), add(add(fc, sc(ax, hx_)), sc(ay, -hy_)),
                   add(add(fc, sc(ax, hx_)), sc(ay, hy_)), add(add(fc, sc(ax, -hx_)), sc(ay, hy_))]
        emit(mat, pts, col, uvs=uv, center=center, jit=jit)


def fbox(F, lx, y, lz, hx_, hy_, hz_, mat, col, skip=(), jit=0.0):
    obox(F.p(lx, y, lz), F.ax, (0, 1, 0), F.az, hx_, hy_, hz_, mat, col, skip, jit)


def seg_box(a, b, w, h, mat, col, up=(0, 1, 0)):
    """Beam from point a to point b with cross-section w x h."""
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    L_ = math.sqrt(dot(d, d))
    ax = norm(d)
    side = norm(cross(up, ax)) if abs(dot(ax, up)) < 0.98 else (1, 0, 0)
    ay = cross(ax, side)
    obox(sc(add(a, b), 0.5), ax, ay, side, L_ / 2, h / 2, w / 2, mat, col)


# ============================================================== palette
C_FRAME = hx(0xe9e3d5)
C_PLINTH = hx(0x9d958a)
SHUTTERS = [0x3f6b3c, 0x2f5233, 0x6b4a2e, 0x55705c, 0x3e6670, 0x4d6b3a, 0x7a3e2c]
STONE_COLS = {0xa39b8b, 0xb8ad97, 0x9c9282, 0xc2b8a3}
FIELD_COLS = [0x77924a, 0x6a8a45, 0x83a052, 0xbba95e, 0xab9850, 0x86694c, 0x5c823b, 0x8ca85c, 0x9f9c62, 0x748f49, 0x67873f]


# ============================================================== buildings
def side_frames(F, w, d):
    """For each wall side: (name, centre-local (lx,lz), tangent-local, normal-local, length)."""
    return [('front', (0, d / 2), (1, 0), (0, 1), w), ('back', (0, -d / 2), (-1, 0), (0, -1), w),
            ('right', (w / 2, 0), (0, -1), (1, 0), d), ('left', (-w / 2, 0), (0, 1), (-1, 0), d)]


class Wall:
    def __init__(self, F, side):
        nm, c, t, n, L_ = side
        self.F = F; self.name = nm; self.c = c; self.t = t; self.n = n; self.L = L_
        self.tw = (t[0] * F.c + t[1] * F.s, 0.0, -t[0] * F.s + t[1] * F.c)
        self.nw = (n[0] * F.c + n[1] * F.s, 0.0, -n[0] * F.s + n[1] * F.c)

    def p(self, t, y, o):
        lx = self.c[0] + self.t[0] * t + self.n[0] * o
        lz = self.c[1] + self.t[1] * t + self.n[1] * o
        return self.F.p(lx, y, lz)

    def quad(self, mat, t0, t1, y0, y1, o, col, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
        emit(mat, [self.p(t0, y0, o), self.p(t1, y0, o), self.p(t1, y1, o), self.p(t0, y1, o)], col, uvs=list(uv))

    def slab(self, mat, t0, t1, y0, y1, o0, o1, col, jit=0.0):
        c = self.p((t0 + t1) / 2, (y0 + y1) / 2, (o0 + o1) / 2)
        obox(c, self.tw, (0, 1, 0), self.nw, (t1 - t0) / 2, (y1 - y0) / 2, (o1 - o0) / 2, mat, col, skip=('-z',), jit=jit)

    def ground(self, t):
        q = self.p(t, 0, 0.3)
        return H(q[0], q[2])


UV_SHUT = ((0, 0), (0.5, 0), (0.5, 1), (0, 1))
UV_DOOR = ((0.5, 0), (1, 0), (1, 1), (0.5, 1))


def window(W, t, sill, ww, wh, shutter_col, lit, closed=False, frame_col=C_FRAME, french=False):
    mat = 'M_WindowLit' if lit else 'M_Window'
    fw = ww / 2 + 0.12
    W.quad(mat, t - fw, t + fw, sill - 0.1, sill + wh + 0.1, 0.03, (1, 1, 1))
    if not french:
        W.slab('M_Plaster', t - fw - 0.08, t + fw + 0.08, sill - 0.2, sill - 0.08, 0.0, 0.16, frame_col)
    if shutter_col is None:
        return
    if closed:
        W.quad('M_Detail', t - fw + 0.04, t, sill - 0.06, sill + wh + 0.06, 0.06, shutter_col, UV_SHUT)
        W.quad('M_Detail', t, t + fw - 0.04, sill - 0.06, sill + wh + 0.06, 0.06, shutter_col, UV_SHUT)
    else:
        sw = ww / 2 + 0.06
        W.quad('M_Detail', t - fw - sw, t - fw, sill - 0.06, sill + wh + 0.06, 0.05, shutter_col, UV_SHUT)
        W.quad('M_Detail', t + fw, t + fw + sw, sill - 0.06, sill + wh + 0.06, 0.05, shutter_col, UV_SHUT)


def hip_roof(F, W_, D_, y0, rh, col, fascia=0.2, fascia_col=hx(0x5a412c), cap=True):
    """Hip roof over footprint W_ x D_ (local x/z), eave at y0, height rh."""
    y1 = y0 + rh
    if W_ >= D_:
        r = (W_ - D_) / 2
        ridge = [F.p(-r, y1, 0), F.p(r, y1, 0)]
        corners = [F.p(-W_ / 2, y0, D_ / 2), F.p(W_ / 2, y0, D_ / 2), F.p(W_ / 2, y0, -D_ / 2), F.p(-W_ / 2, y0, -D_ / 2)]
        faces = [[corners[0], corners[1], ridge[1], ridge[0]], [corners[2], corners[3], ridge[0], ridge[1]],
                 [corners[1], corners[2], ridge[1]], [corners[3], corners[0], ridge[0]]]
        hips = [(corners[0], ridge[0]), (corners[3], ridge[0]), (corners[1], ridge[1]), (corners[2], ridge[1])]
    else:
        r = (D_ - W_) / 2
        ridge = [F.p(0, y1, r), F.p(0, y1, -r)]
        corners = [F.p(-W_ / 2, y0, D_ / 2), F.p(W_ / 2, y0, D_ / 2), F.p(W_ / 2, y0, -D_ / 2), F.p(-W_ / 2, y0, -D_ / 2)]
        faces = [[corners[1], corners[2], ridge[1], ridge[0]], [corners[3], corners[0], ridge[0], ridge[1]],
                 [corners[0], corners[1], ridge[0]], [corners[2], corners[3], ridge[1]]]
        hips = [(corners[0], ridge[0]), (corners[1], ridge[0]), (corners[2], ridge[1]), (corners[3], ridge[1])]
    ctr = F.p(0, y0, 0)
    for f in faces:
        f = [p for i, p in enumerate(f) if i == 0 or (abs(p[0] - f[i - 1][0]) + abs(p[2] - f[i - 1][2]) + abs(p[1] - f[i - 1][1])) > 1e-4]
        if len(f) >= 3:
            emit('M_Roof', f, col, center=ctr, jit=0.05)
    if fascia:
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            emit('M_Wood', [a, b, (b[0], y0 - fascia, b[2]), (a[0], y0 - fascia, a[2])], fascia_col, center=ctr)
        emit('M_Wood', [(p[0], y0 - fascia, p[2]) for p in corners], mul(fascia_col, 0.8), center=(ctr[0], y0 + 5, ctr[2]))
    if cap:
        cc = mul(col, 0.82)
        for a, b in hips:
            seg_box((a[0], a[1] + 0.06, a[2]), (b[0], b[1] + 0.06, b[2]), 0.24, 0.14, 'M_Roof', cc)
        if abs(r) > 0.05:
            seg_box((ridge[0][0], y1 + 0.06, ridge[0][2]), (ridge[1][0], y1 + 0.06, ridge[1][2]), 0.26, 0.16, 'M_Roof', cc)


def decorate_walls(F, w, d, base, top, color, idx, n_fl=None, door=None, shop=None, keepouts=(), stone=False, balcony_ok=True):
    """Walls + plinth + bands + windows/shutters for a rectangular building.
    door: dict(color, gy) or None ; shop: dict(sign_bottom) or None ; keepouts: [(side, t0, t1, y0, y1)]."""
    wall_mat = 'M_Stone' if stone else 'M_Plaster'
    col = color
    bh = top - base
    fbox(F, 0, base + bh / 2, 0, w / 2, bh / 2, d / 2, wall_mat, col, skip=('+y', '-y'))
    gref = None
    sides = [Wall(F, s) for s in side_frames(F, w, d)]
    gmax = max(max(Wl.ground(-Wl.L / 2 + 0.2), Wl.ground(Wl.L / 2 - 0.2), Wl.ground(0)) for Wl in sides)
    gref = gmax
    h = top - gref
    if n_fl is None:
        n_fl = max(1, int(round(h / 2.9)))
    fh = h / n_fl
    # plinth (zoccolo) and bands
    ptop = gref + 0.55
    fbox(F, 0, (base + ptop) / 2, 0, w / 2 + 0.04, (ptop - base) / 2, d / 2 + 0.04, 'M_Stone', mul(C_PLINTH, 0.95 if not stone else 0.8), skip=('-y',))
    band = mul(mix(col, (1, 1, 1), 0.55), 1.0)
    if not stone:
        for k in range(1, n_fl):
            y = gref + k * fh
            fbox(F, 0, y, 0, w / 2 + 0.035, 0.07, d / 2 + 0.035, 'M_Plaster', band, skip=('-y',))
    fbox(F, 0, top - 0.17, 0, w / 2 + 0.1, 0.17, d / 2 + 0.1, 'M_Plaster', band, skip=('-y',))
    shutter_col = hx(SHUTTERS[int(hr(idx, 3) * len(SHUTTERS))])
    if stone and hr(idx, 4) < 0.6:
        shutter_col = hx(0x6b4a2e)
    no_shutters = (not stone) and hr(idx, 5) < 0.12
    ww = 0.86
    wh = min(1.42, fh * 0.48)
    balc = balcony_ok and n_fl >= 2 and hr(idx, 6) < 0.45 and w >= 6
    for Wl in sides:
        nwin = max(1, int((Wl.L - 0.6) / 2.6))
        ts = [(i + 0.5) * Wl.L / nwin - Wl.L / 2 for i in range(nwin)]
        for k in range(n_fl):
            fb = gref + k * fh
            sill = fb + fh * 0.32
            for t in ts:
                if Wl.name == 'front' and k == 0 and (door is not None or shop is not None) and abs(t) < 1.6:
                    continue
                if Wl.name == 'front' and shop is not None and k == 0:
                    continue
                if Wl.ground(t) > sill - 0.45:
                    continue
                blocked = False
                for (sn, t0, t1, y0, y1) in keepouts:
                    if sn == Wl.name and t + 0.75 > t0 and t - 0.75 < t1 and sill + wh + 0.2 > y0 and sill - 0.2 < y1:
                        blocked = True
                if blocked:
                    continue
                lit = hr(idx, t, k, len(Wl.name)) < 0.5
                closed = hr(idx, t * 3.1, k + 7) < 0.14
                if balc and Wl.name == 'front' and k == 1 and abs(t) == min(abs(q) for q in ts):
                    # porta-finestra + balcone
                    window(Wl, t, fb + 0.05, ww + 0.1, min(2.2, fh - 0.5), None if no_shutters else shutter_col, lit, french=True)
                    bw = 1.4
                    Wl.slab('M_Plaster', t - bw, t + bw, fb - 0.08, fb + 0.08, 0.0, 1.0, band)
                    rc = hx(0x2b2b2b)
                    for q in (-1, 1):
                        a = Wl.p(t + q * (bw - 0.05), fb + 0.08, 0.95); b = Wl.p(t + q * (bw - 0.05), fb + 1.0, 0.95)
                        seg_box(a, b, 0.05, 0.05, 'M_Plain', rc)
                        a = Wl.p(t + q * (bw - 0.05), fb + 1.0, 0.05)
                        seg_box(a, b, 0.05, 0.05, 'M_Plain', rc)
                    seg_box(Wl.p(t - bw, fb + 1.0, 0.95), Wl.p(t + bw, fb + 1.0, 0.95), 0.06, 0.06, 'M_Plain', rc)
                    nb = 9
                    for i in range(1, nb):
                        tt = t - bw + 2 * bw * i / nb
                        seg_box(Wl.p(tt, fb + 0.08, 0.95), Wl.p(tt, fb + 1.0, 0.95), 0.03, 0.03, 'M_Plain', rc)
                    continue
                window(Wl, t, sill, ww, wh, None if no_shutters else shutter_col, lit, closed)
    # shop windows (vetrine)
    if shop is not None:
        Wf = sides[0]
        gy = door['gy'] if door else Wf.ground(0)
        vtop = min(gy + 2.45, shop.get('sign_bottom', 99) - 0.15)
        vw = min(2.3, w / 2 - 1.15 - 0.35)
        if vw > 0.8 and vtop - gy > 1.2:
            for q in (-1, 1):
                tc = q * (0.95 + vw / 2)
                Wf.slab('M_Plaster', tc - vw / 2 - 0.12, tc + vw / 2 + 0.12, gy + 0.2, vtop + 0.12, 0.0, 0.06, C_FRAME)
                Wf.quad('M_WindowLit', tc - vw / 2, tc + vw / 2, gy + 0.32, vtop, 0.075, (1, 1, 1),
                        uv=((0.2, 0.2), (0.8, 0.2), (0.8, 0.55), (0.2, 0.55)))
    if door is not None:
        Wf = sides[0]
        gy = door['gy']; dw = door.get('w', 1.25); dh = door.get('h', 2.3)
        Wf.slab('M_Plaster', -dw / 2 - 0.16, dw / 2 + 0.16, gy - 0.05, gy + dh + 0.18, 0.0, 0.08, C_FRAME)
        Wf.quad('M_Detail', -dw / 2, dw / 2, gy, gy + dh, 0.09, door['color'], UV_DOOR)
    return gref, n_fl


def chimney(x, y, z, hc, wall_col, roof_col):
    obox((x, y, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.32, hc / 2, 0.32, 'M_Plaster', mul(wall_col, 0.9), skip=('-y',))
    yt = y + hc / 2
    obox((x, yt + 0.05, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.45, 0.05, 0.45, 'M_Plaster', hx(0xd8d0c0))
    emit_prim('pyr', M(x, yt + 0.32, z, 0, 0.8, 0.34, 0.8), 'M_Roof', roof_col)


def build_house(rec, idx, shop=None):
    a = rec['args']
    x, z, w, d, h, rot, color = a[:7]
    opts = a[7] if len(a) > 7 and a[7] else {}
    parts = rec['parts']
    fac, roof, eave, door, step = parts[:5]
    bh = fac['p']['height']; cy = fac['m'][13]
    base = cy - bh / 2; top = base + bh
    rm = roof['m']; rh = math.sqrt(rm[4] ** 2 + rm[5] ** 2 + rm[6] ** 2)
    roof_col = hx(roof['c'])
    F = Frame((x, 0, z), rot)
    stone = (int(color) in STONE_COLS)
    gy = H(door['m'][12], door['m'][14])
    keep = []
    if shop:
        keep = shop.get('keep', [])
    decorate_walls(F, w, d, base, top, hx(color), idx, door=dict(color=hx(door['c']), gy=gy), shop=shop, keepouts=keep, stone=stone)
    emit_prim('box', step['m'], 'M_Stone', hx(0xbdb5a5))
    hip_roof(F, w + 0.9, d + 0.9, top, rh, roof_col)
    if len(parts) > 5:
        cm = parts[5]['m']
        hc = math.sqrt(cm[4] ** 2 + cm[5] ** 2 + cm[6] ** 2)
        chimney(cm[12], cm[13], cm[14], hc, hx(color), roof_col)


# ---------------------------------------------------- church + campanile
def build_church(rec):
    x, z, w, d, h, ry, ctw, ctx, ctz = rec['args'][:9]
    parts = rec['parts']
    base = H(x, z) - 0.5
    F = Frame((x, 0, z), ry)
    wallc = hx(0xf2ead8)
    fbox(F, 0, base + h / 2, 0, w / 2, h / 2, d / 2, 'M_Plaster', wallc, skip=('+y', '-y'))
    fbox(F, 0, base + 0.75, 0, w / 2 + 0.06, 0.75, d / 2 + 0.06, 'M_Stone', hx(0xb5ad9c), skip=('-y',))
    fbox(F, 0, base + h - 0.2, 0, w / 2 + 0.15, 0.2, d / 2 + 0.15, 'M_Plaster', hx(0xfbf6ea), skip=('-y',))
    # tall arched side windows + lesene
    for sgn, nm in ((1, 'right'), (-1, 'left')):
        Wl = Wall(F, [s for s in side_frames(F, w, d) if s[0] == nm][0])
        nwin = max(2, int(d / 5))
        for i in range(nwin):
            t = (i + 0.5) * d / nwin - d / 2
            y0 = base + h * 0.38; y1 = base + h * 0.72; hw = 0.6
            Wl.slab('M_Plaster', t - hw - 0.2, t + hw + 0.2, y0 - 0.25, y1 + 0.2, 0.0, 0.05, hx(0xe8dfcc))
            Wl.quad('M_WindowLit', t - hw, t + hw, y0, y1, 0.06, (1, 1, 1), uv=((0.2, 0.1), (0.8, 0.1), (0.8, 0.85), (0.2, 0.85)))
            arc = [Wl.p(t + hw * math.cos(math.pi * k / 8), y1 + hw * math.sin(math.pi * k / 8), 0.06) for k in range(9)]
            emit('M_WindowLit', arc, (1, 1, 1), uvs=[(0.3, 0.6)] * 9, center=Wl.p(t, y1, -1))
        for i in range(nwin + 1):
            t = i * d / nwin - d / 2
            Wl.slab('M_Plaster', t - 0.3, t + 0.3, base, base + h - 0.3, 0.0, 0.12, hx(0xe9e0cc))
    # original parts, in church() order: 0 nave, 1 roof, 2 facade, 3 pediment, 4-5 pilasters, 6 door, 7 rose, 8 steps, 9+ campanile
    P_ = parts
    emit_prim('prism', P_[1]['m'], 'M_Roof', hx(P_[1]['c']), jit=0.04)
    emit_prim('box', P_[2]['m'], 'M_Plaster', hx(0xeee2c8), skip_bottom=True)
    m = P_[3]['m']
    emit_prim('prism', m, 'M_Plaster', hx(0xeee2c8))
    sx = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2); sy = math.sqrt(m[4] ** 2 + m[5] ** 2 + m[6] ** 2)
    szv = (m[8], m[9], m[10]); szl = math.sqrt(dot(szv, szv)); azd = norm(szv); axd = norm((m[0], m[1], m[2]))
    fr = add((m[12], m[13], m[14]), sc(azd, szl / 2 + 0.12))
    l = add(fr, sc(axd, -sx / 2 - 0.1)); r = add(fr, sc(axd, sx / 2 + 0.1)); ap = (fr[0], fr[1] + sy + 0.12, fr[2])
    cw = hx(0xfbf6ea)
    seg_box(l, ap, 0.35, 0.3, 'M_Plaster', cw); seg_box(r, ap, 0.35, 0.3, 'M_Plaster', cw)
    seg_box(add(l, (0, -0.1, 0)), add(r, (0, -0.1, 0)), 0.4, 0.3, 'M_Plaster', cw)
    emit_prim('cyl8', M(ap[0], ap[1] + 0.45, ap[2], 0, 0.5, 0.6, 0.5), 'M_Plaster', cw)
    for p in P_[4:6]:  # pilasters + capitals
        m = p['m']
        emit_prim('box', m, 'M_Plaster', hx(0xdccbaa), skip_bottom=True)
        top_y = m[13] + math.sqrt(m[4] ** 2 + m[5] ** 2 + m[6] ** 2) / 2
        emit_prim('box', M(m[12], top_y - 0.2, m[14], ry, 1.25, 0.4, 0.8), 'M_Plaster', cw)
    m = P_[6]['m']  # door with stone frame
    cx_, cy_, cz_ = m[12], m[13], m[14]
    Fd = Frame((cx_, 0, cz_), ry)
    fbox(Fd, 0, cy_ + 0.2, -0.05, 1.5, 2.45, 0.12, 'M_Stone', hx(0xcfc6b3))
    Wd = Wall(Fd, ('front', (0, 0.07), (1, 0), (0, 1), 2.2))
    Wd.quad('M_Detail', -1.1, 1.1, cy_ - 2.1, cy_ + 2.1, 0.01, hx(0x5a3a24), UV_DOOR)
    m = P_[7]['m']  # rose window
    emit_prim('cyl', M(m[12], m[13], m[14], ry, 2.9, 0.12, 2.9, math.pi / 2), 'M_Plaster', hx(0xe2d8c2))
    emit_prim('cyl', m, 'M_WindowLit', (1, 1, 1))
    m = P_[8]['m']  # steps
    emit_prim('box', m, 'M_Stone', hx(0xc9c1b0))
    sxs = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2)
    fx, fz = math.sin(ry), math.cos(ry)
    emit_prim('box', M(m[12] - fx * 0.45, m[13] + 0.35, m[14] - fz * 0.45, ry, sxs - 0.6, 0.2, 1.2), 'M_Stone', hx(0xd2cab8))
    build_campanile(ctx, ctz, ctw)
    return rec['ret']['clock']


def build_campanile(ctx, ctz, ctw):
    cb = H(ctx, ctz) - 0.5
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    shaft = hx(0xe9dfca)
    obox((ctx, cb + ctw / 2, ctz), X, Y, Z, 2, ctw / 2, 2, 'M_Plaster', shaft, skip=('+y', '-y'))
    obox((ctx, cb + 0.8, ctz), X, Y, Z, 2.12, 0.8, 2.12, 'M_Stone', hx(0xb5ad9c), skip=('-y',))
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):
            obox((ctx + sx_ * 1.85, cb + ctw / 2, ctz + sz_ * 1.85), X, Y, Z, 0.3, ctw / 2, 0.3, 'M_Plaster', hx(0xdfd3bc), skip=('-y',))
    y = cb + 7
    while y < cb + ctw - 4.5:
        obox((ctx, y, ctz), X, Y, Z, 2.2, 0.1, 2.2, 'M_Plaster', hx(0xf5efe2), skip=())
        y += 7
    for k in range(4):  # feritoie
        a = k * math.pi / 2
        Fk = Frame((ctx, 0, ctz), a)
        Wk = Wall(Fk, ('front', (0, 2), (1, 0), (0, 1), 4))
        yy = cb + 5
        while yy < cb + ctw - 5:
            if not (k == 0 and yy > cb + ctw - 5.5):
                Wk.quad('M_Plain', -0.14, 0.14, yy, yy + 0.9, 0.01, hx(0x2a2622))
            yy += 6.5
    # clock ring (runtime clock face sits at z+2.03)
    emit_prim('cyl', M(ctx, cb + ctw - 2.4, ctz + 2.0, 0, 2.9, 0.04, 2.9, math.pi / 2), 'M_Plaster', hx(0xcfc4ad))
    # belfry
    yb = cb + ctw
    obox((ctx, yb + 0.15, ctz), X, Y, Z, 2.25, 0.15, 2.25, 'M_Plaster', hx(0xf5efe2))
    obox((ctx, yb + 1.6, ctz), X, Y, Z, 1.35, 1.45, 1.35, 'M_Plain', hx(0x2c2824), skip=('-y',))
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):
            obox((ctx + sx_ * 1.75, yb + 1.6, ctz + sz_ * 1.75), X, Y, Z, 0.45, 1.45, 0.45, 'M_Plaster', hx(0xe6dbc4))
    for k in range(4):
        a = k * math.pi / 2
        Fk = Frame((ctx, 0, ctz), a)
        fbox(Fk, 0, yb + 1.6, 1.85, 0.12, 1.3, 0.12, 'M_Plaster', hx(0xe6dbc4))  # mullion (bifora)
        fbox(Fk, 0, yb + 2.85, 1.85, 1.75, 0.3, 0.38, 'M_Plaster', hx(0xe6dbc4))  # architrave
        for q in (-1, 1):  # little arches
            c0 = Fk.p(q * 0.75, yb + 2.55, 2.2)
            pts = [Fk.p(q * 0.75 + 0.63 * math.cos(math.pi * j / 6), yb + 2.25 + 0.28 * math.sin(math.pi * j / 6), 2.24) for j in range(7)]
            pts += [Fk.p(q * 0.75 - 0.63, yb + 2.55, 2.24), Fk.p(q * 0.75 + 0.63, yb + 2.55, 2.24)]
            emit('M_Plaster', pts, hx(0xe6dbc4), center=Fk.p(q * 0.75, yb + 2.4, 0))
    emit_prim('cyl8', M(ctx, yb + 1.55, ctz, 0, 1.1, 0.95, 1.1), 'M_Plain', hx(0x8a6a2e))  # bell
    emit_prim('cone8', M(ctx, yb + 2.1, ctz, 0, 0.9, 0.35, 0.9), 'M_Plain', hx(0x7a5c28))
    obox((ctx, yb + 3.35, ctz), X, Y, Z, 2.4, 0.2, 2.4, 'M_Plaster', hx(0xf5efe2))
    emit_prim('cyl8', M(ctx, yb + 4.05, ctz, math.pi / 8, 3.3, 1.0, 3.3), 'M_Plaster', hx(0xe9dfca))
    emit_prim('cone8', M(ctx, yb + 4.55 + 2.9, ctz, 0, 3.4, 5.8, 3.4), 'M_Roof', hx(0xa4502f), jit=0.03)
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):
            emit_prim('cone8', M(ctx + sx_ * 1.95, yb + 4.15, ctz + sz_ * 1.95, 0, 0.42, 1.4, 0.42), 'M_Plaster', hx(0xf5efe2))
    ytop = yb + 4.55 + 5.8
    obox((ctx, ytop + 0.7, ctz), X, Y, Z, 0.06, 0.8, 0.06, 'M_Plain', hx(0x333333))
    obox((ctx, ytop + 0.95, ctz), X, Y, Z, 0.4, 0.06, 0.06, 'M_Plain', hx(0x333333))


# ---------------------------------------------------- vegetation
def build_tree(rec):
    a = rec['args']
    x, z = a[0], a[1]
    s = a[2] if len(a) > 2 and a[2] is not None else 1
    kind = a[3] if len(a) > 3 and a[3] else 'leaf'
    parts = rec['parts']
    y = H(x, z)
    r = hr(x, z)
    if kind == 'pine':
        c1 = hx(parts[1]['c']); c2 = hx(parts[2]['c'])
        far = not (L['WB']['x0'] - 10 < x < L['WB']['x1'] + 10 and z > L['WB']['z0'] - 10)
        emit_prim('cyl6', M(x, y + 1.0 * s, z, 0, 0.42 * s, 2.0 * s, 0.42 * s), 'M_Wood', hx(0x4a3426), skip_bottom=True)
        tiers = [(2.9, 2.3, 3.4, c1), (4.8, 1.75, 3.1, mix(c1, c2, 0.5)), (6.5, 1.15, 2.6, c2)] if not far else \
                [(3.2, 2.2, 4.4, c1), (5.8, 1.5, 3.8, c2)]
        for i, (yc, rr, hh, cc) in enumerate(tiers):
            cc = mul(cc, 0.95 + 0.12 * hr(x, z, i))
            pine_tier(x, y + yc * s, z, rr * s, hh * s, cc, r * 6.28 + i)
    elif kind == 'cypress':
        c = hx(parts[1]['c'])
        emit_prim('cyl6', M(x, y + 0.6 * s, z, 0, 0.3 * s, 1.2 * s, 0.3 * s), 'M_Wood', hx(0x5a4030), skip_bottom=True)
        rings = [(0.6, 0.62), (1.6, 0.86), (4.5, 0.72), (6.8, 0.38), (8.3, 0.0)]
        spindle(x, y, z, s, rings, c, r)
    else:
        c = hx(parts[1]['c'])
        tc = hx(0x5b4332)
        emit_prim('cyl6', M(x, y + 1.3 * s, z, r * 3, 0.5 * s, 2.6 * s, 0.5 * s), 'M_Wood', tc, skip_bottom=True)
        emit_prim('cyl6', M(x + 0.45 * s, y + 2.5 * s, z, r * 3, 0.18 * s, 1.4 * s, 0.18 * s, 0, -0.6), 'M_Wood', tc)
        blobs = [(0, 3.9, 0, 2.05, 1.7), (0.9, 3.4, 0.5, 1.35, 1.15), (-0.8, 3.5, -0.4, 1.4, 1.2), (0.2, 4.6, -0.3, 1.3, 1.1)]
        for i, (bx_, by_, bz_, rr, hh) in enumerate(blobs):
            ang = r * 6.28
            ox = bx_ * math.cos(ang) - bz_ * math.sin(ang); oz = bx_ * math.sin(ang) + bz_ * math.cos(ang)
            cc = mul(c, 0.92 + 0.16 * hr(x, z, i))
            blob(x + ox * s, y + by_ * s, z + oz * s, rr * s, hh * s, cc, x * 7 + i)


def pine_tier(x, y, z, r, h, col, seed):
    """Cone tier with jagged drooping skirt."""
    n = 8
    apex = (x, y + h * 0.55, z)
    ring = []
    for i in range(n):
        a = i / n * 2 * math.pi + seed
        rr = r * (1.0 if i % 2 == 0 else 0.78)
        yy = y - h * 0.45 - (0.25 * r if i % 2 == 0 else 0)
        ring.append((x + rr * math.sin(a), yy, z + rr * math.cos(a)))
    top, bot = mul(col, 1.18), mul(col, 0.72)
    for i in range(n):
        j = (i + 1) % n
        emit('M_Foliage', [ring[i], ring[j], apex], [bot, bot, top], center=(x, y - h * 0.2, z), jit=0)
    emit('M_Foliage', ring[::-1], mul(col, 0.5), center=(x, y + h, z))


def spindle(x, y, z, s, rings, col, seed):
    n = 8
    pts = []
    for (hh, rr) in rings:
        pts.append([(x + rr * s * math.sin(i / n * 2 * math.pi + seed), y + hh * s, z + rr * s * math.cos(i / n * 2 * math.pi + seed)) for i in range(n)])
    for k in range(len(rings) - 1):
        k0 = 0.7 + 0.5 * k / (len(rings) - 1); k1 = 0.7 + 0.5 * (k + 1) / (len(rings) - 1)
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = pts[k][i], pts[k][j], pts[k + 1][j], pts[k + 1][i]
            cc = [mul(col, k0), mul(col, k0), mul(col, k1), mul(col, k1)]
            if rings[k + 1][1] == 0:
                emit('M_Foliage', [a, b, c], cc[:3], center=(x, y + rings[k][0] * s * 0.5, z))
            else:
                emit('M_Foliage', [a, b, c, d], cc, center=(x, y + (rings[k][0] + rings[k + 1][0]) * s * 0.5, z))
    emit('M_Foliage', pts[0], mul(col, 0.6), center=(x, y + 5 * s, z))


ICO1 = PRIM['sph1']


def blob(x, y, z, r, h, col, seed):
    for tri in ICO1:
        pts = []
        for q in tri:
            j = 1 + 0.16 * (hr(q[0] * 7 + seed, q[1] * 5, q[2] * 3) - 0.5)
            pts.append((x + q[0] * 2 * r * j, y + q[1] * 2 * h * j, z + q[2] * 2 * r * j))
        cc = [mul(col, 0.7 + 0.45 * min(1, max(0, (p[1] - (y - h)) / (2 * h)))) for p in pts]
        emit('M_Foliage', pts, cc, center=(x, y, z))


def rock(m, col):
    sd = m[12] * 3.1 + m[14]
    for tri in ICO1:
        pts = []
        for q in tri:
            j = 1 + 0.38 * (hr(q[0] * 11 + sd, q[1] * 13, q[2] * 17) - 0.5)
            pts.append(xf(m, (q[0] * j, q[1] * j * (0.8 if q[1] > 0 else 1), q[2] * j)))
        c0 = centroid(pts)
        emit('M_Plain', pts, mul(col, 0.88 + 0.24 * hr(c0[0], c0[1], c0[2])), center=(m[12], m[13], m[14]))


def vine_row(m, col):
    sx = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2)
    ax = norm((m[0], m[1], m[2]))
    cx, cy, cz = m[12], m[13], m[14]
    n = max(1, int(sx / 2.5))
    sl = sx / n
    for i in range(n):
        t = -sx / 2 + (i + 0.5) * sl
        px, pz = cx + ax[0] * t, cz + ax[2] * t
        g = H(px, pz)
        hh = 0.5 + 0.12 * hr(px, pz)
        dd = 0.3 + 0.08 * hr(pz, px)
        cc = mul(col, 0.9 + 0.2 * hr(px, pz, 2))
        obox((px, g + 1.05 + 0.05 * hr(px, 1), pz), ax, (0, 1, 0), (-ax[2], 0, ax[0]), sl / 2 + 0.05, hh, dd, 'M_Foliage', cc)


# ---------------------------------------------------- lamps, benches, signs
def build_lamp(rec):
    x, z = rec['args'][:2]
    y = H(x, z)
    pc = hx(0x2f3a36)
    emit_prim('cyl8', M(x, y + 0.3, z, 0, 0.32, 0.6, 0.32), 'M_Plain', pc)
    emit_prim('cyl8', M(x, y + 2.9, z, 0, 0.15, 4.6, 0.15), 'M_Plain', pc)
    seg_box((x, y + 5.15, z - 0.05), (x, y + 5.25, z + 0.62), 0.07, 0.07, 'M_Plain', pc)
    seg_box((x, y + 4.75, z), (x, y + 5.18, z + 0.32), 0.05, 0.05, 'M_Plain', pc)
    hz_ = z + 0.58
    emit_prim('pyr', M(x, y + 5.32, hz_, 0, 0.62, 0.22, 0.62), 'M_Plain', pc)
    emit_prim('box', M(x, y + 5.02, hz_, 0, 0.42, 0.38, 0.42), 'M_LampGlow', hx(0xfff0c8))
    emit_prim('box', M(x, y + 4.8, hz_, 0, 0.3, 0.08, 0.3), 'M_Plain', pc)


def build_bench(rec):
    x, z, ry = rec['args'][:3]
    y = H(x, z)
    F = Frame((x, 0, z), ry)
    wood = hx(0x8a5a34); iron = hx(0x2a2a2a)
    for i in range(4):
        fbox(F, 0, y + 0.45, -0.18 + i * 0.12, 0.9, 0.025, 0.045, 'M_Wood', mul(wood, 0.95 + 0.1 * (i % 2)))
    for i in range(3):
        fbox(F, 0, y + 0.62 + i * 0.13, -0.27, 0.9, 0.045, 0.02, 'M_Wood', wood)
    for q in (-0.75, 0.75):
        fbox(F, q, y + 0.22, 0.0, 0.03, 0.22, 0.22, 'M_Plain', iron)
        fbox(F, q, y + 0.62, -0.29, 0.03, 0.25, 0.03, 'M_Plain', iron)


def build_sign(rec):
    a = rec['args'] + [None] * 10
    x, z, ry, front, back, w, h, poleH, poles, yAbs = a[:10]
    w = 2 if w is None else w; h = 1 if h is None else h; poleH = 1.6 if poleH is None else poleH
    y = yAbs if yAbs is not None else H(x, z)
    for p in rec['parts']:
        m = p['m']
        emit_prim('cyl8', M(m[12], m[13], m[14], 0, 0.1, math.sqrt(m[4] ** 2 + m[5] ** 2 + m[6] ** 2), 0.1), 'M_Plain', hx(0x8d9296))
    kind = (front or {}).get('tex', {}) or {}
    if kind.get('kind') not in ('warn', 'round'):
        F = Frame((x, 0, z), ry)
        fbox(F, 0, y + poleH + h / 2, 0, w / 2 + 0.04, h / 2 + 0.04, 0.045, 'M_Plain', hx(0x9aa0a6))


def build_drape(rec):
    a = rec['args'] + [None] * 4
    cx, cz, w, d, key, color = a[:6]
    yo = a[6] if a[6] is not None else 0.1
    col = hx(color)
    if key == 'cobble':
        mat = 'M_Cobble'
        if color == 0xffffff:
            col = hx(0xcabda6)
        elif color == 0xd8cfc0:
            col = hx(0xb9ab95)
        if color == 0x6a6a6a:
            mat = 'M_Plaster'; col = hx(0x8e8e8a)
    else:
        mat = 'M_Terrain'
        if color in (0x55575a, 0x6a6c70):
            mat = 'M_Plaster'; col = mul(col, 1.05)
    nx = max(2, int(math.ceil(w / 4))); nz = max(2, int(math.ceil(d / 4)))
    for i in range(nx):
        for j in range(nz):
            x0 = cx - w / 2 + w * i / nx; x1 = cx - w / 2 + w * (i + 1) / nx
            z0 = cz - d / 2 + d * j / nz; z1 = cz - d / 2 + d * (j + 1) / nz
            pts = [(x0, Hs(x0, z0) + yo, z0), (x0, Hs(x0, z1) + yo, z1), (x1, Hs(x1, z1) + yo, z1), (x1, Hs(x1, z0) + yo, z0)]
            S = UVSCALE.get(mat, 4)
            emit(mat, pts, col, uvs=[(p[0] / S, -p[2] / S) for p in pts], ao=False)
    if key == 'cobble' and w * d > 150:  # stone curb around piazzas
        cc = hx(0xd9d2c2)
        for (ax_, az_, bx_, bz_) in ((cx - w / 2, cz - d / 2, cx + w / 2, cz - d / 2), (cx + w / 2, cz - d / 2, cx + w / 2, cz + d / 2),
                                     (cx + w / 2, cz + d / 2, cx - w / 2, cz + d / 2), (cx - w / 2, cz + d / 2, cx - w / 2, cz - d / 2)):
            n = max(1, int(math.hypot(bx_ - ax_, bz_ - az_) / 4))
            for k in range(n):
                t0, t1 = k / n, (k + 1) / n
                p0 = (ax_ + (bx_ - ax_) * t0, az_ + (bz_ - az_) * t0); p1 = (ax_ + (bx_ - ax_) * t1, az_ + (bz_ - az_) * t1)
                g0 = Hs(*p0) + yo + 0.06; g1 = Hs(*p1) + yo + 0.06
                seg_box((p0[0], g0, p0[1]), (p1[0], g1, p1[1]), 0.4, 0.14, 'M_Stone', cc)


# ---------------------------------------------------- loose primitives
WOODY = {0x7a5232, 0x8a6a42, 0x6a4a2e, 0x5a3a22, 0x6e4426, 0x7a5a3a, 0x8a6a4a, 0xa88658, 0x3a2416, 0x4a2c1a, 0x6a5a48}
ROCKS = {0x8a8678, 0x77736a, 0x9a968a, 0x6a675f}
KEYMAT = {'plain': 'M_Plain', 'plaster': 'M_Plaster', 'roof': 'M_Roof', 'foliage': 'M_Foliage', 'glow': 'M_Glow', 'lamp': 'M_LampGlow', 'cobble': 'M_Cobble', 'facade': 'M_Plaster'}


def build_loose(p, idx):
    prim, key, m, c = p['prim'], p['key'], p['m'], int(p['c'])
    col = hx(c)
    if prim == 'BoxGeometry':  # osteria / municipio facades
        bw, bh, bd = p['p']['width'], p['p']['height'], p['p']['depth']
        rot = math.atan2(m[8], m[10])
        x, cy, z = m[12], m[13], m[14]
        base, top = cy - bh / 2, cy + bh / 2
        F = Frame((x, 0, z), rot)
        if abs(x + 30) < 1:  # osteria: the door is a separate original part, keep sign area clear
            decorate_walls(F, bw, bd, base, top, col, 900 + idx, keepouts=[('front', -3.8, 3.8, top - 4.9, top - 2.4), ('front', -1.4, 1.4, base, base + 3.6)], balcony_ok=False)
        else:  # municipio
            gy = H(*F.p(0, 0, bd / 2 + 0.3)[::2])
            decorate_walls(F, bw, bd, base, top, col, 901, door=dict(color=hx(0x4a2c1a), gy=gy, w=1.8, h=2.8),
                           keepouts=[('front', -2.8, 2.8, top - 3.0, top - 1.0)], balcony_ok=True)
        return
    if prim == 'pyr' and key == 'roof':
        W_ = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2); rh = math.sqrt(m[4] ** 2 + m[5] ** 2 + m[6] ** 2)
        D_ = math.sqrt(m[8] ** 2 + m[9] ** 2 + m[10] ** 2)
        hip_roof(Frame((m[12], 0, m[14]), math.atan2(m[8], m[10])), W_, D_, m[13] - rh / 2, rh, col)
        return
    if prim == 'box' and key == 'foliage' and c == 0x4e7a2a:
        vine_row(m, col); return
    if prim == 'sph1' and c in ROCKS:
        rock(m, col); return
    mat = KEYMAT.get(key, 'M_Plain')
    if mat == 'M_Plain' and prim == 'box' and c in WOODY:
        mat = 'M_Wood'
    if c == 0x8a6a4a and prim == 'box':  # barns: wooden walls + door
        mat = 'M_Wood'
    if key == 'roof':
        emit_prim(prim, m, 'M_Roof', col, jit=0.04); return
    grad = None
    if mat == 'M_Foliage':
        sy = math.sqrt(m[4] ** 2 + m[5] ** 2 + m[6] ** 2)
        grad = (m[13] - sy / 2, m[13] + sy / 2, 0.8, 1.1)
    emit_prim(prim, m, mat, col, jit=0.035 if mat in ('M_Plain', 'M_Foliage') else 0.0, grad=grad)


# ============================================================== roads
def resample(d, step):
    out = [d[0]]
    for i in range(1, len(d)):
        a, b = d[i - 1], d[i]
        L_ = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(math.ceil(L_ / step)))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return out


def build_roads():
    for ri, r in enumerate(L['roads']):
        d = resample(r['dense'], 1.5); hw = r['w'] / 2; yo = r['yo'] + ri * 0.003
        mat = 'M_RoadMain' if r['main'] else 'M_RoadSmall'
        sh = 0.9  # gravel shoulder
        ncol = max(2, int(math.ceil(2 * hw / 2.2)))
        cols = [(hw + sh, -0.07, 0.0)] + [(hw - 2 * hw * k / ncol, 0.0, 0.1 + 0.8 * k / ncol) for k in range(ncol + 1)] + [(-hw - sh, -0.07, 1.0)]
        rows = []
        v = 0.0
        for i in range(len(d)):
            a = d[max(0, i - 1)]; b = d[min(len(d) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dz) or 1; dx /= l; dz /= l
            nx, nz = -dz, dx
            if i > 0:
                v += math.hypot(d[i][0] - d[i - 1][0], d[i][1] - d[i - 1][1])
            row = []
            for off, dy, u in cols:
                px, pz = d[i][0] + nx * off, d[i][1] + nz * off
                row.append((px, Hs(px, pz) + yo + dy, pz))
            rows.append((row, v / 9.0))
        us = [c[2] for c in cols]
        for i in range(1, len(rows)):
            (ra, va), (rb, vb) = rows[i - 1], rows[i]
            for k in range(len(cols) - 1):
                pts = [ra[k], ra[k + 1], rb[k + 1], rb[k]]
                uv = [(us[k], va), (us[k + 1], va), (us[k + 1], vb), (us[k], vb)]
                emit(mat, pts, (1, 1, 1), uvs=uv, center=(pts[0][0], pts[0][1] - 10, pts[0][2]), ao=False)


# ============================================================== terrain
def grid_lines(a, b, da, db, step_in, step_out, prio):
    reg = list(np.arange(a, da, step_out)) + list(np.arange(da, db, step_in)) + list(np.arange(db, b + 1e-6, step_out))
    prio = sorted(set([p for p in prio if a <= p <= b] + [a, b]))
    out = list(prio)
    for v in reg:
        if min(abs(v - p) for p in prio) > 1.2:
            out.append(float(v))
    return np.array(sorted(out))


def occlusion_map():
    gx0, gz0, res = -500.0, -440.0, 1.0
    nx, nz = 840, 740
    occ = np.zeros((nz, nx), np.float32)
    for (x0, z0, x1, z1, top, tag) in L['colliders']:
        if tag in ('tree', 'vine', 'rail', 'roccia', 'balla', 'deck'):
            continue
        i0 = int((x0 - 1.2 - gx0) / res); i1 = int((x1 + 1.2 - gx0) / res) + 1
        j0 = int((z0 - 1.2 - gz0) / res); j1 = int((z1 + 1.2 - gz0) / res) + 1
        occ[max(0, j0):max(0, j1), max(0, i0):max(0, i1)] = 1.0
    for rec in TREES:
        a = rec['args']; s = a[2] if len(a) > 2 and a[2] else 1
        rr = (2.0 if (len(a) > 3 and a[3] == 'pine') else 1.8) * s
        cx_, cz_ = (a[0] - gx0) / res, (a[1] - gz0) / res
        ri = int(rr / res) + 1
        for j in range(int(cz_) - ri, int(cz_) + ri + 1):
            for i in range(int(cx_) - ri, int(cx_) + ri + 1):
                if 0 <= j < nz and 0 <= i < nx and (i - cx_) ** 2 + (j - cz_) ** 2 <= (rr / res) ** 2:
                    occ[j, i] = max(occ[j, i], 0.75)
    f = np.fft.rfft2(occ, s=(nz + 64, nx + 64))
    ky = np.fft.fftfreq(nz + 64)[:, None]; kx = np.fft.rfftfreq(nx + 64)[None, :]
    sig = 2.2
    occ = np.fft.irfft2(f * np.exp(-2 * np.pi ** 2 * sig ** 2 * (kx ** 2 + ky ** 2)), s=(nz + 64, nx + 64))[:nz, :nx]

    def sample(x, z):
        fi = np.clip((x - gx0) / res, 0, nx - 1.001); fj = np.clip((z - gz0) / res, 0, nz - 1.001)
        i = fi.astype(int); j = fj.astype(int); u = fi - i; v = fj - j
        return (occ[j, i] * (1 - u) * (1 - v) + occ[j, i + 1] * u * (1 - v) + occ[j + 1, i] * (1 - u) * v + occ[j + 1, i + 1] * u * v)
    return sample


TOWNS = [(0, -18, 78), (-170, -14, 58), (170, -12, 55), (-392, -14, 52), (24, -128, 34)]


def forest_mask(x, z):
    f = (np.sin(x * 0.019 + np.sin(z * 0.013) * 1.7) * np.cos(z * 0.017 - x * 0.007) + 0.6 * np.sin(x * 0.041 - z * 0.033 + 1.1))
    return np.clip((f + 0.15) / 0.9, 0, 1)


def town_mask(x, z):
    m = np.zeros_like(x)
    for tx, tz, r in TOWNS:
        d = np.hypot(x - tx, z - tz)
        m = np.maximum(m, np.clip((r - d) / 18, 0, 1))
    return m


def terrain_colors(x, z, h):
    """Smooth (non-field) colour per vertex, sRGB float arrays (N,3)."""
    def C(c): return np.array(hx(c))[None, :]
    def lerp(a, b, t): return a * (1 - t[:, None]) + b * t[:, None]
    n1 = 0.5 + 0.5 * np.sin(x * 0.037 + np.sin(z * 0.021) * 2.0) * np.cos(z * 0.043 - x * 0.011)
    fm = forest_mask(x, z)
    meadow = lerp(C(0x668845), C(0x7c9a50), n1)
    forest = lerp(C(0x3f5f2c), C(0x35512a), n1)
    low = lerp(meadow, forest, np.clip(fm * 1.2, 0, 1) * np.clip((-z - 60) / 80, 0.25, 1))
    alp = lerp(C(0x608444), C(0x768f50), n1)
    mid = lerp(lerp(alp, forest * 1.05, np.clip(fm - 0.2, 0, 1)), C(0x8b8b78), np.clip((h - 560) / 200, 0, 1))
    col = lerp(low, mid, np.clip((h - 170) / 120, 0, 1))
    col = lerp(col, C(0x9c9c8e), np.clip((h - 620) / 120, 0, 1))
    gx_ = (H(x + 4, z) - H(x - 4, z)) / 8; gz_ = (H(x, z + 4) - H(x, z - 4)) / 8
    sl = np.hypot(gx_, gz_)
    rk = np.where(z < -150, np.clip((sl - 0.85) / 0.5, 0, 0.6), 0)
    col = lerp(col, C(0x7f8070), rk)
    tw = terrW(x, z) * 0.85
    col = lerp(col, C(0x86b052), tw)
    tm = town_mask(x, z)
    lawn = lerp(C(0x67874a), C(0x76944f), n1)
    col = lerp(col, lawn, tm * (z > -60))
    return col


def field_color(cx, cz):
    fi = math.floor(cx / 42); fj = math.floor(cz / 31)
    k = int(hr(fi, fj, 11) * len(FIELD_COLS))
    return np.array(hx(FIELD_COLS[k])) * (0.94 + 0.1 * hr(fi, fj, 12))


XS = None; ZS = None


def terrain_grid():
    global XS, ZS
    XS = grid_lines(-700, 700, -485, 330, 5, 20, [X0 + CHUNK * i for i in range(NCX + 1)] + [42 * k for k in range(-11, 8)] + [-480, 320])
    ZS = grid_lines(-780, 420, -420, 280, 5, 20, [Z0 + CHUNK * j for j in range(NCZ + 1)] + [31 * k for k in range(-1, 9)] + [-40])
    return XS, ZS


def Tmesh(x, z):
    """Height of the rendered terrain mesh (same grid and diagonal as build_terrain)."""
    i = int(np.clip(np.searchsorted(XS, x) - 1, 0, len(XS) - 2)); j = int(np.clip(np.searchsorted(ZS, z) - 1, 0, len(ZS) - 2))
    x0, x1, z0, z1 = XS[i], XS[i + 1], ZS[j], ZS[j + 1]
    u = (x - x0) / (x1 - x0); v = (z - z0) / (z1 - z0)
    ha, hb, hc, hd = float(H(x0, z0)), float(H(x0, z1)), float(H(x1, z1)), float(H(x1, z0))
    if v >= u:
        return ha + v * (hb - ha) + u * (hc - hb)
    return ha + u * (hd - ha) + v * (hc - hd)


def Hs(x, z):
    """Surface height for things laid on the ground: never below the rendered terrain."""
    return max(H(x, z), Tmesh(x, z))


def build_terrain(occ_sample):
    xs, zs = terrain_grid()
    objs = []
    for ci in range(NCX):
        for cj in range(NCZ):
            xa, xb = X0 + CHUNK * ci, X0 + CHUNK * (ci + 1)
            za, zb = Z0 + CHUNK * cj, Z0 + CHUNK * (cj + 1)
            gx = xs[(xs >= xa - 1e-6) & (xs <= xb + 1e-6)]; gz = zs[(zs >= za - 1e-6) & (zs <= zb + 1e-6)]
            Xg, Zg = np.meshgrid(gx, gz)  # (nz, nx)
            X = Xg.ravel(); Z = Zg.ravel(); Hh = H(X, Z)
            e = 0.6
            nxv = -(H(X + e, Z) - H(X - e, Z)) / (2 * e); nzv = -(H(X, Z + e) - H(X, Z - e)) / (2 * e)
            nl = np.sqrt(nxv ** 2 + 1 + nzv ** 2)
            normals = np.stack([nxv / nl, -nzv / nl, 1 / nl], 1)  # blender space
            vcol = terrain_colors(X, Z, Hh)
            shade = (0.93 + 0.1 * (0.5 + 0.5 * np.sin(X * 0.21 + Z * 0.17) * np.sin(X * 0.13 - Z * 0.29)))
            occ = occ_sample(X, Z)
            shade = shade * (1 - 0.4 * np.clip(occ, 0, 1))
            nx_, nz_ = len(gx), len(gz)
            faces = []; fcols = []
            for j in range(nz_ - 1):
                for i in range(nx_ - 1):
                    a = j * nx_ + i; b = (j + 1) * nx_ + i; c = (j + 1) * nx_ + i + 1; d = j * nx_ + i + 1
                    faces.append((a, b, c)); faces.append((a, c, d))
                    mx = (gx[i] + gx[i + 1]) / 2; mz = (gz[j] + gz[j + 1]) / 2
                    if mz > -40 and -480 < mx < 320 and town_mask(np.array([mx]), np.array([mz]))[0] < 0.5:
                        fc = field_color(mx, mz)
                        fcols.append([fc * shade[v] for v in (a, b, c)]); fcols.append([fc * shade[v] for v in (a, c, d)])
                    else:
                        fcols.append([vcol[v] * shade[v] for v in (a, b, c)]); fcols.append([vcol[v] * shade[v] for v in (a, c, d)])
            verts = np.stack([X, -Z, Hh], 1)
            name = f"T_{ci}_{cj}"
            me = bpy.data.meshes.new(name)
            me.from_pydata(verts.tolist(), [], faces)
            me.polygons.foreach_set('use_smooth', [True] * len(faces))
            me.use_auto_smooth = True
            me.normals_split_custom_set_from_vertices(normals.tolist())
            uv = me.uv_layers.new(name='UVMap')
            uvs = np.array([(X[v] / 8.0, -Z[v] / 8.0) for f in faces for v in f])
            uv.data.foreach_set('uv', uvs.astype(np.float32).ravel())
            cols = srgb_to_lin(np.array(fcols).reshape(-1, 3))
            ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
            ca.data.foreach_set('color', np.hstack([cols, np.ones((len(cols), 1))]).astype(np.float32).ravel())
            me.materials.append(MAT['M_Terrain'])
            ob = bpy.data.objects.new(name, me)
            COLL.objects.link(ob)
            objs.append(ob)
    return objs


def srgb_to_lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ============================================================== materials
MAT = {}
MAT_DEF = {
    'M_Terrain': ('grass', True), 'M_RoadMain': ('asphalt_main', False), 'M_RoadSmall': ('asphalt_small', False),
    'M_Cobble': ('cobble', True), 'M_Plaster': ('plaster', True), 'M_Stone': ('stone', True), 'M_Roof': ('roof', True),
    'M_Wood': ('wood', True), 'M_Detail': ('detail', True), 'M_Window': ('window', False), 'M_WindowLit': ('window', False),
    'M_Plain': (None, True), 'M_Foliage': (None, True), 'M_LampGlow': (None, True), 'M_Glow': (None, True),
}


def make_materials():
    for name, (tex, vcol) in MAT_DEF.items():
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
        if name == 'M_Glow':
            em = nt.nodes.new('ShaderNodeEmission'); em.location = (300, 0)
            va = nt.nodes.new('ShaderNodeVertexColor'); va.layer_name = 'Col'; va.location = (0, 0)
            nt.links.new(va.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
            MAT[name] = m
            continue
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.location = (300, 0)
        bs.inputs['Roughness'].default_value = 0.92 if name not in ('M_Window', 'M_WindowLit') else 0.25
        bs.inputs['Specular'].default_value = 0.15 if name not in ('M_Window', 'M_WindowLit') else 0.5
        nt.links.new(bs.outputs[0], out.inputs['Surface'])
        src = None
        if tex:
            it = nt.nodes.new('ShaderNodeTexImage'); it.location = (-300, 100)
            img = bpy.data.images.get(tex + '.png') or bpy.data.images.load(os.path.join(TEXDIR, tex + '.png'), check_existing=True)
            img.reload()
            it.image = img
            src = it.outputs['Color']
        if vcol:
            va = nt.nodes.new('ShaderNodeVertexColor'); va.layer_name = 'Col'; va.location = (-300, -150)
            if src is not None:
                mx = nt.nodes.new('ShaderNodeMixRGB'); mx.blend_type = 'MULTIPLY'; mx.inputs['Fac'].default_value = 1.0; mx.location = (0, 0)
                nt.links.new(src, mx.inputs['Color1']); nt.links.new(va.outputs['Color'], mx.inputs['Color2'])
                src = mx.outputs['Color']
            else:
                src = va.outputs['Color']
        if src is not None:
            nt.links.new(src, bs.inputs['Base Color'])
        if name == 'M_LampGlow':
            bs.inputs['Emission Strength'].default_value = 0.0
        MAT[name] = m
    return MAT


# ============================================================== assembling blender objects
COLL = None


def get_collection(name='BorsoWorld'):
    global COLL
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    COLL = c
    return c


def clear_collection():
    c = get_collection()
    for o in list(c.objects):
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def finalize_chunks():
    objs = []
    for (ci, cj), mats in sorted(CH.items()):
        names = sorted(mats.keys())
        P = []; C = []; UV = []; F = []; A = []; MI = []
        for k, mn in enumerate(names):
            b = mats[mn]
            P.extend(b.P); C.extend(b.C); UV.extend(b.UV); F.extend(b.F); A.extend(b.A); MI.extend([k] * len(b.F))
        if not F:
            continue
        P = np.array(P, float); C = np.array(C, float); A = np.array(A, bool)
        # ambient occlusion from height above ground
        if A.any():
            agl = P[A, 1] - H(P[A, 0], P[A, 2])
            t = np.clip(agl / 2.4, 0, 1)
            C[A] *= (0.66 + 0.34 * (t * t * (3 - 2 * t)))[:, None]
        cols = srgb_to_lin(C)
        nv = len(P)
        name = f"C_{ci}_{cj}"
        me = bpy.data.meshes.new(name)
        me.vertices.add(nv)
        me.vertices.foreach_set('co', np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1).astype(np.float32).ravel())
        me.loops.add(nv)
        me.loops.foreach_set('vertex_index', np.arange(nv, dtype=np.int32))
        me.polygons.add(len(F))
        starts = np.concatenate([[0], np.cumsum(F)[:-1]])
        me.polygons.foreach_set('loop_start', starts.astype(np.int32))
        me.polygons.foreach_set('loop_total', np.array(F, dtype=np.int32))
        me.polygons.foreach_set('material_index', np.array(MI, dtype=np.int32))
        me.update(calc_edges=True)
        uv = me.uv_layers.new(name='UVMap')
        uv.data.foreach_set('uv', np.array(UV, np.float32).ravel())
        ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        ca.data.foreach_set('color', np.hstack([cols, np.ones((nv, 1))]).astype(np.float32).ravel())
        for mn in names:
            me.materials.append(MAT[mn])
        ob = bpy.data.objects.new(name, me)
        COLL.objects.link(ob)
        objs.append(ob)
    return objs


# ============================================================== extra static pieces from the original
def build_extras():
    # Sacrario del Grappa (summit)
    x, z = -40, -640
    y = H(x, z)
    for i in range(5):
        r = 26 - i * 4.5
        n = 28
        emit_prim('cyl', M(x, y + 2 + i * 4, z, 0, 2 * r, 4, 2 * r), 'M_Plaster', hx(0xe8e4da))
        for k in range(n):  # dark arches band
            a = k / n * 2 * math.pi
            Fk = Frame((x, 0, z), a)
            Wk = Wall(Fk, ('front', (0, r * 0.985), (1, 0), (0, 1), 4))
            Wk.quad('M_Plain', -0.9, 0.9, y + 0.6 + i * 4, y + 3.0 + i * 4, 0.05, hx(0x5a5850))
    obox((x, y + 24, z), (1, 0, 0), (0, 1, 0), (0, 0, 1), 2.5, 4.5, 2.5, 'M_Plaster', hx(0xe8e4da))
    # farmacia: green cross
    yy = H(20, 9.7)
    obox((23.6, yy + 3.6, 9.86), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.55, 0.18, 0.1, 'M_Glow', hx(0x22c25a))
    obox((23.6, yy + 3.6, 9.86), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.18, 0.55, 0.1, 'M_Glow', hx(0x22c25a))


# ============================================================== main
TREES = []


def collect():
    """Flatten layout records into categories."""
    out = {'house': [], 'tree': [], 'lamp': [], 'bench': [], 'church': [], 'sign': [], 'drape': [], 'loose': [], 'wallsign': []}
    top = L['top']
    for i, r in enumerate(top):
        if 'prim' in r:
            out['loose'].append(r); continue
        fn = r['fn']
        if fn == 'placeHouse':
            shop = None
            nxt = top[i + 1] if i + 1 < len(top) else None
            opts = r['args'][7] if len(r['args']) > 7 and r['args'][7] else {}
            if nxt is not None and nxt.get('fn') == 'wallSign' and opts.get('recruitable') is False:
                sx, sy, sz, sry, _tex, sw, shh = nxt['args'][:7]
                shop = dict(sign_bottom=sy - shh / 2, keep=[('front', -sw / 2 - 0.2, sw / 2 + 0.2, sy - shh / 2 - 0.2, sy + shh / 2 + 0.2)])
            out['house'].append((r, shop))
        elif fn == 'tree': out['tree'].append(r)
        elif fn == 'lamp': out['lamp'].append(r)
        elif fn == 'bench': out['bench'].append(r)
        elif fn == 'church': out['church'].append(r)
        elif fn == 'placeSign': out['sign'].append(r)
        elif fn == 'drapedArea': out['drape'].append(r)
        elif fn == 'wallSign': out['wallsign'].append(r)
    return out


def build_forest():
    WB = L['WB']
    n = 0
    step = 14.0
    for gz in np.arange(-770, 410, step):
        for gx in np.arange(-690, 690, step):
            x = gx + (hr(gx, gz, 1) - 0.5) * step * 0.9; z = gz + (hr(gx, gz, 2) - 0.5) * step * 0.9
            if WB['x0'] - 25 < x < WB['x1'] + 25 and z > WB['z0'] - 25:
                continue
            if math.hypot(x - SAC['x'], z - SAC['z']) < SAC['r1'] + 25 or (abs(x - SAC['x']) < 18 and SAC['z'] - 200 < z < SAC['z']):
                continue  # Sacrario, Via Eroica e Portale liberi
            fm = float(forest_mask(np.array([x]), np.array([z]))[0])
            h = H(x, z)
            if h > 640 or hr(gx, gz, 3) > fm * 0.9:
                continue
            s_ = 1.3 + 1.2 * hr(gx, gz, 4)
            y = h
            c = hx([0x2f4f2a, 0x34552c, 0x2a4626, 0x355a2e][int(hr(gx, gz, 5) * 4)])
            emit_prim('cyl6', M(x, y + 1.0 * s_, z, 0, 0.42 * s_, 2.0 * s_, 0.42 * s_), 'M_Wood', hx(0x4a3426), skip_bottom=True)
            pine_tier(x, y + 3.2 * s_, z, 2.2 * s_, 4.4 * s_, c, gx)
            pine_tier(x, y + 5.8 * s_, z, 1.5 * s_, 3.8 * s_, mul(c, 1.1), gz)
            n += 1
    return n


def build(stages=('terrain', 'roads', 'buildings', 'veg', 'props')):
    global TREES
    import time
    t0 = time.time()
    CH.clear()
    get_collection(); clear_collection(); make_materials()
    cat = collect()
    TREES = cat['tree']
    log = {'h_err': check_heights()}
    terrain_grid()
    if 'terrain' in stages:
        build_terrain(occlusion_map())
    if 'roads' in stages:
        build_roads()
        for r in cat['drape']: build_drape(r)
    if 'buildings' in stages:
        for i, (r, shop) in enumerate(cat['house']): build_house(r, i, shop)
        for r in cat['church']: build_church(r)
    if 'veg' in stages:
        for r in cat['tree']: build_tree(r)
        log['forest'] = build_forest()
    if 'props' in stages:
        for r in cat['lamp']: build_lamp(r)
        for r in cat['bench']: build_bench(r)
        for r in cat['sign']: build_sign(r)
        for i, p in enumerate(cat['loose']): build_loose(p, i)
        build_extras()
    objs = finalize_chunks()
    tris = 0
    for o in COLL.objects:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    log.update(objects=len(COLL.objects), tris=tris, secs=round(time.time() - t0, 1))
    return log


# ============================================================== export
def export_glb(path=os.path.join(ROOT, "docs", "models", "world.glb"), draco=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in COLL.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = COLL.objects[0]
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_colors=True, export_normals=True,
              export_texcoords=True, export_materials='EXPORT', export_yup=True, export_apply=False,
              export_cameras=False, export_lights=False, export_extras=False)
    fmts = [i.identifier for i in props['export_image_format'].enum_items]
    kw['export_image_format'] = 'NONE' if 'NONE' in fmts else 'JPEG'
    if draco:
        kw.update(export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                  export_draco_position_quantization=16, export_draco_normal_quantization=10,
                  export_draco_texcoord_quantization=12, export_draco_color_quantization=10)
    bpy.ops.export_scene.gltf(**kw)
    return path, os.path.getsize(path), kw['export_image_format']
