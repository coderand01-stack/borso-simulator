"""Borso Simulator HD - sacred objects of Binea's quest (hd/models/items.glb).

Calice (assets/santo_graal.glb), Bibbia (assets/holy_bible.glb) and croce (assets/wooden_cross.glb) come from the
assets; the altar-boy bell and the thurible are modelled here. Each item is one object named item_<name>,
roughly real size (the game rescales it: big and floating in the world, small on the altar).
Run in Blender:  exec(open(r"C:\\Coding\\borso-simulator\\blender\\build_items.py").read()); build()
"""
import bpy, bmesh, math, io, contextlib
from mathutils import Matrix, Vector

exec(open(r"C:\Coding\borso-simulator\blender\common.py", encoding="utf-8").read())


def mat(name, color, rough=0.35, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = tuple(((color >> s) & 255) / 255 for s in (16, 8, 0)) and \
        tuple((((color >> s) & 255) / 255) ** 2.2 for s in (16, 8, 0)) + (1,)
    bs.inputs['Roughness'].default_value = rough; bs.inputs['Metallic'].default_value = metal
    return m


def lathe(name, prof, m, seg=20, c=None):
    """Surface of revolution around game Y. prof = [(radius, y)], radius 0 closes the end."""
    bm = bmesh.new(); rings = []
    for r, y in prof:
        if r < 1e-5:
            rings.append([bm.verts.new((0, 0, y))])  # blender (x, -z, y): axis = blender Z
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), y)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(seg): bm.faces.new((a[0], b[i], b[(i + 1) % seg]))
        elif len(b) == 1:
            for i in range(seg): bm.faces.new((a[i], b[0], a[(i + 1) % seg]))
        else:
            for i in range(seg): bm.faces.new((a[i], b[i], b[(i + 1) % seg], a[(i + 1) % seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def seg_box(name, a, b, t, m, c):
    """Thin box from a to b (game coords), section t x t (a chain of the thurible)."""
    a = Vector((a[0], -a[2], a[1])); b = Vector((b[0], -b[2], b[1]))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    d = b - a; L = d.length
    rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot @ Matrix.Diagonal((t, t, L, 1)), verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def bell(c):
    bronze = mat('Metal_Bronze', 0xc79a3a, 0.3, 1.0); wood = mat('Wood_Handle', 0x6a4022, 0.6); dark = mat('Bell_Inside', 0x3a2a14, 0.8)
    parts = [lathe('bell', [(0.074, 0.0), (0.079, 0.006), (0.072, 0.018), (0.061, 0.045), (0.052, 0.08), (0.047, 0.104), (0.036, 0.118), (0.0, 0.123)], bronze, 24, c),
             lathe('bell_in', [(0.0, 0.004), (0.072, 0.004)], dark, 24, c),
             lathe('bell_clap', [(0.0, -0.012), (0.014, -0.006), (0.012, 0.01), (0.0, 0.02)], bronze, 10, c),
             lathe('bell_collar', [(0.0, 0.118), (0.024, 0.118), (0.026, 0.132), (0.0, 0.134)], bronze, 16, c),
             lathe('bell_handle', [(0.0, 0.13), (0.015, 0.13), (0.017, 0.19), (0.026, 0.215), (0.021, 0.238), (0.0, 0.246)], wood, 14, c)]
    return parts


def thurible(c):
    silver = mat('Metal_Silver', 0xd6d2c8, 0.25, 1.0); gold = mat('Metal_Gold', 0xe0b84a, 0.3, 1.0); ember = mat('Ember', 0x3a1a10, 0.9)
    p = [lathe('tur_bowl', [(0.0, 0.0), (0.032, 0.0), (0.036, 0.016), (0.024, 0.032), (0.058, 0.048), (0.074, 0.085), (0.076, 0.108), (0.0, 0.108)], silver, 20, c),
         lathe('tur_rim', [(0.074, 0.104), (0.082, 0.106), (0.082, 0.116), (0.074, 0.118)], gold, 20, c),
         lathe('tur_lid', [(0.077, 0.116), (0.072, 0.15), (0.054, 0.19), (0.034, 0.222), (0.022, 0.25), (0.028, 0.262), (0.0, 0.272)], silver, 20, c),
         lathe('tur_band', [(0.068, 0.155), (0.074, 0.158), (0.07, 0.17), (0.064, 0.168)], gold, 20, c),
         lathe('tur_top', [(0.0, 0.70), (0.036, 0.70), (0.036, 0.712), (0.0, 0.716)], gold, 16, c),
         lathe('tur_ring', [(0.0, 0.716), (0.008, 0.716), (0.008, 0.77), (0.0, 0.77)], gold, 8, c)]
    hook = lathe('tur_hook', [(0.0, 0.77), (0.022, 0.775), (0.022, 0.79), (0.0, 0.795)], gold, 12, c)
    p.append(hook)
    for k in range(3):
        a = 2 * math.pi * k / 3
        p.append(seg_box(f'tur_chain{k}', (math.cos(a) * 0.078, 0.112, math.sin(a) * 0.078), (math.cos(a) * 0.03, 0.70, math.sin(a) * 0.03), 0.006, silver, c))
    p.append(seg_box('tur_chainc', (0, 0.272, 0), (0, 0.70, 0), 0.005, silver, c))  # chain that lifts the lid
    p.append(lathe('tur_smoke', [(0.0, 0.258), (0.012, 0.26), (0.0, 0.27)], ember, 8, c))
    return p


def from_asset(fname, prefix, budget, c, metal=False):
    objs = add_asset_simple(fname, c, prefix)
    weld_dec(objs, budget)
    if metal:
        for o in objs:
            for s in o.material_slots:
                if s.material and not s.material.name.startswith('Metal'):
                    s.material.name = 'Metal_' + s.material.name
    for o in objs:
        o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return objs


def add_asset_simple(fname, c, prefix):
    with contextlib.redirect_stdout(io.StringIO()):
        src = import_glb(fname, c)
    return bake_world(src, c, lambda o: True, prefix)


def weld_dec(objs, budget):
    import numpy as np
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0004); bm.to_mesh(o.data); bm.free()
    ar = {}
    for o in objs:
        a = np.zeros(len(o.data.polygons)); o.data.polygons.foreach_get('area', a); ar[o.name] = a.sum()
    tot = sum(ar.values()) or 1
    for o in objs:
        decimate(o, max(40, int(budget * ar[o.name] / tot)))


def normalize(objs, size, flat=False):
    """Bottom-centre at the origin, longest side = size (metres)."""
    mn, mx = bbox(objs)
    s = size / max(mx - mn)
    M = Matrix.Scale(s, 4) @ Matrix.Translation(-Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2])))
    for o in objs:
        o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4); o.data.transform(M)


def build():
    c = coll('Items')
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    groups = {}
    groups['item_campanello'] = bell(c)
    groups['item_turibolo'] = thurible(c)
    g = from_asset('santo_graal.glb', 'graal_', 3000, c, metal=True); normalize(g, 0.24); groups['item_calice'] = g
    b = from_asset('holy_bible.glb', 'bible_', 1800, c); normalize(b, 0.26); groups['item_bibbia'] = b
    x = from_asset('wooden_cross.glb', 'cross_', 1500, c); normalize(x, 0.5)
    for o in x:
        o.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))  # bracci lungo x: di fronte sull'altare
    groups['item_croce'] = x
    for n, objs in groups.items():
        for o in objs:
            if o.name.startswith(('bell', 'tur_')):
                o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    slim_materials([o for objs in groups.values() for o in objs], 256)
    out = []
    for n, objs in groups.items():
        out.append(join(objs, n))
    with contextlib.redirect_stdout(io.StringIO()):
        root, size = export(out, 'items', 'items.glb')
    return {o.name: tris(o) for o in out}, size
