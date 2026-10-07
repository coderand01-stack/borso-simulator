"""Borso Simulator HD - interiors made from the assets (Semonzo church, Bar Sport).

Rooms are exported in the GAME room space of the interior (x right, y up, z towards the exit door;
the exit is at (0, d/2)), converted to Blender as (x, -z, y). Gameplay boxes/hotspots matching these
layouts live in tools/make_hd.py (buildChiesaHD / buildBarHD).
"""
import bpy, bmesh, math, os, io, contextlib, re
import numpy as np
from mathutils import Matrix, Vector

exec(open(r"C:\Coding\borso-simulator\blender\common.py", encoding="utf-8").read())


def base(n):
    return re.sub(r"\.\d{3}$", "", n)


def weld_decimate(objs, budget, weight=lambda o: 1.0, floor=60):
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008); bm.to_mesh(o.data); bm.free()
    ar = {}
    for o in objs:
        a = np.zeros(len(o.data.polygons)); o.data.polygons.foreach_get('area', a); ar[o.name] = a.sum() * weight(o)
    tot = sum(ar.values()) or 1
    for o in objs:
        decimate(o, max(floor, int(budget * ar[o.name] / tot)))


def game_matrix(gx, gy, gz, ry=0.0, s=1.0):
    """Blender matrix placing an object at game coords (Blender = (x, -z, y)), rotated ry around the vertical."""
    return Matrix.Translation(Vector((gx, -gz, gy))) @ Matrix.Rotation(ry, 4, 'Z') @ Matrix.Scale(s, 4)


def add_asset(fname, c, M, prefix, keep=lambda o: True, decim=None):
    with contextlib.redirect_stdout(io.StringIO()):
        src = import_glb(fname, c)
    objs = bake_world(src, c, keep, prefix)
    for o in objs:
        o.data.transform(M)
    if decim:
        weld_decimate(objs, decim)
    return objs


def instance_copies(objs, mats, c, prefix):
    out = []
    for k, M in enumerate(mats):
        for o in objs:
            me = o.data.copy(); me.transform(M)
            n = bpy.data.objects.new(f"{prefix}{k}_{o.name[:20]}", me); c.objects.link(n); out.append(n)
    return out


