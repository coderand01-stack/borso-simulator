"""Borso Simulator HD - character part library (docs/models/chars.glb).

Same blocky style and the same rig as the game's makeChar() (groups body/head/legL/legR/armL/armR,
pivots and sizes unchanged), but every part is modelled with bevels and details.
Each part is exported as its own mesh, modelled in the local space of the group it belongs to.
Colours are NOT baked: TEXCOORD_0.x = colour slot index + 0.5, TEXCOORD_0.y = shading factor; the game
resolves the slot with the character preset (shirt, pants, skin...) and merges the parts per group.
"""
import bpy, bmesh, math, os, io, contextlib
from mathutils import Vector, Matrix

ROOT = r"C:\Coding\borso-simulator"
SLOTS = ['skin', 'shirt', 'sleeve', 'pants', 'shoes', 'hair', 'hat', 'vest', 'white', 'dark', 'skirt', 'gold', 'bag', 'sack',
         'apron', 'glasses', 'sole', 'mouth', 'balaclava', 'belt', 'iris']
S = {n: i for i, n in enumerate(SLOTS)}


class Part:
    def __init__(self, name):
        self.name = name; self.bm = bmesh.new(); self.uv = self.bm.loops.layers.uv.new('UVMap')

    def box(self, c, size, slot, bevel=0.0, shade=(0.82, 1.0), seg=1, taper=None, rot=None, cuts=()):
        """Bevelled box in GAME coords (x right, y up, z front). shade = (bottom, top) multiplier.
        cuts = heights (game y) of extra edge loops, so the part can bend there when skinned (knee, elbow, waist)."""
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            x, y, z = v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]  # cube local: treat its y as game y
            if taper and y > 0:
                x *= taper[0]; z *= taper[1]
            v.co = Vector((x, y, z))
        if bevel > 0:
            bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=min(bevel, min(size) * 0.45), segments=seg, affect='EDGES', profile=0.5)
        if rot is not None:
            bmesh.ops.transform(tmp, matrix=rot, verts=tmp.verts)
        bmesh.ops.translate(tmp, verts=tmp.verts, vec=Vector(c))
        for y in cuts:
            if c[1] - size[1] / 2 < y < c[1] + size[1] / 2:
                bmesh.ops.bisect_plane(tmp, geom=list(tmp.verts) + list(tmp.edges) + list(tmp.faces), plane_co=(0, y, 0), plane_no=(0, 1, 0))
        self._merge(tmp, slot, shade, c, size)

    def poly(self, pts, slot, shade=1.0):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        for l in f.loops:
            l[self.uv].uv = (S[slot] + 0.5, shade)

    def _merge(self, tmp, slot, shade, c, size):
        ymin = c[1] - size[1] / 2; h = max(size[1], 1e-4)
        vmap = {}
        for v in tmp.verts:
            vmap[v] = self.bm.verts.new(v.co)
        for f in tmp.faces:
            nf = self.bm.faces.new([vmap[v] for v in f.verts])
            for l in nf.loops:
                t = min(1, max(0, (l.vert.co.y - ymin) / h))
                k = shade[0] + (shade[1] - shade[0]) * t
                if f.normal.y < -0.5:
                    k *= 0.75
                l[self.uv].uv = (S[slot] + 0.5, k)
        tmp.free()

    def to_object(self, coll):
        me = bpy.data.meshes.new(self.name)
        # game (x, y, z) -> blender (x, -z, y)
        for v in self.bm.verts:
            v.co = Vector((v.co.x, -v.co.z, v.co.y))
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me); self.bm.free()
        ob = bpy.data.objects.new(self.name, me); coll.objects.link(ob)
        return ob


def RY(a):
    return Matrix.Rotation(a, 4, 'Y')


def RZ(a):
    return Matrix.Rotation(a, 4, 'Z')


def RX(a):
    return Matrix.Rotation(a, 4, 'X')


KNEE = (-0.30, -0.36, -0.40, -0.44, -0.48, -0.52, -0.58)     # leg space (hip pivot), knee at -0.44
ELBOW = (-0.17, -0.22, -0.26, -0.29, -0.32, -0.36, -0.41)    # arm space (shoulder pivot), elbow at -0.29
WAIST = (1.0, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40)            # body space, spine joint at 1.08


