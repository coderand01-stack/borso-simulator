"""Borso Simulator HD - traffic cars from assets/ (Fiat Panda 4x4, Uno Turbo, 500, Multipla).

Every car ends up oriented like the game's cars (front = game +Z = Blender -Y), at real size,
grounded at z=0, decimated per part with an area-weighted triangle budget, smooth-shaded,
with 4 separate wheel nodes "wheel_*" (pivot on the hub, axle on X), a tintable "Paint"
material (white base colour, the game multiplies it by the car colour) and a "Glass" material.
"""
import bpy, bmesh, math, os, io, contextlib, re
import numpy as np
from mathutils import Matrix, Vector

exec(open(r"C:\Coding\borso-simulator\blender\common.py", encoding="utf-8").read())

CARS = {
    # key: file, front axis in the source ('-X' / '-Y'), target length (m), paint, glass, tyre materials
    'uno': dict(file='fiat_uno_turbo_i.e_mk2.glb', front='-X', length=3.69, width=1.66, paint=['Carrosserie'], glass=['Vitre'], tyre=['pNEU'],
                drop=['Ceinture1', 'Ceinture2', 'Moket', 'Compteur', 'Centre-V', 'Cuir_perf'], budget=16000, cap=500, cull=True),
    'cinquecento': dict(file='fiat_500_-_1970_model.glb', front='-Y', length=2.97, paint=['Body_Color'], glass=['Glass.001'], tyre=['Tires'],
                        drop=[], budget=11000),
    'multipla': dict(file='fiat_multipla_1998_3d_model.glb', front='-Y', length=3.99, paint=['Car_paint_fiat'], glass=['Car_Windows_All'],
                     tyre=['Car_rubber_wheel'], drop=['Car_brakedisk', 'Car_caliper'], budget=14000),
}


def base(n):
    return re.sub(r"\.\d{3}$", "", n)


def mesh_area(o):
    a = np.zeros(len(o.data.polygons)); o.data.polygons.foreach_get('area', a)
    return float(a.sum())


def smooth(objs, angle=40):
    for o in objs:
        o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
        o.data.use_auto_smooth = True; o.data.auto_smooth_angle = math.radians(angle)
        o.data.update()


def material_faces(o, names):
    idx = [i for i, s in enumerate(o.material_slots) if s.material and base(s.material.name) in names]
    if not idx:
        return np.zeros(len(o.data.polygons), bool)
    mi = np.zeros(len(o.data.polygons), np.int32); o.data.polygons.foreach_get('material_index', mi)
    return np.isin(mi, idx)


def find_hubs(objs, tyre_names):
    pts = []
    for o in objs:
        m = material_faces(o, tyre_names)
        if not m.any():
            continue
        c = np.zeros(len(o.data.polygons) * 3); o.data.polygons.foreach_get('center', c)
        pts.append(c.reshape(-1, 3)[m])
    P = np.concatenate(pts)
    P = P[P[:, 2] < 0.8]  # tyres touch the ground (rubber is sometimes reused for steering wheel/seals)
    xs = np.abs(P[:, 0]); P = P[xs > 0.45 * xs.max()]  # ignore a spare wheel near the middle
    yc = (P[:, 1].min() + P[:, 1].max()) / 2
    hubs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = P[(np.sign(P[:, 0]) == sx) & (np.sign(P[:, 1] - yc) == sy)]
            mn, mx = q.min(0), q.max(0)
            hubs.append(dict(c=(mn + mx) / 2, r=(mx[2] - mn[2]) / 2, w=mx[0] - mn[0]))
    return hubs


def split_wheels(body, hubs):
    """Separate the faces inside each wheel cylinder into wheel_i objects."""
    wheels = []
    for i, h in enumerate(hubs):
        n = len(body.data.polygons)
        c = np.zeros(n * 3); body.data.polygons.foreach_get('center', c); c = c.reshape(-1, 3)
        dx = np.abs(c[:, 0] - h['c'][0]); dyz = np.hypot(c[:, 1] - h['c'][1], c[:, 2] - h['c'][2])
        sel = (dx < h['w'] / 2 + 0.03) & (dyz < h['r'] * 1.03)
        if not sel.any():
            continue
        select([body])
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        body.data.polygons.foreach_set('select', sel)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        w = [o for o in bpy.context.selected_objects if o is not body][0]
        w.name = w.data.name = f'wheel_{i}'
        hc = Vector(h['c'].tolist())
        w.data.transform(Matrix.Translation(-hc)); w.location = hc
        wheels.append(w)
    return wheels


