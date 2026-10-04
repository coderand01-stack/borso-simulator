"""Borso Simulator HD - shop/house interiors rebuilt in Blender (docs/models/rooms.glb).

Input: tools/out/rooms.json, captured from the game by tools/instrumented.html (exact boxes, cylinders,
planes and lights of every room). Each static primitive is rebuilt with real materials (wood, tiles,
plaster, stone) and every room gets extra details: wainscoting, windows with daylight, pendant lamps over
the lights, ceiling beams in the rustic rooms, pictures. Glowing parts (MeshBasic), canvas signs, NPCs and
animated objects stay in the game, which hides only the static primitives this file replaces.
Room space = game interior space (x right, y up, z towards the door), Blender = (x, -z, y).
"""
import bpy, math, os, json, colorsys, io, contextlib
import numpy as np

ROOT = r"C:\Coding\borso-simulator"
TEXDIR = os.path.join(ROOT, "docs", "textures")
ROOMS = json.load(open(os.path.join(ROOT, "tools", "out", "rooms.json"), encoding="utf-8"))

MATS = {  # name: (texture, uv metres per tile)
    'R_Wood': ('wood', 1.2), 'R_Floor': ('wood', 1.6), 'R_Plaster': ('plaster', 2.5), 'R_Stone': ('stone', 2.0),
    'R_Tile': ('tile', 1.2), 'R_Plain': (None, 1), 'R_Glass': (None, 1), 'R_Sky': (None, 1), 'R_Bulb': (None, 1),
}
STYLE = {  # wainscot colour/material, beams, windows
    'osteria': dict(wains=None, beams=False, win=('right',), pics=2),
    'farmacia': dict(wains=('R_Tile', 0xe8f2ea, 1.2), beams=False, win=('left', 'right'), pics=1),
    'tabacchi': dict(wains=('R_Wood', 0x4a3222, 1.0), beams=False, win=('left',), pics=2),
    'pizzeria': dict(wains=('R_Tile', 0xe8d8b8, 1.1), beams=True, win=('right',), pics=2),
    'scuola': dict(wains=None, beams=False, win=('left', 'right'), pics=2),
    'alimentari': dict(wains=('R_Wood', 0x5a3a22, 1.0), beams=False, win=('left',), pics=1),
    'cubamia': dict(wains=None, beams=False, win=(), pics=0),
    'malga': dict(wains=None, beams=True, win=('left', 'right'), pics=1),
}


