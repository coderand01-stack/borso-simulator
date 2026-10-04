"""Borso Simulator HD - vehicles from assets/ (Fiat Panda 4x4, David Brown 25D tractor).

Each model is oriented like the game's cars (front = game +Z = Blender -Y), scaled to metres,
put on the ground, decimated for mobile, and exported with separate wheel nodes named
"wheel_*" (pivot on the hub, axle on X) so the game can spin them with rotation.x.
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Matrix, Vector

ROOT = r"C:\Coding\borso-simulator"
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ROOT, "docs", "models")


def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def import_glb(path, c):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
    return new


def bake_world(objs, c):
    """Mesh copies with world transforms applied, no parents."""
    out = []
    for o in objs:
        if o.type != 'MESH':
            continue
        me = o.data.copy()
        me.transform(o.matrix_world)
        n = bpy.data.objects.new(o.name + "_w", me)
        c.objects.link(n)
        out.append(n)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return out


def transform_all(objs, M):
    for o in objs:
        o.data.transform(M)
        o.data.update()


def bbox(objs):
    pts = [v.co for o in objs for v in o.data.vertices]
    a = np.array([[p.x, p.y, p.z] for p in pts])
    return a.min(0), a.max(0)


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name; o.data.name = name
    return o


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def decimate(o, target):
    t = tris(o)
    if t <= target:
        return t
    m = o.modifiers.new("dec", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'; m.ratio = target / t; m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=m.name)
    return tris(o)


def pivot_to_center(o):
    mn, mx = bbox([o])
    c = Vector(((mn + mx) / 2).tolist())
    o.data.transform(Matrix.Translation(-c))
    o.location = c
    return c


def shrink_images(objs, size=512):
    seen = set()
    for o in objs:
        for s in o.material_slots:
            if not s.material or not s.material.use_nodes:
                continue
            for n in s.material.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.image.name not in seen:
                    seen.add(n.image.name)
                    if max(n.image.size) > size:
                        n.image.scale(size, size)
    return len(seen)


def export(objs, root_name, path):
    root = bpy.data.objects.new(root_name, None)
    objs[0].users_collection[0].objects.link(root)
    for o in objs:
        o.parent = root
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_image_format='JPEG',
                              export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7)
    return os.path.getsize(path)


def build_panda():
    c = coll("Veh_Panda")
    objs = bake_world(import_glb(os.path.join(ASSETS, "fiat_panda_4x4.glb"), c), c)
    mn, mx = bbox(objs)
    s = 3.45 / (mx[0] - mn[0])
    ctr = (mn + mx) / 2
    M = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-ctr[0], -ctr[1], -mn[2])))
    transform_all(objs, M)
    wheels = [o for o in objs if o.name.startswith('wheel')]
    body = join([o for o in objs if o not in wheels], 'panda_body')
    log = {'body': decimate(body, 9000)}
    for i, w in enumerate(sorted(wheels, key=lambda o: o.name)):
        w.name = f'wheel_{i}'
        log[w.name] = decimate(w, 420)
        pivot_to_center(w)
    # brighten the grey paint so the game can tint it with the car colour
    img = bpy.data.images['Image_3'] if 'Image_3' in bpy.data.images else None
    mat = bpy.data.materials.get('Top_chassis1')
    if mat:
        tex = next((n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links and n.outputs['Color'].links[0].to_socket.name == 'Base Color'), None)
        if tex is not None:
            px = np.array(tex.pixels[:]).reshape(-1, 4)
            g = np.median(px[:, :3].mean(1))
            px[:, :3] = np.clip(px[:, :3] / g * 0.93, 0, 1)
            tex.pixels.foreach_set(px.astype(np.float32).ravel())
            tex.update()
            log['paint_grey'] = round(float(g), 3)
        mat.name = 'Paint'
    log['images'] = shrink_images([body] + wheels)
    log['bytes'] = export([body] + wheels, 'panda', os.path.join(OUT, 'panda.glb'))
    return log


REAR = dict(y=0.81, z=0.59, r=0.56)
FRONT = dict(y=-0.94, z=0.41, r=0.38)


def build_tractor():
    c = coll("Veh_Tractor")
    src = import_glb(os.path.join(ASSETS, "david_brown_25d_tractor.glb"), c)
    root = next(o for o in src if o.parent is None)
    root.location = (0, 0, 0); root.scale = (0.14, 0.14, 0.14)
    bpy.context.view_layer.update()
    objs = bake_world(src, c)
    body = join(objs, 'tractor_body')
    mn, mx = bbox([body])
    xc = (mn[0] + mx[0]) / 2
    # split wheels: connected components whose centre sits on one of the 4 hubs
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    comp = [-1] * len(bm.verts); comps = []
    for v in bm.verts:
        if comp[v.index] >= 0:
            continue
        k = len(comps); stack = [v]; comp[v.index] = k; idx = []
        while stack:
            a = stack.pop(); idx.append(a.index)
            for e in a.link_edges:
                b = e.other_vert(a)
                if comp[b.index] < 0:
                    comp[b.index] = k; stack.append(b)
        comps.append(idx)
    co = np.array([v.co[:] for v in bm.verts])
    hubs = []
    for side in (-1, 1):
        for h in (REAR, FRONT):
            hubs.append((side, h))
    wheel_of = {}
    for k, idx in enumerate(comps):
        p = co[idx]; lo, hi = p.min(0), p.max(0); ce = (lo + hi) / 2; d = hi - lo
        for wi, (side, h) in enumerate(hubs):
            if (ce[0] - xc) * side <= 0.2:
                continue
            if math.hypot(ce[1] - h['y'], ce[2] - h['z']) < 0.12 and d[0] < 0.45 and max(d[1], d[2]) < 2.15 * h['r']:
                wheel_of[k] = wi
    groups = {}
    for f in bm.faces:
        k = comp[f.verts[0].index]
        if k in wheel_of:
            groups.setdefault(wheel_of[k], []).append(f.index)
    bm.free()
    wheels = []; done_ids = set()
    for wi, faces in sorted(groups.items()):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = body
        body.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        for fi in faces:
            body.data.polygons[fi].select = True
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        w = [o for o in bpy.context.selected_objects if o is not body][0]
        w.name = f'wheel_t{wi}'
        wheels.append(w); done_ids.add(wi)
        # face indices shift after each separation: recompute groups on the fly
        break
    # (re-run separation one wheel at a time because indices change)
    for _ in range(3):
        bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
        comp = [-1] * len(bm.verts); comps = []
        for v in bm.verts:
            if comp[v.index] >= 0:
                continue
            k = len(comps); stack = [v]; comp[v.index] = k; idx = []
            while stack:
                a = stack.pop(); idx.append(a.index)
                for e in a.link_edges:
                    b = e.other_vert(a)
                    if comp[b.index] < 0:
                        comp[b.index] = k; stack.append(b)
            comps.append(idx)
        co = np.array([v.co[:] for v in bm.verts])
        done = done_ids
        target = None; sel = []
        for k, idx in enumerate(comps):
            p = co[idx]; lo, hi = p.min(0), p.max(0); ce = (lo + hi) / 2; d = hi - lo
            for wi, (side, h) in enumerate(hubs):
                if wi in done or (ce[0] - xc) * side <= 0.2:
                    continue
                if math.hypot(ce[1] - h['y'], ce[2] - h['z']) < 0.12 and d[0] < 0.45 and max(d[1], d[2]) < 2.15 * h['r']:
                    if target is None:
                        target = wi
                    if wi == target:
                        sel.append(k)
        if target is None:
            bm.free(); break
        selv = set(i for k in sel for i in comps[k])
        bm.free()
        bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = body; body.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        for p in body.data.polygons:
            p.select = p.vertices[0] in selv
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        w = [o for o in bpy.context.selected_objects if o is not body][0]
        w.name = f'wheel_t{target}'
        wheels.append(w); done_ids.add(target)
    # orient/scale/ground: front already faces -Y; centre on X/Y, ground at Z=0
    allo = [body] + wheels
    mn, mx = bbox(allo)
    T = Matrix.Translation(Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2])))
    transform_all(allo, T)
    log = {'body': decimate(body, 26000)}
    for w in wheels:
        log[w.name] = decimate(w, 2600)
        pivot_to_center(w)
    log['images'] = shrink_images(allo)
    log['bytes'] = export(allo, 'trattore', os.path.join(OUT, 'trattore.glb'))
    return log