def fix_materials(objs, paint, glass):
    for o in objs:
        for s in o.material_slots:
            m = s.material
            if not m:
                continue
            bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if base(m.name) in paint or base(m.name) == 'Paint':
                m.name = 'Paint'
                if bs and not bs.inputs['Base Color'].is_linked:
                    bs.inputs['Base Color'].default_value = (0.85, 0.85, 0.85, 1)
            elif base(m.name) in glass or base(m.name) == 'Glass':
                m.name = 'Glass'
                if bs:
                    bs.inputs['Base Color'].default_value = (0.08, 0.1, 0.12, 1); bs.inputs['Alpha'].default_value = 0.55
                m.blend_method = 'BLEND'


DBG = []


def visibility_cull(objs, glass, samples=120, dirs=40, keep_ratio=0.03):
    """Delete parts that can't be seen from outside the car (glass counts as transparent)."""
    from mathutils.bvhtree import BVHTree
    V = []; Pp = []; owner = []; off = 0
    solid = [o for o in objs if not ({base(sl.material.name) for sl in o.material_slots if sl.material} <= set(glass))]
    for k, o in enumerate(solid):
        me = o.data
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
        V.append(co.reshape(-1, 3))
        for p in me.polygons:
            Pp.append([off + i for i in p.vertices]); owner.append(k)
        off += len(me.vertices)
    V = np.concatenate(V); owner = np.array(owner)
    bvh = BVHTree.FromPolygons(V.tolist(), Pp)
    mn, mx = V.min(0), V.max(0); ctr = (mn + mx) / 2; R_ = float(np.linalg.norm(mx - mn)) * 1.5
    rng = np.random.default_rng(1)
    D = rng.normal(size=(dirs, 3)); D[:, 2] = np.abs(D[:, 2]) * 0.8 + 0.05  # mostly from above/sides, never from below
    D /= np.linalg.norm(D, axis=1)[:, None]
    removed = []
    for k, o in enumerate(solid):
        n = len(o.data.polygons)
        c = np.zeros(n * 3); o.data.polygons.foreach_get('center', c); c = c.reshape(-1, 3)
        idx = rng.choice(n, min(samples, n), replace=False)
        seen = 0; tests = 0
        for i in idx:
            for d in D[rng.choice(dirs, 6, replace=False)]:
                org = c[i] + d * R_
                hit = bvh.ray_cast(Vector(org.tolist()), Vector((-d).tolist()), R_ * 2)
                tests += 1
                if hit[2] is not None and owner[hit[2]] == k:
                    seen += 1
        if seen / max(1, tests) < keep_ratio:
            removed.append(o.name[:30])
            objs.remove(o); bpy.data.objects.remove(o, do_unlink=True)
    return removed


