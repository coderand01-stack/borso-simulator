"""Esporta la mappa per il progetto Unity: come export_glb() di build_world.py ma con le tangenti
(servono alle normal map) e senza Draco. La versione web (docs/models/world.glb) non cambia.
Uso: aprire blender/borso_world.blend, poi exec(open(r"C:\\Coding\\borso-simulator\\blender\\export_unity.py").read())
"""
import bpy, os

UNITY = r"C:\Unity\borso-simulator\borso-simulator\Assets\Borso\Models\world.glb"


def export_world_unity(path=UNITY):
    coll = bpy.data.collections.get('BorsoWorld')
    # le tangenti si calcolano solo su triangoli: triangolazione temporanea applicata all'export
    mods = []
    for o in coll.objects:
        if o.type == 'MESH':
            m = o.modifiers.new('tri_unity', 'TRIANGULATE')
            m.keep_custom_normals = True
            mods.append((o, m))
    bpy.ops.object.select_all(action='DESELECT')
    for o in coll.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = coll.objects[0]
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    fmts = [i.identifier for i in props['export_image_format'].enum_items]
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_colors=True,
                              export_normals=True, export_tangents=True, export_texcoords=True,
                              export_materials='EXPORT', export_yup=True, export_apply=True,
                              export_cameras=False, export_lights=False, export_extras=False,
                              export_image_format='NONE' if 'NONE' in fmts else 'JPEG',
                              export_draco_mesh_compression_enable=False)
    for o, m in mods:
        o.modifiers.remove(m)
    return path, os.path.getsize(path)
