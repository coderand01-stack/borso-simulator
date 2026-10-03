"""One-off source patch: terrain triangles with a known diagonal, roads/drapes conform to the terrain mesh."""
p = r'C:\Coding\borso-simulator\blender\build_world.py'
s = open(p, encoding='utf-8').read()


def R(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:60])
    s = s.replace(a, b)


R("""                    faces.append((a, b, c, d))
                    mx = (gx[i] + gx[i + 1]) / 2; mz = (gz[j] + gz[j + 1]) / 2
                    if mz > -40 and -480 < mx < 320 and town_mask(np.array([mx]), np.array([mz]))[0] < 0.5:
                        fc = field_color(mx, mz)
                        fcols.append([fc * shade[v] for v in (a, b, c, d)])
                    else:
                        fcols.append([vcol[v] * shade[v] for v in (a, b, c, d)])""",
  """                    faces.append((a, b, c)); faces.append((a, c, d))
                    mx = (gx[i] + gx[i + 1]) / 2; mz = (gz[j] + gz[j + 1]) / 2
                    if mz > -40 and -480 < mx < 320 and town_mask(np.array([mx]), np.array([mz]))[0] < 0.5:
                        fc = field_color(mx, mz)
                        fcols.append([fc * shade[v] for v in (a, b, c)]); fcols.append([fc * shade[v] for v in (a, c, d)])
                    else:
                        fcols.append([vcol[v] * shade[v] for v in (a, b, c)]); fcols.append([vcol[v] * shade[v] for v in (a, c, d)])""")
R("""def build_terrain(occ_sample):
    xs = grid_lines(-700, 700, -485, 330, 5, 20, [X0 + CHUNK * i for i in range(NCX + 1)] + [42 * k for k in range(-11, 8)] + [-480, 320])
    zs = grid_lines(-780, 420, -420, 280, 5, 20, [Z0 + CHUNK * j for j in range(NCZ + 1)] + [31 * k for k in range(-1, 9)] + [-40])
""", '''XS = None; ZS = None


def terrain_grid():
    global XS, ZS
    XS = grid_lines(-700, 700, -485, 330, 5, 20, [X0 + CHUNK * i for i in range(NCX + 1)] + [42 * k for k in range(-11, 8)] + [-480, 320])
    ZS = grid_lines(-780, 420, -420, 280, 5, 20, [Z0 + CHUNK * j for j in range(NCZ + 1)] + [31 * k for k in range(-1, 9)] + [-40])
    return XS, ZS


def Tmesh(x, z):
    """Height of the rendered terrain mesh (same grid and diagonal as build_terrain)."""
    i = int(np.clip(np.searchsorted(XS, x) - 1, 0, len(XS) - 2)); j = int(np.clip(np.searchsorted(ZS, z) - 1, 0, len(ZS) - 2))
    x0, x1, z0, z1 = XS[i], XS[i + 1], ZS[j], ZS[j + 1]
    u = (x - x0) / (x1 - x0); v = (z - z0) / (z1 - z0)
    ha, hb, hc, hd = float(H(x0, z0)), float(H(x0, z1)), float(H(x1, z1)), float(H(x1, z0))
    if v >= u:
        return ha + v * (hb - ha) + u * (hc - hb)
    return ha + u * (hd - ha) + v * (hc - hd)


def Hs(x, z):
    """Surface height for things laid on the ground: never below the rendered terrain."""
    return max(H(x, z), Tmesh(x, z))


def build_terrain(occ_sample):
    xs, zs = terrain_grid()
''')
a = s.index("def build_roads():"); b = s.index("# ============================================================== terrain", a)
s = s[:a] + '''def resample(d, step):
    out = [d[0]]
    for i in range(1, len(d)):
        a, b = d[i - 1], d[i]
        L_ = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(math.ceil(L_ / step)))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return out


def build_roads():
    for ri, r in enumerate(L['roads']):
        d = resample(r['dense'], 1.5); hw = r['w'] / 2; yo = r['yo'] + ri * 0.003
        mat = 'M_RoadMain' if r['main'] else 'M_RoadSmall'
        sh = 0.9  # gravel shoulder
        ncol = max(2, int(math.ceil(2 * hw / 2.2)))
        cols = [(hw + sh, -0.07, 0.0)] + [(hw - 2 * hw * k / ncol, 0.0, 0.1 + 0.8 * k / ncol) for k in range(ncol + 1)] + [(-hw - sh, -0.07, 1.0)]
        rows = []
        v = 0.0
        for i in range(len(d)):
            a = d[max(0, i - 1)]; b = d[min(len(d) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dz) or 1; dx /= l; dz /= l
            nx, nz = -dz, dx
            if i > 0:
                v += math.hypot(d[i][0] - d[i - 1][0], d[i][1] - d[i - 1][1])
            row = []
            for off, dy, u in cols:
                px, pz = d[i][0] + nx * off, d[i][1] + nz * off
                row.append((px, Hs(px, pz) + yo + dy, pz))
            rows.append((row, v / 9.0))
        us = [c[2] for c in cols]
        for i in range(1, len(rows)):
            (ra, va), (rb, vb) = rows[i - 1], rows[i]
            for k in range(len(cols) - 1):
                pts = [ra[k], ra[k + 1], rb[k + 1], rb[k]]
                uv = [(us[k], va), (us[k + 1], va), (us[k + 1], vb), (us[k], vb)]
                emit(mat, pts, (1, 1, 1), uvs=uv, center=(pts[0][0], pts[0][1] - 10, pts[0][2]), ao=False)


''' + s[b:]
R("pts = [(x0, H(x0, z0) + yo, z0), (x0, H(x0, z1) + yo, z1), (x1, H(x1, z1) + yo, z1), (x1, H(x1, z0) + yo, z0)]",
  "pts = [(x0, Hs(x0, z0) + yo, z0), (x0, Hs(x0, z1) + yo, z1), (x1, Hs(x1, z1) + yo, z1), (x1, Hs(x1, z0) + yo, z0)]")
R("g0 = H(*p0) + yo + 0.06; g1 = H(*p1) + yo + 0.06", "g0 = Hs(*p0) + yo + 0.06; g1 = Hs(*p1) + yo + 0.06")
R("    log = {'h_err': check_heights()}", "    log = {'h_err': check_heights()}\n    terrain_grid()")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