def build_car(key, preview=True):
    cfg = CARS[key]; DBG.clear()
    c = coll('Car_' + key)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    with contextlib.redirect_stdout(io.StringIO()):
        src = import_glb(cfg['file'], c)
    objs = bake_world(src, c, prefix=key + '_')
    # drop unwanted parts (by dominant material) and empty meshes
    for o in list(objs):
        mats = {base(s.material.name) for s in o.material_slots if s.material}
        if not o.data.polygons or (mats and mats <= set(cfg['drop'])):
            objs.remove(o); bpy.data.objects.remove(o, do_unlink=True)
    # orient: front -> -Y, scale to length, centre, ground
    R = Matrix.Rotation(math.radians(90), 4, 'Z') if cfg['front'] == '-X' else Matrix.Identity(4)
    transform_all(objs, R)
    mn, mx = bbox(objs)
    s = cfg['width'] / (mx[0] - mn[0]) if 'width' in cfg else cfg['length'] / (mx[1] - mn[1])
    transform_all(objs, Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2]))))
    # area-weighted decimation per part
    def weight(o):  # paint holds the silhouette; hidden interior shells get little
        ms = {base(sl.material.name) for sl in o.material_slots if sl.material}
        if ms & set(cfg['paint']):
            return 3.0
        if any(k in m.lower() for m in ms for k in ('interior', 'tissu', 'cuir', 'seat', 'moket', 'plastic', 'noir')):
            return 0.35
        return 1.0
    areas = {o.name: mesh_area(o) * weight(o) for o in objs}
    tot = sum(areas.values()) or 1
    for o in objs:  # weld UV-seam duplicates first, otherwise the collapse leaves holes and spikes
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006)
        bm.to_mesh(o.data); bm.free()
    for o in objs:
        mats = {base(sl.material.name) for sl in o.material_slots if sl.material}
        t0 = tris(o)
        mnb, mxb = bbox([o]); cz = (mnb[2] + mxb[2]) / 2
        in_wheel = cz < 0.45 and abs((mnb[0] + mxb[0]) / 2) > 0.35 and (mxb[2] - mnb[2]) < 0.8
        floor = 900 if (mats & set(cfg['tyre']) or in_wheel) else max(40, min(cfg.get('cap', 900), int(0.025 * t0)))
        tg = max(floor, int(cfg['budget'] * areas[o.name] / tot))
        DBG.append((decimate(o, tg), tg, t0, o.name[:30]))
    culled = visibility_cull(objs, cfg['glass']) if cfg.get('cull') else []
    hubs = find_hubs(objs, cfg['tyre'])
    body = join(objs, key + '_body')
    wheels = split_wheels(body, hubs)
    smooth([body] + wheels, 32)
    fix_materials([body] + wheels, cfg['paint'], cfg['glass'])
    slim_materials([body] + wheels, 512)
    with contextlib.redirect_stdout(io.StringIO()):
        root, size = export([body] + wheels, key, key + '.glb')
    log = dict(culled=len(culled), body=tris(body), wheels=[tris(w) for w in wheels], hubs=[[round(v, 2) for v in h['c']] for h in hubs], bytes=size,
               dims=[round(v, 2) for v in (bbox([body])[1] - bbox([body])[0])])
    return log


def build_panda():
    """Panda 4x4: wheels are already separate objects; welded + area-weighted decimation, smooth shading."""
    c = coll('Car_panda')
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    with contextlib.redirect_stdout(io.StringIO()):
        src = import_glb('fiat_panda_4x4.glb', c)
    objs = bake_world(src, c, prefix='pd_')
    transform_all(objs, Matrix.Rotation(math.radians(90), 4, 'Z'))  # front -X -> -Y
    mn, mx = bbox(objs)
    s = 3.45 / (mx[1] - mn[1])
    transform_all(objs, Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2]))))
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006); bm.to_mesh(o.data); bm.free()
    wheels = sorted([o for o in objs if 'wheel' in o.name], key=lambda o: o.name)
    rest = [o for o in objs if o not in wheels]
    areas = {o.name: mesh_area(o) * (3.0 if 'Top_chassis' in o.name else 1.0) for o in rest}
    tot = sum(areas.values())
    for o in rest:
        decimate(o, max(300, int(16000 * areas[o.name] / tot)))
    body = join(rest, 'panda_body')
    for i, w in enumerate(wheels):
        decimate(w, 900); w.name = w.data.name = f'wheel_{i}'; pivot_to_center(w)
    smooth([body] + wheels, 32)
    mat = next((sl.material for sl in body.material_slots if sl.material and base(sl.material.name) == 'Top_chassis1'), None)
    if mat:
        bs = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        tex = bs.inputs['Base Color'].links[0].from_node.image if bs.inputs['Base Color'].is_linked else None
        if tex is not None:
            px = np.array(tex.pixels[:]).reshape(-1, 4)
            g = np.median(px[:, :3].mean(1))
            px[:, :3] = np.clip(px[:, :3] / g * 0.93, 0, 1)
            tex.pixels.foreach_set(px.astype(np.float32).ravel()); tex.update()
        mat.name = 'Paint'
    fix_materials([body] + wheels, ['Paint'], ['Glass'])
    slim_materials([body] + wheels, 512)
    with contextlib.redirect_stdout(io.StringIO()):
        root, size = export([body] + wheels, 'panda', 'panda.glb')
    return dict(body=tris(body), wheels=[tris(w) for w in wheels], bytes=size, dims=[round(v, 2) for v in (bbox([body])[1] - bbox([body])[0])])