def box(c, name, gx, gy, gz, sx, sy, sz, color, mat_name=None, ry=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.transform(game_matrix(gx, gy, gz, ry) @ Matrix.Diagonal((sx, sz, sy, 1)))
    m = bpy.data.materials.get(mat_name or ('Col_%06x' % color))
    if m is None:
        m = bpy.data.materials.new(mat_name or ('Col_%06x' % color)); m.use_nodes = True
        bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        r, g, b = ((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255
        bs.inputs['Base Color'].default_value = (r ** 2.2, g ** 2.2, b ** 2.2, 1); bs.inputs['Roughness'].default_value = 0.8
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def cyl(c, name, gx, gy, gz, r, h, color, seg=12, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.transform(game_matrix(gx, gy, gz))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    m = box(c, name + '_tmp', 0, -50, 0, 0.01, 0.01, 0.01, color).active_material
    bpy.data.objects.remove(bpy.data.objects[name + '_tmp'], do_unlink=True)
    me.materials.append(m)
    return o


# ------------------------------------------------------------------ Semonzo church
CH = dict(xc=-5.1, floor=-15.13)  # source model: nave along +X (altar), floor at z=-15.13


def church_src_to_game():
    # source (x, y, z) -> game: gx = -y, gz = -(x - xc), gy = z - floor  => Blender (gx, -gz, gy) = (-y, x - xc, z - floor)
    return Matrix.Translation(Vector((0, -CH['xc'], -CH['floor']))) .__matmul__(Matrix.Identity(4)) if False else \
        Matrix(((0, -1, 0, 0), (1, 0, 0, -CH['xc']), (0, 0, 1, -CH['floor']), (0, 0, 0, 1)))


def build_church():
    c = coll('Room_chiesa')
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    M = church_src_to_game()
    drop = {'banc', 'chain'}  # pews replaced by church_bench.glb, hanging chains are 77k triangles of noise
    objs = add_asset('old_church_modeling_-_interior_scene.glb', c, M, 'ch_',
                     keep=lambda o: not ({base(s.material.name) for s in o.material_slots if s.material} & drop))
    weld_decimate(objs, 52000, floor=40)
    # altar top height (game y) from the altar mesh
    alt = [o for o in objs if any(base(s.material.name) == 'autel' for s in o.material_slots if s.material)]
    altar_top = float(bbox(alt)[1][2]) if alt else 1.2
    # pews: church_bench.glb (uniform scale -> 2.0 m long), 9 rows x 2 per side, facing the altar (-z)
    pew = add_asset('church_bench.glb', c, Matrix.Identity(4), 'pewsrc_', decim=None)
    mn, mx = bbox(pew)
    s = 2.0 / (mx[0] - mn[0])
    ctr = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]))
    norm = Matrix.Scale(s, 4) @ Matrix.Translation(-ctr)
    # the bench's seat faces source -Y (backrest at +Y): in game it must face the altar (-z = Blender +Y) -> rotate 180
    mats = []
    for row in range(9):
        gz = -3.2 + row * 1.15
        for gx in (3.85, 1.75, -1.75, -3.85):
            mats.append(game_matrix(gx, 0, gz, math.pi*180) @ norm)
    pews = instance_copies(pew, mats, c, 'pew')
    for o in pew:
        bpy.data.objects.remove(o, do_unlink=True)
    # wooden cross hanging above the altar
    cross = add_asset('wooden_cross.glb', c, Matrix.Identity(4), 'crosssrc_')
    mn, mx = bbox(cross); h = mx[2] - mn[2]
    for o in cross:
        o.data.transform(game_matrix(0, altar_top + 2.6, -12.6, math.pi / 2, 2.4 / h) @ Matrix.Translation(-Vector(((mn + mx) / 2).tolist())))
    # calice (Graal) e Bibbia non stanno sull'altare: sono oggetti della quest di Binea (models/items.glb)
    # confessional (right aisle) and candle stand (left aisle)
    extra = []
    wd = 0x4a2c1a
    extra += [box(c, 'conf_body', 9.0, 1.25, -2.0, 2.2, 2.5, 1.3, wd, 'Wood_dark'), box(c, 'conf_top', 9.0, 2.6, -2.0, 2.4, 0.2, 1.5, 0x3a2414, 'Wood_darker'),
              box(c, 'conf_curtain', 9.0, 1.15, -1.33, 0.8, 1.9, 0.04, 0x6a1a2a, 'Curtain'), box(c, 'conf_cross', 9.0, 2.9, -2.0, 0.08, 0.5, 0.08, 0xd8c08a, 'Brass'),
              box(c, 'conf_crossb', 9.0, 2.95, -2.0, 0.3, 0.07, 0.08, 0xd8c08a, 'Brass')]
    extra += [box(c, 'lum_stand', -9.0, 0.45, -6.0, 1.4, 0.9, 0.6, 0x3a3a3a, 'Iron'), box(c, 'lum_top', -9.0, 0.93, -6.0, 1.5, 0.06, 0.7, 0x2a2a2a, 'Iron_dark')]
    for i in range(10):
        x = -9.55 + (i % 5) * 0.27; z = -6.15 + (i // 5) * 0.3
        extra.append(cyl(c, f'lum_{i}', x, 1.02, z, 0.045, 0.12, 0xf4efe0, 8))
    for o in objs + pews + cross:
        o.data.polygons.foreach_set('use_smooth', [False] * len(o.data.polygons))
    allo = objs + pews + cross + extra
    slim_materials(allo, 512, big={'mur-bas': 1024, 'mur-haut': 1024, 'colonne': 1024, 'arche': 1024})
    with contextlib.redirect_stdout(io.StringIO()):
        root, size = export(allo, 'room_chiesa', 'room_chiesa.glb')
    return dict(objs=len(allo), tris=sum(tris(o) for o in allo), bytes=size, altar_top=round(altar_top, 3))


# ------------------------------------------------------------------ Bar Sport
BAR = dict(door_x=-1.3, floor=4.36)  # source: floor z=4.36, front wall (door) at y=-5.42


def build_bar():
    c = coll('Room_bar')
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    # source (x, y, z) -> game: gx = x - door_x, gz = -y, gy = z - floor  => Blender (gx, -gz, gy) = (x - door_x, y, z - floor)
    M = Matrix.Translation(Vector((-BAR['door_x'], 0, -BAR['floor'])))
    objs = add_asset('old_bar.glb', c, M, 'bar_')  # 41k triangles: kept intact (decimation breaks its UVs)
    # biliardino (foosball table) for the Binea quest, built here
    ex = []
    fx, fz = 9.3, 1.3
    ex.append(box(c, 'foos_body', fx, 0.62, fz, 1.35, 0.35, 0.8, 0x2a5a2a, 'Foos_green'))
    ex.append(box(c, 'foos_field', fx, 0.80, fz, 1.2, 0.02, 0.68, 0x3a8a3a, 'Foos_field'))
    for sx in (-1, 1):
        for sz in (-1, 1):
            ex.append(box(c, f'foos_leg{sx}{sz}', fx + sx * 0.58, 0.23, fz + sz * 0.33, 0.08, 0.46, 0.08, 0x1a1a1a, 'Iron_dark'))
    for i in range(8):
        x = fx - 0.52 + i * 0.149
        ex.append(box(c, f'foos_rod{i}', x, 0.86, fz, 0.025, 0.025, 1.25, 0xc8c8c8, 'Chrome'))
        ex.append(box(c, f'foos_handle{i}', x, 0.86, fz + (0.66 if i % 2 else -0.66), 0.05, 0.05, 0.14, 0x111111, 'Black'))
        for k in range(1 + (i % 3)):
            ex.append(box(c, f'foos_man{i}_{k}', x, 0.86, fz - 0.2 + k * 0.2, 0.05, 0.14, 0.04, 0xc8302a if i % 2 else 0x2a4a9a))
    ex.append(box(c, 'door_frame_l', -0.75, 1.3, 5.38, 0.1, 2.6, 0.12, 0x3a2414, 'Wood_darker'))
    ex.append(box(c, 'door_frame_r', 0.75, 1.3, 5.38, 0.1, 2.6, 0.12, 0x3a2414, 'Wood_darker'))
    ex.append(box(c, 'door_frame_t', 0, 2.62, 5.38, 1.6, 0.12, 0.12, 0x3a2414, 'Wood_darker'))
    allo = objs + ex
    slim_materials(ex, 512)  # the bar's own materials are exported as imported (small textures, 2 UV sets)
    with contextlib.redirect_stdout(io.StringIO()):
        root, size = export(allo, 'room_bar', 'room_bar.glb')
    mn, mx = bbox(objs)
    return dict(objs=len(allo), tris=sum(tris(o) for o in allo), bytes=size, game_x=(round(mn[0], 2), round(mx[0], 2)), game_z=(round(-mx[1], 2), round(-mn[1], 2)))
