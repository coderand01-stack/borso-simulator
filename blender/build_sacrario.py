"""Borso Simulator HD - Sacrario militare del Monte Grappa (hd/models/sacrario.glb).

Visual landmark on the summit, outside the playable area (game x=-40, z=-640, on the levelled square
SAC of build_world.H). Low-poly but recognisable: five circular stepped tiers with rows of bronze niches,
the central stairway facing the plain, the Madonnina chapel on top, the Via Eroica with its stone
pillars running north to the Portale di Roma.
Everything is built in GAME coords and converted to Blender as (x, -z, y); colours are vertex colours.
Run in Blender:  exec(open(r"C:\\Coding\\borso-simulator\\blender\\build_sacrario.py").read()); build()
"""
import bpy, bmesh, math, os, io, contextlib
import numpy as np

ROOT = r"C:\Coding\borso-simulator"
_w = {'np': np}
_src = open(os.path.join(ROOT, 'blender', 'build_world.py'), encoding='utf-8').read()
exec(_src[_src.index('GT = dict'):_src.index('def check_heights')], _w)
H = _w['H']; SAC = _w['SAC']

CX, CZ = SAC['x'], SAC['z']
Y0 = SAC['y']
STONE = 0xe4dfd2; STONE2 = 0xd2ccbe; PAVE = 0xc9c2b2; NICHE = 0x5c4a30; DARK = 0x3a3530; STATUE = 0xf4f1e8; DOME = 0x9aa69c


def lin(c):
    # bmesh loop colours are byte colours stored as sRGB: the glTF exporter linearises them, the game converts back
    return tuple((((c >> s) & 255) / 255) for s in (16, 8, 0)) + (1.0,)


class Mesh:
    def __init__(self):
        self.bm = bmesh.new(); self.col = self.bm.loops.layers.color.new('Col')

    def face(self, pts, c):
        vs = [self.bm.verts.new((p[0], -p[2], p[1])) for p in pts]
        f = self.bm.faces.new(vs)
        for l in f.loops:
            l[self.col] = lin(c)
        return f

    def box(self, cx, cy, cz, sx, sy, sz, c, ry=0.0, top=None):
        ca, sa = math.cos(ry), math.sin(ry)
        P = lambda x, y, z: (cx + x * ca + z * sa, cy + y, cz - x * sa + z * ca)
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        v = [P(x, y, z) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
        # v index: x*4 + y*2 + z
        quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for k, q in enumerate(quads):
            self.face([v[i] for i in q], (top if (top is not None and k == 3) else c))

    def lathe(self, cx, cz, prof, n, c):
        rings = []
        for r, y in prof:
            rings.append([(cx + r * math.cos(2 * math.pi * i / n), y, cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)])
        for a, b in zip(rings, rings[1:]):
            for i in range(n):
                j = (i + 1) % n
                self.face([a[i], a[j], b[j], b[i]], c)

    def finish(self, name, coll):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name); self.bm.to_mesh(me); self.bm.free()
        ca = me.color_attributes.get('Col')
        if ca is not None:  # the glTF exporter only writes the active colour attribute
            me.color_attributes.active_color = ca
            try:
                me.color_attributes.render_color_index = me.color_attributes.active_color_index
            except AttributeError:
                pass
        o = bpy.data.objects.new(name, me); coll.objects.link(o)
        return o


def tiers(m):
    n = 72
    R = [30.0 - 3.6 * k for k in range(5)]; th = 5.4  # steep enough to rise above the crest seen from the town
    m.lathe(CX, CZ, [(34.6, Y0 - 45.0), (34.0, Y0 - 0.2), (34.6, Y0 + 0.4), (R[0] + 0.01, Y0 + 0.4)], n, STONE2)  # stone podium on the crest
    for k, r in enumerate(R):
        y0 = Y0 + 0.4 + th * k; y1 = y0 + th
        rin = R[k + 1] if k + 1 < len(R) else 0.0
        m.lathe(CX, CZ, [(r, y0), (r, y1 - 0.5), (r + 0.25, y1 - 0.5), (r + 0.25, y1), (rin + (0.01 if rin else 0), y1)], n, STONE)
        if rin:
            m.lathe(CX, CZ, [(rin + 1.0, y1 + 0.05), (rin + 1.0, y1 + 1.1), (rin + 1.25, y1 + 1.1)], n, STONE2)  # parapet hint
        # bronze niches (loculi): two rows on the outer wall, except where the stairway passes (south, +z)
        cols = int(2 * math.pi * r / 1.5)
        for i in range(cols):
            a = 2 * math.pi * (i + 0.5) / cols
            sx, sz = math.cos(a), math.sin(a)
            if sz > 0 and abs(sx) * r < 4.6:  # stairway gap
                continue
            tx, tz = -sz, sx
            for row in range(2):
                yb = y0 + 0.7 + row * 1.6; yt = yb + 1.15
                rr = r + 0.04; w = 0.45
                m.face([(CX + sx * rr - tx * w, yb, CZ + sz * rr - tz * w), (CX + sx * rr + tx * w, yb, CZ + sz * rr + tz * w),
                        (CX + sx * rr + tx * w, yt, CZ + sz * rr + tz * w), (CX + sx * rr - tx * w, yt, CZ + sz * rr - tz * w)], NICHE)
    # central stairway on the south side, one flight per tier
    for k, r in enumerate(R):
        y0 = Y0 + 0.4 + th * k
        steps = 12
        rin = R[k + 1] if k + 1 < len(R) else 0.0
        z_out = CZ + r + 3.0; z_in = CZ + r - 0.2
        for s in range(steps):
            t0 = s / steps
            zz = z_out + (z_in - z_out) * t0
            hgt = th * (s + 1) / steps
            m.box(CX, y0 + hgt / 2, zz, 8.0, hgt, (z_out - z_in) / steps + 0.02, STONE2, top=PAVE)
        for sx in (-1, 1):
            m.box(CX + sx * 4.3, y0 + th / 2 + 0.3, (z_out + z_in) / 2, 0.6, th + 0.6, z_out - z_in, STONE)
    return Y0 + 0.4 + th * 5


