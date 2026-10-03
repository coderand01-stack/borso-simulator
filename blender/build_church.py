"""Sant'Eulalia church from assets/church.glb -> hd/models/church_se.glb.

Placement matches seChurch() in tools/make_hd.py (colliders): the model's portal already faces -Y
(= game +Z, towards the piazza); scaled x2.4, nave centred on game x=170, porch front at game z=-29.5.
"""
import bpy, os, math
from mathutils import Matrix, Vector

ROOT = r"C:\Coding\borso-simulator"
S = 2.4
Z0 = -40.25  # game z of the model origin after scaling (porch my=-4.48 -> z=-29.5)


def build(Hfun):
    c = bpy.data.collections.get("SE_Church")
    if c is None:
        c = bpy.data.collections.new("SE_Church"); bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "assets", "church.glb"))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    base = float(Hfun(170, -42)) - 0.3
    T = Matrix.Translation(Vector((170, -Z0, base))) @ Matrix.Scale(S, 4)
    meshes = []
    for o in new:
        if o.type == 'MESH' and 'ground' not in o.name:
            me = o.data.copy(); me.transform(T @ o.matrix_world)
            n = bpy.data.objects.new("se_" + o.name[:40], me); c.objects.link(n); meshes.append(n)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    # join into one object per material count is small; keep separate meshes but parent to a root
    root = bpy.data.objects.new("church_se", None); c.objects.link(root)
    for m in meshes:
        m.parent = root
    return root, meshes


def export(root, meshes):
    path = os.path.join(ROOT, "hd", "models", "church_se.glb")
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for m in meshes:
        m.select_set(True)
    for m in meshes:
        for sl in m.material_slots:
            if sl.material and sl.material.use_nodes:
                for n in sl.material.node_tree.nodes:
                    if n.type == 'TEX_IMAGE' and n.image and max(n.image.size) > 1024:
                        n.image.scale(1024, 1024)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_image_format='AUTO',
                              export_yup=True, export_cameras=False, export_lights=False,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7)
    return path, os.path.getsize(path)
