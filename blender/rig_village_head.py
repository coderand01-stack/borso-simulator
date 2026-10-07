"""Scheletro umanoide per assets/village_head.glb (modello statico in posa ad A) -> FBX per Unity.

Ossa con i nomi Mixamo (Unity le riconosce da sole come Humanoid); pesi automatici; poi le braccia
vengono alzate in posa a T e quella diventa la posa di riposo (Unity vuole la T).
Uso: exec(open(r"C:\\Coding\\borso-simulator\\blender\\rig_village_head.py").read()); build()
"""
import bpy, math, os
from mathutils import Vector

SRC = r"C:\Coding\borso-simulator\assets\village_head.glb"
OUT = r"C:\Unity\borso-simulator\borso-simulator\Assets\Borso\Characters\Npc\Src\village_head.fbx"
HEIGHT = 1.72

# giunture misurate sulla vista frontale (unità del modello: altezza 66.7, x a sinistra del personaggio = +x)
J = {
    'Hips': (0, 36.6), 'Spine': (0, 40.5), 'Spine1': (0, 45), 'Spine2': (0, 49.5), 'Neck': (0, 55.5), 'Head': (0, 58.5), 'HeadTop_End': (0, 67),
    'Shoulder': (2.2, 53.5), 'Arm': (7.6, 53.0), 'ForeArm': (14.8, 42.1), 'Hand': (18.1, 33.9), 'HandEnd': (19.4, 29.5),
    'UpLeg': (3.6, 35.0), 'Leg': (3.9, 17.0), 'Foot': (5.0, 4.6), 'ToeBase': (5.2, 1.0), 'Toe_End': (5.2, 0.5),
}


def build():
    sc = bpy.data.scenes.get('Chars') or bpy.data.scenes.new('Chars')
    bpy.context.window.scene = sc
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    mesh = next(o for o in sc.objects if o.type == 'MESH')
    # gerarchia vuota del glb: si tiene solo la mesh con le trasformazioni applicate
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in [o for o in sc.objects if o is not mesh]:
        bpy.data.objects.remove(o, do_unlink=True)
    mesh.name = 'VillageHead'
    # profondità del corpo: y medio della mesh
    ys = [v.co.y for v in mesh.data.vertices]
    yc = (min(ys) + max(ys)) / 2

    arm = bpy.data.armatures.new('Armature')
    rig = bpy.data.objects.new('Armature', arm)
    sc.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones

    def P(name, side=1):
        x, z = J[name]
        return Vector((x * side, yc, z))

    def bone(name, head, tail, parent=None):
        b = eb.new(name); b.head = head; b.tail = tail
        if parent: b.parent = eb[parent]; b.use_connect = False
        return b

    bone('Hips', P('Hips'), P('Spine'))
    bone('Spine', P('Spine'), P('Spine1'), 'Hips')
    bone('Spine1', P('Spine1'), P('Spine2'), 'Spine')
    bone('Spine2', P('Spine2'), P('Neck'), 'Spine1')
    bone('Neck', P('Neck'), P('Head'), 'Spine2')
    bone('Head', P('Head'), P('HeadTop_End'), 'Neck')
    for side, s in (('Left', 1), ('Right', -1)):
        bone(f'{side}Shoulder', P('Shoulder', s), P('Arm', s), 'Spine2')
        bone(f'{side}Arm', P('Arm', s), P('ForeArm', s), f'{side}Shoulder')
        bone(f'{side}ForeArm', P('ForeArm', s), P('Hand', s), f'{side}Arm')
        bone(f'{side}Hand', P('Hand', s), P('HandEnd', s), f'{side}ForeArm')
        bone(f'{side}UpLeg', P('UpLeg', s), P('Leg', s), 'Hips')
        bone(f'{side}Leg', P('Leg', s), P('Foot', s), f'{side}UpLeg')
        foot = bone(f'{side}Foot', P('Foot', s), P('ToeBase', s) + Vector((0, -4.0, 0)), f'{side}Leg')
        bone(f'{side}ToeBase', foot.tail, foot.tail + Vector((0, -2.5, 0)), f'{side}Foot')
    bpy.ops.object.mode_set(mode='OBJECT')

    # pesi automatici
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    # posa a T: braccia orizzontali, poi diventa la posa di riposo
    bpy.ops.object.mode_set(mode='POSE')
    for side, s in (('Left', 1), ('Right', -1)):
        pb = rig.pose.bones[f'{side}Arm']
        a = P('Arm', s); h = P('Hand', s)
        ang = math.atan2(a.z - h.z, abs(h.x - a.x))          # quanto scende il braccio
        pb.rotation_mode = 'XYZ'
        # rotazione attorno all'asse Y del mondo (avanti/dietro): alza il braccio fino all'orizzontale
        rig.pose.bones[f'{side}Arm'].matrix = rig.pose.bones[f'{side}Arm'].matrix  # assicura l'aggiornamento
        from mathutils import Matrix
        R = Matrix.Rotation(-ang * s, 4, "Y")
        M = pb.matrix.copy()
        loc = M.to_translation()
        pb.matrix = Matrix.Translation(loc) @ R @ Matrix.Translation(-loc) @ M
        bpy.context.view_layer.update()
        # l'avambraccio segue già il braccio; si raddrizza rispetto al braccio
        pf = rig.pose.bones[f'{side}ForeArm']
        f = pf.matrix.copy(); fl = f.to_translation()
        d = (pf.tail - pf.head).normalized()
        ang2 = math.atan2(-d.z, abs(d.x))
        pf.matrix = Matrix.Translation(fl) @ Matrix.Rotation(-ang2 * s, 4, "Y") @ Matrix.Translation(-fl) @ f
        bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='OBJECT')
    # la deformazione diventa definitiva e la posa attuale quella di riposo
    bpy.context.view_layer.objects.active = mesh
    mod = next(m for m in mesh.modifiers if m.type == 'ARMATURE')
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    m2 = mesh.modifiers.new('Armature', 'ARMATURE'); m2.object = rig

    # scala reale
    k = HEIGHT / 66.7
    rig.scale = (k, k, k)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True); mesh.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'ARMATURE', 'MESH'},
                             add_leaf_bones=False, path_mode='COPY', embed_textures=True,
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_anim=False)
    return OUT