def chapel(m, ytop):
    m.lathe(CX, CZ, [(5.4, ytop), (5.4, ytop + 5.6), (5.9, ytop + 5.8), (5.9, ytop + 6.3), (0.01, ytop + 6.3)], 24, STONE)
    m.lathe(CX, CZ, [(4.8, ytop + 6.3), (4.5, ytop + 8.0), (3.4, ytop + 9.6), (1.4, ytop + 10.5), (0.01, ytop + 10.6)], 24, DOME)
    # door + windows facing south
    m.face([(CX - 0.9, ytop, CZ + 5.42), (CX + 0.9, ytop, CZ + 5.42), (CX + 0.9, ytop + 2.8, CZ + 5.42), (CX - 0.9, ytop + 2.8, CZ + 5.42)], DARK)
    # the Madonnina on her pedestal
    m.box(CX, ytop + 11.2, CZ, 1.2, 1.6, 1.2, STONE2)
    m.lathe(CX, CZ, [(0.75, ytop + 12.0), (0.58, ytop + 13.6), (0.42, ytop + 14.4), (0.33, ytop + 14.5), (0.01, ytop + 14.5)], 12, STATUE)
    m.lathe(CX, CZ, [(0.01, ytop + 14.5), (0.27, ytop + 14.7), (0.24, ytop + 15.1), (0.01, ytop + 15.25)], 10, STATUE)
    # flagpole with the tricolore
    fx, fz = CX + 9.0, CZ + 6.5
    m.box(fx, ytop + 6.0, fz, 0.18, 12.0, 0.18, STONE)
    for i, c in enumerate((0x1d8a3a, 0xf4f4f0, 0xc8242c)):
        x0 = fx + 0.1 + i * 1.0
        m.box(x0 + 0.5, ytop + 10.8, fz, 1.0, 2.0, 0.04, c)


def via_eroica(m):
    z0 = CZ - 33.0; z1 = CZ - 165.0
    nseg = 25
    for i in range(nseg):
        za = z0 + (z1 - z0) * i / nseg; zb = z0 + (z1 - z0) * (i + 1) / nseg
        ya = float(H(CX, za)) + 0.35; yb = float(H(CX, zb)) + 0.35
        for x0, x1, c in ((-3.5, 3.5, PAVE),):
            m.face([(CX + x0, ya, za), (CX + x1, ya, za), (CX + x1, yb, zb), (CX + x0, yb, zb)], c)
            for xe in (x0, x1):
                m.face([(CX + xe, ya - 2.5, za), (CX + xe, yb - 2.5, zb), (CX + xe, yb, zb), (CX + xe, ya, za)], STONE2)
    for k in range(12):  # cippi with the names of the battles
        z = z0 - 8 - k * 9.5
        for sx in (-1, 1):
            y = float(H(CX + sx * 5.2, z))
            m.box(CX + sx * 5.2, y + 1.0, z, 0.8, 3.0, 0.8, STONE)
            m.box(CX + sx * 5.2, y + 2.6, z, 1.0, 0.25, 1.0, STONE2)
    # Portale di Roma: block with a great arch, terrace on top
    pz = z1 - 6.0; py = float(H(CX, pz))
    m.box(CX, py + 5.5, pz, 26.0, 15.0, 10.0, STONE, top=PAVE)
    m.face([(CX - 3.5, py + 0.4, pz + 5.03), (CX + 3.5, py + 0.4, pz + 5.03), (CX + 3.5, py + 9.0, pz + 5.03), (CX - 3.5, py + 9.0, pz + 5.03)], DARK)
    for sx in (-1, 1):
        for k in range(3):
            x = CX + sx * (6.5 + k * 2.6)
            m.face([(x - 0.6, py + 6.0, pz + 5.03), (x + 0.6, py + 6.0, pz + 5.03), (x + 0.6, py + 9.5, pz + 5.03), (x - 0.6, py + 9.5, pz + 5.03)], NICHE)
    m.box(CX, py + 13.6, pz, 27.0, 1.2, 11.0, STONE2)


def build():
    c = bpy.data.collections.get('Sacrario')
    if c is None:
        c = bpy.data.collections.new('Sacrario'); bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    m = Mesh()
    ytop = tiers(m)
    chapel(m, ytop)
    via_eroica(m)
    o = m.finish('sacrario', c)
    mat = bpy.data.materials.get('M_Sacrario') or bpy.data.materials.new('M_Sacrario')
    mat.use_nodes = True
    nt = mat.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    va = next((n for n in nt.nodes if n.type == 'VERTEX_COLOR'), None) or nt.nodes.new('ShaderNodeVertexColor')
    va.layer_name = 'Col'; nt.links.new(va.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = 0.9
    o.data.materials.clear(); o.data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    path = os.path.join(ROOT, 'hd', 'models', 'sacrario.glb')
    with contextlib.redirect_stdout(io.StringIO()):
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_colors=True,
                                  export_normals=True, export_texcoords=False, export_materials='EXPORT',
                                  export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                                  export_cameras=False, export_lights=False)
    o.data.calc_loop_triangles()
    return dict(tris=len(o.data.loop_triangles), bytes=os.path.getsize(path), y0=round(Y0, 2), ytop=round(ytop, 2))
