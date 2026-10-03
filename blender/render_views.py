"""Preview renders of the HD world (EEVEE). Camera positions are given in GAME coords."""
import bpy, mathutils, os

OUT = os.environ.get('BORSO_RENDER_OUT', r"C:\Coding\borso-simulator\tools\out\renders")
os.makedirs(OUT, exist_ok=True)

VIEWS = {
    'overview': ((60, 230, 260), (-60, 20, -120), 24),
    'street': ((-4, 1.8, 12), (2, 4, -30), 24),
    'piazza_hi': ((35, 22, 25), (-5, 2, -30), 24),
    'grappa': ((-40, 120, -250), (-110, 72, -340), 26),
    'grappa_face': ((-30, 60, 60), (-60, 200, -500), 22),
    'semonzo': ((-140, 30, 40), (-185, 5, -30), 24),
    'fields': ((-60, 18, 120), (40, 0, 40), 24),
}


def look(cam, pos, target, lens):
    p = mathutils.Vector((pos[0], -pos[2], pos[1]))
    t = mathutils.Vector((target[0], -target[2], target[1]))
    cam.location = p
    cam.data.lens = lens
    cam.rotation_euler = (t - p).to_track_quat('-Z', 'Y').to_euler()


def render(names=None, res=(1280, 720)):
    sc = bpy.context.scene
    cam = sc.camera
    sc.render.resolution_x, sc.render.resolution_y = res
    done = []
    for k, (p, t, l) in VIEWS.items():
        if names and k not in names:
            continue
        look(cam, p, t, l)
        sc.render.filepath = os.path.join(OUT, k + '.png')
        bpy.ops.render.render(write_still=True)
        done.append(sc.render.filepath)
    return done
