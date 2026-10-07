"""Borso Simulator Unity - armi alleggerite dagli asset (assets/*.glb).

Ogni modello viene importato in una scena di lavoro, decimato al numero di triangoli voluto,
scalato alla lunghezza reale (asse più lungo) e centrato; esportato in glb per Unity.
Uso (Blender, Scripting): exec(open(r"C:\\Coding\\borso-simulator\\blender\\build_weapons.py").read()); build()
"""
import bpy, os
from mathutils import Vector

SRC = r"C:\Coding\borso-simulator\assets"
OUT = r"C:\Unity\borso-simulator\borso-simulator\Assets\Borso\Weapons\Opt"

# nome: (file, lunghezza reale in m, triangoli massimi)
# EXTRA: materiali da togliere e rotazione (gradi su Z di Blender) per avere la canna verso +Z in Unity
EXTRA = {'bazooka': {'drop': ('rocket_.',), 'rot_z': 180}}
WEAPONS = {
    'ciabatta': ('adidas_flip_flop.glb', 0.29, 6000),
    'deagle':   ('desert_eagle_gun.glb', 0.27, 9000),
    'bazooka':  ('bazooka_rocket_launcher.glb', 1.15, 20000),
    'm4':       ('m4a1_rifle.glb', 0.84, 22000),
    'fucile':   ('rifle.glb', 1.10, 9200),
}


def _work_scene():
    sc = bpy.data.scenes.get('Weapons') or bpy.data.scenes.new('Weapons')
    bpy.context.window.scene = sc
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return sc


def build_one(name, log):
    fn, length, max_tris = WEAPONS[name]
    sc = _work_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, fn))
    ex = EXTRA.get(name, {})
    for o in [o for o in sc.objects if o.type == 'MESH']:
        if any(m and m.name.startswith(d) for m in o.data.materials for d in ex.get('drop', ())):
            bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for o in sc.objects if o.type == 'MESH']
    # applica le trasformazioni della gerarchia e unisce in un'unica mesh (i materiali restano)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in [o for o in sc.objects if o.type != 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)
    ob.name = name
    if ex.get('rot_z'):
        import math
        ob.rotation_euler = (0, 0, math.radians(ex['rot_z']))
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if tris > max_tris:
        m = ob.modifiers.new('dec', 'DECIMATE')
        m.ratio = max_tris / tris
        m.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    tris2 = sum(len(p.vertices) - 2 for p in ob.data.polygons)

    # scala alla lunghezza reale e centra sull'origine
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    size = mx - mn
    k = length / max(size)
    ob.location = -(mn + mx) / 2 * k
    ob.scale = (k, k, k)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    size_after = size * k

    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name + '.glb'), use_selection=True, export_format='GLB',
                              export_draco_mesh_compression_enable=False, export_apply=True)
    log.append(f"{name}: {tris} -> {tris2} tri, size {tuple(round(v, 3) for v in size_after)}")


def build(names=None):
    log = []
    prev = bpy.context.window.scene
    for n in names or WEAPONS:
        build_one(n, log)
    bpy.context.window.scene = prev
    print('\n'.join(log))
    return log