def parts():
    P = []

    def new(n):
        p = Part(n); P.append(p); return p

    # ---------------- legs (group pivot = hip joint, leg hangs along -y)
    for side, sx in (('L', -1), ('R', 1)):
        p = new('leg_' + side)
        p.box((0, -0.40, 0), (0.21, 0.80, 0.23), 'pants', bevel=0.035, shade=(0.78, 1.0), cuts=KNEE)
        p.box((0, -0.62, 0.118), (0.17, 0.05, 0.012), 'pants', shade=(0.72, 0.72))  # knee crease
        p = new('shoe_' + side)
        p.box((0, -0.835, 0.04), (0.235, 0.10, 0.31), 'shoes', bevel=0.035, shade=(0.85, 1.05))
        p.box((0, -0.895, 0.045), (0.245, 0.03, 0.325), 'sole', bevel=0.01, shade=(0.9, 0.9))
        p.box((0, -0.80, 0.17), (0.16, 0.015, 0.06), 'white', shade=(0.9, 0.9))  # laces
        p = new('bigshoe_' + side)
        p.box((0, -0.82, 0.06), (0.26, 0.14, 0.40), 'shoes', bevel=0.05, shade=(0.88, 1.05))
        p.box((0, -0.89, 0.06), (0.27, 0.055, 0.42), 'sole', bevel=0.02, shade=(0.95, 0.95))
        p.box((sx * 0.131, -0.82, 0.02), (0.01, 0.05, 0.22), 'dark', shade=(1, 1))  # swoosh
        p = new('legstripe_' + side)
        p.box((sx * 0.107, -0.40, 0), (0.012, 0.80, 0.05), 'white', shade=(0.9, 1.0), cuts=KNEE)
        p = new('stocking_' + side)  # bare-ish legs under a skirt
        p.box((0, -0.40, 0), (0.19, 0.80, 0.21), 'pants', bevel=0.04, shade=(0.85, 1.0), cuts=KNEE)

    # ---------------- torso (group = body, feet at y=0)
    p = new('torso')
    p.box((0, 1.26, 0), (0.56, 0.66, 0.30), 'shirt', bevel=0.05, shade=(0.8, 1.0), cuts=WAIST)
    p.box((0, 0.965, 0), (0.565, 0.07, 0.305), 'belt', bevel=0.015, shade=(0.9, 0.9))
    p.box((0, 0.965, 0.155), (0.07, 0.05, 0.01), 'gold', shade=(1, 1))  # buckle
    p.box((-0.07, 1.565, 0.12), (0.12, 0.05, 0.06), 'shirt', bevel=0.012, shade=(1.05, 1.05), rot=RZ(0.35))  # collar
    p.box((0.07, 1.565, 0.12), (0.12, 0.05, 0.06), 'shirt', bevel=0.012, shade=(1.05, 1.05), rot=RZ(-0.35))
    for y in (1.43, 1.30, 1.17):
        p.box((0, y, 0.152), (0.025, 0.025, 0.01), 'white', shade=(0.9, 0.9))  # buttons
    p = new('torso_track')  # tracksuit top: zip, no collar
    p.box((0, 1.26, 0), (0.56, 0.66, 0.30), 'shirt', bevel=0.05, shade=(0.8, 1.0), cuts=WAIST)
    p.box((0, 0.955, 0), (0.57, 0.06, 0.31), 'shirt', bevel=0.015, shade=(0.7, 0.7))  # elastic hem
    p.box((0, 1.27, 0.152), (0.018, 0.60, 0.01), 'white', shade=(0.85, 0.85), cuts=WAIST)
    p.box((0, 1.575, 0.0), (0.30, 0.05, 0.24), 'shirt', bevel=0.02, shade=(0.9, 0.9))  # high collar
    p = new('torsostripes')
    for sx in (-1, 1):
        p.box((sx * 0.20, 1.26, 0.151), (0.035, 0.64, 0.01), 'white', shade=(0.95, 0.95), cuts=WAIST)
    p = new('neck')
    p.box((0, 1.60, 0), (0.15, 0.08, 0.14), 'skin', bevel=0.02, shade=(0.8, 0.85))
    p = new('vest')
    for sx in (-1, 1):
        p.box((sx * 0.16, 1.33, 0.15), (0.24, 0.50, 0.03), 'vest', bevel=0.012, shade=(0.85, 1.0), cuts=WAIST)
        p.box((sx * 0.287, 1.33, 0), (0.016, 0.50, 0.30), 'vest', shade=(0.85, 1.0), cuts=WAIST)
        p.box((sx * 0.10, 1.25, 0.168), (0.025, 0.025, 0.008), 'dark', shade=(1, 1))
    p.box((0, 1.33, -0.152), (0.58, 0.50, 0.012), 'vest', shade=(0.85, 1.0), cuts=WAIST)
    p = new('apron')
    p.box((0, 1.02, 0.163), (0.50, 0.74, 0.02), 'apron', bevel=0.008, shade=(0.88, 1.0), cuts=WAIST)
    p.box((0, 1.43, 0.157), (0.30, 0.08, 0.02), 'apron', shade=(0.95, 0.95))
    p.box((0, 1.0, 0.176), (0.20, 0.13, 0.01), 'apron', shade=(0.85, 0.85))  # pocket
    p = new('chain')
    for i in range(9):
        a = (i / 8 - 0.5) * 2.2
        p.box((math.sin(a) * 0.14, 1.52 - math.cos(a * 0.9) * 0.05 + 0.05, 0.158), (0.032, 0.022, 0.012), 'gold', shade=(1.1, 1.1))
    p = new('borsello')
    p.box((0.02, 1.30, 0.158), (0.045, 0.80, 0.012), 'dark', shade=(0.9, 0.9), rot=RZ(0.75))
    p.box((0.17, 1.03, 0.19), (0.26, 0.18, 0.09), 'bag', bevel=0.025, shade=(0.8, 1.0))
    p.box((0.17, 1.06, 0.237), (0.22, 0.02, 0.01), 'gold', shade=(1, 1))
    p = new('sack')
    p.box((0, 1.25, -0.33), (0.52, 0.58, 0.32), 'sack', bevel=0.08, seg=2, shade=(0.75, 1.0), taper=(0.75, 0.8), rot=RZ(0.15))
    p.box((0.02, 1.58, -0.30), (0.14, 0.10, 0.12), 'sack', bevel=0.03, shade=(0.8, 0.9))
    p = new('skirt')
    p.box((0, 0.80, 0), (0.56, 0.44, 0.36), 'skirt', bevel=0.03, shade=(0.75, 1.0), taper=(0.86, 0.86))

    # ---------------- head (group pivot y=1.6 in body)
    p = new('head')
    p.box((0, 0.22, 0), (0.34, 0.36, 0.34), 'skin', bevel=0.045, seg=2, shade=(0.88, 1.02))
    for sx in (-1, 1):
        p.box((sx * 0.175, 0.20, -0.01), (0.035, 0.09, 0.07), 'skin', bevel=0.012, shade=(0.85, 0.9))  # ears
        p.box((sx * 0.075, 0.245, 0.171), (0.075, 0.065, 0.008), 'white', shade=(1, 1))  # eye
        p.box((sx * 0.072, 0.243, 0.177), (0.038, 0.048, 0.006), 'iris', shade=(1, 1))
        p.box((sx * 0.072, 0.243, 0.181), (0.018, 0.024, 0.004), 'dark', shade=(1, 1))
        p.box((sx * 0.078, 0.302, 0.172), (0.09, 0.022, 0.012), 'hair', shade=(1, 1), rot=RZ(sx * -0.08))  # brows
    p.box((0, 0.185, 0.18), (0.055, 0.085, 0.05), 'skin', bevel=0.015, shade=(0.92, 1.0))  # nose
    p.box((0, 0.112, 0.171), (0.11, 0.022, 0.008), 'mouth', shade=(1, 1))
    # hair & hats (hat slot = preset hatColor, hair slot = preset hair)
    p = new('hair_short')
    p.box((0, 0.405, -0.01), (0.36, 0.07, 0.36), 'hair', bevel=0.03, shade=(0.9, 1.05))
    p.box((0, 0.30, -0.165), (0.36, 0.22, 0.045), 'hair', bevel=0.015, shade=(0.85, 1.0))
    for sx in (-1, 1):
        p.box((sx * 0.172, 0.33, 0.0), (0.02, 0.10, 0.20), 'hair', shade=(0.9, 1.0))
    p = new('hair_long')
    p.box((0, 0.41, -0.01), (0.37, 0.08, 0.37), 'hair', bevel=0.035, shade=(0.9, 1.05))
    p.box((0, 0.21, -0.17), (0.37, 0.44, 0.06), 'hair', bevel=0.02, shade=(0.8, 1.0))
    for sx in (-1, 1):
        p.box((sx * 0.178, 0.25, -0.03), (0.03, 0.34, 0.24), 'hair', bevel=0.01, shade=(0.8, 1.0))
    p.box((0, 0.38, 0.165), (0.30, 0.05, 0.03), 'hair', bevel=0.01, shade=(1, 1))  # fringe
    p = new('hair_tuft')
    p.box((0, 0.405, 0), (0.36, 0.06, 0.36), 'hair', bevel=0.025, shade=(0.9, 1.0))
    p.box((0, 0.47, 0.03), (0.16, 0.12, 0.30), 'hair', bevel=0.04, shade=(0.95, 1.1), taper=(0.7, 0.85))
    p.box((0, 0.31, -0.165), (0.34, 0.18, 0.03), 'hair', shade=(0.8, 0.9))
    p = new('hair_bald')  # grey fringe around the ears for the old men
    for sx in (-1, 1):
        p.box((sx * 0.171, 0.29, -0.06), (0.025, 0.08, 0.22), 'hair', shade=(0.9, 1.0))
    p.box((0, 0.29, -0.171), (0.34, 0.08, 0.025), 'hair', shade=(0.9, 1.0))
    p = new('hat_cap')
    p.box((0, 0.43, 0), (0.37, 0.11, 0.37), 'hat', bevel=0.05, seg=2, shade=(0.9, 1.05))
    p.box((0, 0.39, 0.25), (0.30, 0.025, 0.17), 'hat', bevel=0.01, shade=(0.8, 0.85), rot=RX(-0.12))
    p.box((0, 0.49, 0), (0.05, 0.02, 0.05), 'hat', shade=(1.1, 1.1))
    p = new('hat_capBack')
    p.box((0, 0.43, 0), (0.37, 0.11, 0.37), 'hat', bevel=0.05, seg=2, shade=(0.9, 1.05))
    p.box((0, 0.39, -0.25), (0.30, 0.025, 0.17), 'hat', bevel=0.01, shade=(0.8, 0.85), rot=RX(0.12))
    p.box((0, 0.45, 0.188), (0.12, 0.05, 0.01), 'white', shade=(1, 1))  # logo
    p = new('hat_coppola')  # flat cap
    p.box((0, 0.425, -0.01), (0.38, 0.07, 0.38), 'hat', bevel=0.03, shade=(0.88, 1.0), rot=RX(-0.10))
    p.box((0, 0.40, 0.22), (0.33, 0.03, 0.12), 'hat', bevel=0.012, shade=(0.8, 0.85), rot=RX(-0.18))
    p.box((0, 0.47, 0.04), (0.30, 0.03, 0.26), 'hat', bevel=0.012, shade=(1.0, 1.05), rot=RX(-0.16))
    p = new('hat_scarf')  # headscarf (fazzoletto) knotted under the chin
    p.box((0, 0.34, -0.01), (0.38, 0.22, 0.38), 'hat', bevel=0.05, seg=2, shade=(0.85, 1.0))
    p.box((0, 0.20, -0.172), (0.38, 0.26, 0.04), 'hat', bevel=0.012, shade=(0.8, 0.95))
    for sx in (-1, 1):
        p.box((sx * 0.182, 0.17, 0.02), (0.03, 0.22, 0.28), 'hat', bevel=0.01, shade=(0.8, 0.95))
    p.box((0, 0.03, 0.12), (0.10, 0.06, 0.06), 'hat', bevel=0.02, shade=(0.8, 0.9))
    p = new('hat_helmet')  # cycling helmet with vents
    p.box((0, 0.45, -0.01), (0.39, 0.15, 0.43), 'hat', bevel=0.06, seg=2, shade=(0.9, 1.1), taper=(0.85, 0.9))
    for x in (-0.09, 0.0, 0.09):
        p.box((x, 0.52, 0.0), (0.035, 0.02, 0.24), 'dark', shade=(1, 1))
    p.box((0, 0.38, 0.215), (0.30, 0.04, 0.02), 'dark', shade=(1, 1))
    p = new('hat_beanie')
    p.box((0, 0.42, 0), (0.37, 0.16, 0.37), 'hat', bevel=0.06, seg=2, shade=(0.85, 1.05))
    p.box((0, 0.35, 0), (0.385, 0.06, 0.385), 'hat', bevel=0.015, shade=(0.75, 0.8))
    p.box((0, 0.515, 0), (0.08, 0.05, 0.08), 'hat', bevel=0.025, shade=(1.0, 1.1))
    p = new('mustache')
    p.box((0, 0.145, 0.183), (0.19, 0.04, 0.025), 'hair', bevel=0.012, shade=(1, 1))
    p = new('beard')
    p.box((0, 0.09, 0.15), (0.32, 0.14, 0.08), 'hair', bevel=0.03, shade=(0.85, 1.0))
    for sx in (-1, 1):
        p.box((sx * 0.155, 0.17, 0.06), (0.04, 0.16, 0.16), 'hair', shade=(0.85, 1.0))
    p = new('glasses')
    for sx in (-1, 1):
        p.box((sx * 0.075, 0.245, 0.188), (0.10, 0.075, 0.012), 'glasses', shade=(1, 1))
        p.box((sx * 0.175, 0.255, 0.08), (0.012, 0.018, 0.2), 'glasses', shade=(1, 1))
    p.box((0, 0.255, 0.188), (0.06, 0.015, 0.01), 'glasses', shade=(1, 1))
    p = new('balaclava')  # passamontagna: covers the head except an eye band
    p.box((0, 0.22, 0), (0.355, 0.375, 0.355), 'balaclava', bevel=0.05, seg=2, shade=(0.85, 1.0))
    p.box((0, 0.25, 0.181), (0.29, 0.085, 0.006), 'skin', shade=(1, 1))
    for sx in (-1, 1):
        p.box((sx * 0.072, 0.25, 0.186), (0.06, 0.05, 0.004), 'white', shade=(1, 1))
        p.box((sx * 0.072, 0.25, 0.19), (0.028, 0.034, 0.004), 'dark', shade=(1, 1))
    p.box((0, 0.44, 0), (0.06, 0.04, 0.06), 'balaclava', bevel=0.02, shade=(1, 1))

    # ---------------- arms (group pivot = shoulder, hang along -y)
    for side, sx in (('L', -1), ('R', 1)):
        p = new('arm_' + side)
        p.box((0, -0.27, 0), (0.17, 0.54, 0.19), 'sleeve', bevel=0.035, shade=(0.8, 1.0), cuts=ELBOW)
        p.box((0, -0.545, 0), (0.175, 0.05, 0.195), 'sleeve', bevel=0.012, shade=(0.72, 0.75))  # cuff
        p.box((0, -0.035, 0), (0.18, 0.08, 0.20), 'sleeve', bevel=0.03, shade=(1.0, 1.05))  # shoulder cap
        p = new('hand_' + side)
        p.box((0, -0.635, 0.005), (0.14, 0.13, 0.15), 'skin', bevel=0.035, shade=(0.88, 1.0))
        p.box((-sx * 0.07, -0.625, 0.055), (0.04, 0.08, 0.05), 'skin', bevel=0.015, shade=(0.9, 0.95))  # thumb
        p = new('armstripe_' + side)
        p.box((sx * 0.087, -0.27, 0), (0.012, 0.54, 0.045), 'white', shade=(0.95, 1.0), cuts=ELBOW)
    return P


