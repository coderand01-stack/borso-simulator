"""Shared helpers for asset preparation (Borso Simulator HD)."""
import bpy, os, math, re
import numpy as np
from mathutils import Matrix, Vector

ROOT = r"C:\Coding\borso-simulator"
ASSETS = os.path.join(ROOT, "assets")
MODELS = os.path.join(ROOT, "hd", "models")


def coll(name, clear=True):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    if clear:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    return c


def import_glb(fname, c):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ASSETS, fname))
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
    bpy.context.view_layer.update()
    return new


def bake_world(objs, c, keep=lambda o: True, prefix=""):
    """Mesh copies with world transforms applied; source hierarchy removed."""
    out = []
    for o in objs:
        if o.type == 'MESH' and keep(o):
            me = o.data.copy(); me.transform(o.matrix_world)
            n = bpy.data.objects.new(prefix + o.name[:50], me); c.objects.link(n); out.append(n)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return out


def bbox(objs):
    a = np.array([o.matrix_world @ v.co for o in objs for v in o.data.vertices])
    return a.min(0), a.max(0)


def transform_all(objs, M):
    for o in objs:
        o.data.transform(M); o.data.update()


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def select(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def join(objs, name):
    select(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name; o.data.name = name
    return o


def decimate(o, target, planar=False):
    t = tris(o)
    if t <= target:
        return t
    m = o.modifiers.new("dec", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'; m.ratio = max(0.002, target / t); m.use_collapse_triangulate = True
    select([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return tris(o)


def pivot_to_center(o):
    mn, mx = bbox([o])
    c = Vector(((mn + mx) / 2).tolist())
    o.data.transform(Matrix.Translation(-c)); o.location = o.location + c
    return c


def _color_source(nt):
    """(image_node, rgba, alpha) feeding the visible colour of a node tree (Principled, spec-gloss Diffuse, Emission)."""
    bs = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    sock = None
    if bs:
        sock = bs.inputs['Base Color']
    else:
        d = next((n for n in nt.nodes if n.type == 'BSDF_DIFFUSE'), None) or next((n for n in nt.nodes if n.type == 'EMISSION'), None)
        if d:
            sock = d.inputs['Color']
    if sock is None:
        return None, (0.8, 0.8, 0.8, 1), 1.0, None
    alpha = bs.inputs['Alpha'].default_value if bs else 1.0
    if not sock.is_linked:
        return None, tuple(sock.default_value), alpha, None
    stack = [sock.links[0].from_node]; seen = set(); img = None; vcol = None
    while stack:
        n = stack.pop(0)
        if n.name in seen:
            continue
        seen.add(n.name)
        if n.type == 'TEX_IMAGE' and n.image and img is None:
            img = n.image
        if n.type in ('VERTEX_COLOR', 'ATTRIBUTE') and vcol is None:
            vcol = getattr(n, 'layer_name', None) or getattr(n, 'attribute_name', None) or 'Col'
        stack += [l.from_node for i in n.inputs for l in i.links]
    return img, (1, 1, 1, 1) if (img or vcol) else tuple(sock.default_value), alpha, vcol


def slim_materials(objs, max_size=512, big=None):
    """Rebuild every material as Principled + (optional) base-colour image: the game only uses a colour map."""
    seen = set()
    for o in objs:
        for s in o.material_slots:
            m = s.material
            if not m or not m.use_nodes or m.name in seen:
                continue
            seen.add(m.name)
            nt = m.node_tree
            img, col, alpha, vcol = _color_source(nt)
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
            nt.links.new(bs.outputs[0], out.inputs['Surface'])
            bs.inputs['Roughness'].default_value = 0.8; bs.inputs['Alpha'].default_value = alpha
            src = None
            if img is not None:
                t = nt.nodes.new('ShaderNodeTexImage'); t.image = img; src = t.outputs['Color']
                lim = (big or {}).get(re.sub(r"\.\d{3}$", "", m.name), max_size)
                if max(img.size) > lim:
                    img.scale(lim, lim)
            if vcol:
                va = nt.nodes.new('ShaderNodeVertexColor'); va.layer_name = vcol
                if src is not None:
                    mx = nt.nodes.new('ShaderNodeMixRGB'); mx.blend_type = 'MULTIPLY'; mx.inputs['Fac'].default_value = 1
                    nt.links.new(src, mx.inputs['Color1']); nt.links.new(va.outputs['Color'], mx.inputs['Color2']); src = mx.outputs['Color']
                else:
                    src = va.outputs['Color']
            if src is not None:
                nt.links.new(src, bs.inputs['Base Color'])
            else:
                bs.inputs['Base Color'].default_value = col
    return len(seen)


def export(objs, root_name, fname, image_format='JPEG', draco=True, extra=None):
    c = objs[0].users_collection[0]
    root = bpy.data.objects.new(root_name, None); c.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root
    select([root] + objs, root)
    path = os.path.join(MODELS, fname)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_image_format=image_format, export_yup=True,
              export_apply=False, export_cameras=False, export_lights=False)
    if draco:
        kw.update(export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                  export_draco_texcoord_quantization=14)
    if extra:
        kw.update(extra)
    bpy.ops.export_scene.gltf(**kw)
    return root, os.path.getsize(path)
