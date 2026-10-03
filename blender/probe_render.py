"""Render a quick preview of one imported asset hierarchy (isolated) for inspection."""
import bpy, mathutils, os, math

OUT = r"C:\Coding\borso-simulator\tools\out\renders"


def world_bbox(objs):
    pts = []
    for o in objs:
        if o.type == 'MESH':
            pts += [o.matrix_world @ mathutils.Vector(b) for b in o.bound_box]
    mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
    mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    return mn, mx


def preview(root_name, name, az=35, el=25, lens=40, inside=False):
    sc = bpy.context.scene
    root = bpy.data.objects[root_name]
    objs = [root] + list(root.children_recursive)
    keep = set(objs)
    hidden = []
    for o in sc.objects:
        if o.type in ('MESH', 'EMPTY') and o not in keep and not o.hide_render:
            o.hide_render = True; hidden.append(o)
    mn, mx = world_bbox(objs)
    c = (mn + mx) / 2; r = (mx - mn).length / 2
    cam = sc.camera
    cam.data.type = 'PERSP'; cam.data.lens = lens; cam.data.clip_start = max(0.001, r * 0.002); cam.data.clip_end = r * 50
    d = r / math.tan(math.atan(18 / lens)) * 1.05
    if inside:
        d = 0.01
    a, e = math.radians(az), math.radians(el)
    cam.location = c + mathutils.Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = 900, 600
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    return sc.render.filepath, [round(v, 2) for v in mn], [round(v, 2) for v in mx]