def build():
    c = bpy.data.collections.get('Chars')
    if c is None:
        c = bpy.data.collections.new('Chars'); bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mat = bpy.data.materials.get('M_Char') or bpy.data.materials.new('M_Char')
    objs = []
    for p in parts():
        ob = p.to_object(c)
        ob.data.materials.append(mat)
        objs.append(ob)
    return objs


def export(objs):
    path = os.path.join(ROOT, 'docs', 'models', 'chars.glb')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    with contextlib.redirect_stdout(io.StringIO()):
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_materials='NONE',
                                  export_yup=True, export_texcoords=True, export_normals=True, export_colors=False,
                                  export_cameras=False, export_lights=False)
    return path, os.path.getsize(path)


def preview_scene(objs, presets):
    """Assemble a few characters in Blender for a visual check (colours resolved like the game)."""
    import numpy as np
    c = bpy.data.collections.get('CharPreview')
    if c is None:
        c = bpy.data.collections.new('CharPreview'); bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    by = {o.name: o for o in objs}
    out = []
    for k, (pal, groups) in enumerate(presets):
        for gname, (names, off) in groups.items():
            for n in names:
                src = by.get(n)
                if not src:
                    continue
                me = src.data.copy()
                ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
                uv = me.uv_layers[0].data
                for i, l in enumerate(me.loops):
                    u, v = uv[i].uv
                    col = pal.get(SLOTS[int(u)], (1, 0, 1))
                    ca.data[i].color = (col[0] * v, col[1] * v, col[2] * v, 1)
                ob = bpy.data.objects.new(n + '_pv', me)
                ob.location = (k * 1.0 + off[0], -off[2], off[1]); c.objects.link(ob); out.append(ob)
    m = bpy.data.materials.get('M_CharPreview') or bpy.data.materials.new('M_CharPreview')
    m.use_nodes = True
    nt = m.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    va = next((n for n in nt.nodes if n.type == 'VERTEX_COLOR'), None) or nt.nodes.new('ShaderNodeVertexColor')
    va.layer_name = 'Col'; nt.links.new(va.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = 0.8
    for o in out:
        o.data.materials.clear(); o.data.materials.append(m)
    return out