def hx(c):
    return ((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0


def lin(c):
    return tuple((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def woody(c):
    h, s, v = colorsys.rgb_to_hsv(*hx(c))
    return 0.02 < h < 0.13 and s > 0.3 and v < 0.62


class Room:
    def __init__(self, key):
        self.key = key; self.bufs = {}

    def poly(self, mat, pts, col, uvs=None, face=None):
        b = self.bufs.setdefault(mat, dict(P=[], C=[], UV=[], F=[]))
        if face is not None:  # flip so the normal points along 'face'
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = pts[0], pts[1], pts[2]
            n = ((by - ay) * (cz - az) - (bz - az) * (cy - ay), (bz - az) * (cx - ax) - (bx - ax) * (cz - az), (bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
            if n[0] * face[0] + n[1] * face[1] + n[2] * face[2] < 0:
                pts = pts[::-1]
                if uvs is not None:
                    uvs = uvs[::-1]
        if uvs is None:
            uvs = planar(pts, MATS[mat][1])
        k = []
        for (x, y, z) in pts:
            ao = 0.78 + 0.22 * min(1.0, max(0.0, y / 1.1)) if mat not in ('R_Sky', 'R_Bulb', 'R_Glass') else 1.0
            k.append(tuple(v * ao for v in col))
        b['P'] += pts; b['C'] += k; b['UV'] += uvs; b['F'].append(len(pts))

    def box(self, mat, M, col, sx=1, sy=1, sz=1, skip=()):
        c = [(x * sx, y * sy, z * sz) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
        faces = {'-x': (0, 1, 3, 2), '+x': (4, 6, 7, 5), '-y': (0, 4, 5, 1), '+y': (2, 3, 7, 6), '-z': (0, 2, 6, 4), '+z': (1, 5, 7, 3)}
        for nm, q in faces.items():
            if nm in skip:
                continue
            self.poly(mat, [xf(M, c[i]) for i in q], col)

    def cyl(self, mat, M, col, rt, rb, h, n):
        n = max(6, min(int(n), 16))
        top = [(rt * math.sin(i / n * 2 * math.pi), h / 2, rt * math.cos(i / n * 2 * math.pi)) for i in range(n)]
        bot = [(rb * math.sin(i / n * 2 * math.pi), -h / 2, rb * math.cos(i / n * 2 * math.pi)) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            self.poly(mat, [xf(M, bot[i]), xf(M, bot[j]), xf(M, top[j]), xf(M, top[i])], col)
        if rt > 0:
            self.poly(mat, [xf(M, p) for p in top], col)
        self.poly(mat, [xf(M, p) for p in bot[::-1]], col)

    def dome(self, mat, M, col, r, nu=14, nv=6):
        for j in range(nv):
            a0, a1 = j / nv * math.pi / 2, (j + 1) / nv * math.pi / 2
            for i in range(nu):
                b0, b1 = i / nu * 2 * math.pi, (i + 1) / nu * 2 * math.pi
                p = lambda a, b: xf(M, (r * math.cos(a) * math.sin(b), r * math.sin(a), r * math.cos(a) * math.cos(b)))
                self.poly(mat, [p(a0, b0), p(a0, b1), p(a1, b1), p(a1, b0)], col)


def xf(m, p):
    return (m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13], m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14])


def T(x, y, z, sx=1, sy=1, sz=1, ry=0.0):
    c, s = math.cos(ry), math.sin(ry)
    return [c * sx, 0, -s * sx, 0, 0, sy, 0, 0, s * sz, 0, c * sz, 0, x, y, z, 1]


def planar(pts, S):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = pts[0], pts[1], pts[2]
    ux, uy, uz = bx - ax, by - ay, bz - az; vx, vy, vz = cx - ax, cy - ay, cz - az
    n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    l = math.sqrt(sum(v * v for v in n)) or 1; n = tuple(v / l for v in n)
    if abs(n[1]) > 0.8:
        return [(p[0] / S, -p[2] / S) for p in pts]
    u = (n[2], 0, -n[0]); ul = math.hypot(u[0], u[2]) or 1; u = (u[0] / ul, 0, u[2] / ul)
    return [((p[0] * u[0] + p[2] * u[2]) / S, p[1] / S) for p in pts]


def rebuild(key, data):
    R = Room(key)
    w, d, h = data['w'], data['d'], data['h']
    for p in data['prims']:
        if p['basic'] or p['tex'] == 'canvas':
            continue
        t, m, c = p['t'], p['m'], int(p['c'])
        col = hx(c)
        if t == 'PlaneGeometry':
            ny = m[9]  # local +z mapped to world y
            mat = {'plank': 'R_Floor', 'tile': 'R_Tile', 'stone': 'R_Stone'}.get(p['tex'], 'R_Plaster')
            W, Hh = p['p']['width'], p['p']['height']
            pts = [xf(m, (-W / 2, -Hh / 2, 0)), xf(m, (W / 2, -Hh / 2, 0)), xf(m, (W / 2, Hh / 2, 0)), xf(m, (-W / 2, Hh / 2, 0))]
            if p['tex'] == 'plank' and c == 0xffffff:
                col = hx(0x8a5a36)  # untinted plank floor -> warm oak
            R.poly(mat, pts, col)
        elif t == 'BoxGeometry':
            pp = p['p']
            if p['tex'] in ('plaster', 'stone'):
                mat = 'R_Stone' if p['tex'] == 'stone' else 'R_Plaster'
            else:
                mat = 'R_Wood' if woody(c) else 'R_Plain'
            R.box(mat, m, col, pp['width'], pp['height'], pp['depth'])
        elif t == 'CylinderGeometry':
            pp = p['p']
            mat = 'R_Glass' if p['op'] < 0.99 else ('R_Wood' if woody(c) else 'R_Plain')
            R.cyl(mat, m, col, pp['radiusTop'], pp['radiusBottom'], pp['height'], pp['radialSegments'])
        elif t == 'SphereGeometry':
            R.dome('R_Stone', m, col, p['p']['radius'])
    extras(R, key, w, d, h, data)
    return R


def wall_free(data, side, z0, z1, y0, y1, w):
    x = -w / 2 if side == 'left' else w / 2
    for p in data['prims']:
        if p['t'] != 'BoxGeometry' or p['tex'] in ('plaster', 'stone'):
            continue
        m = p['m']; pp = p['p']
        cx, cy, cz = m[12], m[13], m[14]
        hx_ = abs(m[0]) * pp['width'] / 2 + abs(m[8]) * pp['depth'] / 2; hz = abs(m[2]) * pp['width'] / 2 + abs(m[10]) * pp['depth'] / 2
        if abs(cx - x) - hx_ < 0.9 and cz + hz > z0 and cz - hz < z1 and cy + abs(m[5]) * pp['height'] / 2 > y0 and cy - abs(m[5]) * pp['height'] / 2 < y1:
            return False
    return True


def extras(R, key, w, d, h, data):
    st = STYLE.get(key, {})
    rng = np.random.default_rng(len(key) * 7 + 3)
    # wainscoting on the back and side walls
    if st.get('wains'):
        mat, c, hh = st['wains']; col = hx(c)
        R.box(mat, T(0, hh / 2, -d / 2 + 0.035), col, w - 0.02, hh, 0.07, skip=('-z',))
        for sx in (-1, 1):
            R.box(mat, T(sx * (w / 2 - 0.035), hh / 2, 0), col, 0.07, hh, d - 0.02, skip=('-x' if sx < 0 else '+x',))
        R.box('R_Wood', T(0, hh + 0.03, -d / 2 + 0.05), hx(0x3a2414), w, 0.06, 0.1)
        for sx in (-1, 1):
            R.box('R_Wood', T(sx * (w / 2 - 0.05), hh + 0.03, 0), hx(0x3a2414), 0.1, 0.06, d)
    # crown moulding
    R.box('R_Plaster', T(0, h - 0.08, -d / 2 + 0.06), hx(0xf4efe4), w, 0.16, 0.12)
    for sx in (-1, 1):
        R.box('R_Plaster', T(sx * (w / 2 - 0.06), h - 0.08, 0), hx(0xf4efe4), 0.12, 0.16, d)
    # beams
    if st.get('beams'):
        x = -w / 2 + 0.9
        while x < w / 2 - 0.5:
            R.box('R_Wood', T(x, h - 0.17, 0), hx(0x4a3020), 0.26, 0.3, d - 0.02); x += 1.8
    # windows with daylight on the side walls
    for side in st.get('win', ()):
        sx = -1 if side == 'left' else 1
        for zc in (-d / 4, d / 4):
            if not wall_free(data, side, zc - 0.8, zc + 0.8, 0.9, 2.4, w):
                continue
            x = sx * (w / 2 - 0.02)
            R.box('R_Wood', T(x - sx * 0.04, 1.75, zc), hx(0xf2efe6), 0.08, 1.5, 1.25)
            R.poly('R_Sky', [(x - sx * 0.09, 1.08, zc - 0.5), (x - sx * 0.09, 1.08, zc + 0.5), (x - sx * 0.09, 2.42, zc + 0.5), (x - sx * 0.09, 2.42, zc - 0.5)],
                   hx(0xcfe6f6), uvs=[(0, 0)] * 4, face=(-sx, 0, 0))
            R.box('R_Wood', T(x - sx * 0.1, 1.75, zc), hx(0xf2efe6), 0.03, 1.36, 0.05)
            R.box('R_Wood', T(x - sx * 0.1, 1.95, zc), hx(0xf2efe6), 0.03, 0.05, 1.0)
            R.box('R_Stone', T(x - sx * 0.13, 0.98, zc), hx(0xd8d0c0), 0.24, 0.06, 1.35)
    # pendant lamps over the room lights
    for (lx, ly, lz, lc, li, ld) in data['lights']:
        if ly < 2.2:
            continue
        top = h; y = min(ly, h - 0.35)
        R.box('R_Plain', T(lx, (top + y + 0.3) / 2, lz), hx(0x222222), 0.02, top - y - 0.3, 0.02)
        R.cyl('R_Plain', T(lx, y + 0.18, lz), hx(0x2f4a3a if key != 'cubamia' else 0x2a2340), 0.06, 0.32, 0.26, 12)
        R.cyl('R_Bulb', T(lx, y + 0.06, lz), hx(lc), 0.09, 0.09, 0.08, 10)
    # pictures
    for i in range(st.get('pics', 0)):
        x = (-0.25 + 0.5 * i) * w if st.get('pics', 0) > 1 else w * 0.3
        R.box('R_Wood', T(x, 2.1, -d / 2 + 0.03), hx(0x6a4026), 0.9, 0.7, 0.04)
        R.box('R_Plain', T(x, 2.1, -d / 2 + 0.055), hx(int(rng.choice([0x5e7a4a, 0x8a5a3a, 0x3a5a8a, 0xb8a060]))), 0.76, 0.56, 0.01)
    return R


def make_material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs['Surface']); bs.inputs['Roughness'].default_value = 0.85
    va = nt.nodes.new('ShaderNodeVertexColor'); va.layer_name = 'Col'
    tex = MATS[name][0]
    if tex:
        it = nt.nodes.new('ShaderNodeTexImage')
        it.image = bpy.data.images.load(os.path.join(TEXDIR, tex + '.png'), check_existing=True)
        mx = nt.nodes.new('ShaderNodeMixRGB'); mx.blend_type = 'MULTIPLY'; mx.inputs['Fac'].default_value = 1
        nt.links.new(it.outputs['Color'], mx.inputs['Color1']); nt.links.new(va.outputs['Color'], mx.inputs['Color2'])
        nt.links.new(mx.outputs['Color'], bs.inputs['Base Color'])
    else:
        nt.links.new(va.outputs['Color'], bs.inputs['Base Color'])
    if name == 'R_Glass':
        bs.inputs['Alpha'].default_value = 0.75; m.blend_method = 'BLEND'
    if name in ('R_Sky', 'R_Bulb'):
        nt.links.new(va.outputs['Color'], bs.inputs['Emission']); bs.inputs['Emission Strength'].default_value = 1.0
    return m


def to_object(R, coll):
    names = sorted(R.bufs)
    P = []; C = []; UV = []; F = []; MI = []
    for k, n in enumerate(names):
        b = R.bufs[n]; P += b['P']; C += b['C']; UV += b['UV']; F += b['F']; MI += [k] * len(b['F'])
    P = np.array(P, float); nv = len(P)
    me = bpy.data.meshes.new('room_' + R.key)
    me.vertices.add(nv); me.vertices.foreach_set('co', np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1).astype(np.float32).ravel())
    me.loops.add(nv); me.loops.foreach_set('vertex_index', np.arange(nv, dtype=np.int32))
    me.polygons.add(len(F))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(F)[:-1]]).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.array(F, np.int32)); me.polygons.foreach_set('material_index', np.array(MI, np.int32))
    me.update(calc_edges=True)
    uv = me.uv_layers.new(name='UVMap'); uv.data.foreach_set('uv', np.array(UV, np.float32).ravel())
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
    cols = np.array([lin(c) for c in C], np.float32)
    ca.data.foreach_set('color', np.hstack([cols, np.ones((nv, 1), np.float32)]).ravel())
    for n in names:
        me.materials.append(make_material(n))
    ob = bpy.data.objects.new('room_' + R.key, me); coll.objects.link(ob)
    return ob


def build(export=True):
    c = bpy.data.collections.get('Rooms')
    if c is None:
        c = bpy.data.collections.new('Rooms'); bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    objs = []; log = {}
    for key, data in ROOMS.items():
        R = rebuild(key, data)
        ob = to_object(R, c); objs.append(ob)
        ob.data.calc_loop_triangles(); log[key] = len(ob.data.loop_triangles)
    if export:
        path = os.path.join(ROOT, 'docs', 'models', 'rooms.glb')
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        with contextlib.redirect_stdout(io.StringIO()):
            bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_image_format='JPEG',
                                      export_yup=True, export_colors=True, export_cameras=False, export_lights=False,
                                      export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7)
        log['bytes'] = os.path.getsize(path)
    return log
