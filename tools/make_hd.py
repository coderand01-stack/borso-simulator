"""Generates docs/index.html (Borso Simulator HD) from the original game.

The original world-building code still runs, so colliders, houses, quests and the seeded
layout stay identical, but its procedural meshes are switched off and the world built in
Blender (docs/models/world.glb) is loaded instead. Re-run after editing the original:
    python tools/make_hd.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()


def rep(s, old, new, count=1):
    n = s.count(old)
    if n != count:
        raise SystemExit(f'patch failed ({n} matches, expected {count}): {old[:70]!r}')
    return s.replace(old, new)


s = src
s = rep(s, '<title>Borso Simulator</title>', '<title>Borso Simulator HD</title>')
s = rep(s, '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>',
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/DRACOLoader.js"></script>')
s = rep(s, 'const LOWQ = IS_TOUCH;', 'const LOWQ = IS_TOUCH;\nconst HD = true; // grafica da docs/models/*.glb: la geometria procedurale non viene disegnata\nconst HDM = { pendingChars: [], cars: {} };')

# --- the procedural meshes are replaced by the .glb (colliders and layout logic stay)
s = rep(s, '(function buildTerrain() {', '(function buildTerrain() {\n  if (HD) return;')
s = rep(s, 'ROADS.forEach(r => {\n  const d = r.dense, pos = []', 'if (!HD) ROADS.forEach(r => {\n  const d = r.dense, pos = []')
s = rep(s, '  add(geo, key, m, color) {\n', '  add(geo, key, m, color) {\n    if (HD) return;\n')
s = rep(s, '  { const y = H(20, 9.7); const m = new THREE.Mesh(', '  if (!HD) { const y = H(20, 9.7); const m = new THREE.Mesh(')
s = rep(s, '(function () { const x = -40, z = -640, y = H(x, z);', 'if (!HD) (function () { const x = -40, z = -640, y = H(x, z);')

# --- one fixed layout for every device (the .glb was baked from the desktop layout)
for old, new in [('const want2 = LOWQ ? 150 : 300;', 'const want2 = 300;'),
                 ('const want3 = LOWQ ? 20 : 46;', 'const want3 = 46;'),
                 ("n: LOWQ ? 30 : 38, tall", "n: 38, tall"),
                 ("r: 62, n: LOWQ ? 20 : 26", "r: 62, n: 26"),
                 ("r: 60, n: LOWQ ? 18 : 24", "r: 60, n: 24"),
                 ("r: 56, n: LOWQ ? 14 : 20", "r: 56, n: 20"),
                 ('while (fh < (LOWQ ? 16 : 24) && tries < 2000)', 'while (fh < 24 && tries < 2000)'),
                 ('const want = LOWQ ? 260 : 420;', 'const want = 420;'),
                 ('for (let i = 0; i < (LOWQ ? 260 : 420); i++) { const x = sr(-500, 500)', 'for (let i = 0; i < 420; i++) { const x = sr(-500, 500)'),
                 ('for (let i = 0; i < (LOWQ ? 60 : 110); i++) { const x = sr(-480, 480)', 'for (let i = 0; i < 110; i++) { const x = sr(-480, 480)')]:
    s = rep(s, old, new)

# --- layout fixes: houses never on the (smoothed) roads, hand-placed props moved off the carriageway
s = rep(s, '    ROAD_SEGS.push({ ax: a[0], az: a[1], bx: b[0], bz: b[1], w: r.w, road: r });\n', '')
s = rep(s, '  r.dense = d;\n});',
        '  r.dense = d;\n'
        '  // distanze misurate sul tracciato disegnato (curve smussate), non sulla spezzata di controllo\n'
        '  for (let i = 0; i < d.length - 1; i++) ROAD_SEGS.push({ ax: d[i][0], az: d[i][1], bx: d[i + 1][0], bz: d[i + 1][1], w: r.w, road: r });\n'
        '});')
s = rep(s, '  const pts = [[x, z], [x - ex / 2, z - ez / 2], [x + ex / 2, z - ez / 2], [x - ex / 2, z + ez / 2], [x + ex / 2, z + ez / 2], [x, z - ez / 2], [x, z + ez / 2], [x - ex / 2, z], [x + ex / 2, z]];\n'
           '  for (const [px, pz] of pts) if (!roadClear(px, pz, 2.2)) return false;',
        '  for (let i = 0; i <= 6; i++) for (let j = 0; j <= 6; j++) if (!roadClear(x - ex / 2 + ex * i / 6, z - ez / 2 + ez * j / 6, 2.8)) return false;')
s = rep(s, "shop(4, 13, 8, 8, 0xe9c79a, ['TABACCHI']", "shop(10, 13, 7, 8, 0xe9c79a, ['TABACCHI']")
s = rep(s, "tabacchi: { name: 'Tabacchi', door: { x: 4, z: 7.7 }", "tabacchi: { name: 'Tabacchi', door: { x: 10, z: 7.7 }")
s = rep(s, "fermata(26, -95, -Math.PI / 2, 'Cassanego');", "fermata(12.5, -86, Math.PI / 2, 'Cassanego');")
s = rep(s, '[[-96, -6, 0], [94, -6, 0], [-166, 6, Math.PI]]', '[[-96, -9, 0], [97, -9.5, 0], [-166, 8.5, Math.PI]]')
s = rep(s, "  church(170, -42, 11, 22, 12, 0, 26, 180, -49, \"Sant'Eulalia\");", "  seChurch(); // chiesa da assets/church.glb (models/world.glb)")
s = rep(s, '[162, -32], [178, -32]]) tree(x, z, 0.75, \'cypress\');', '[161, -31], [188, -31]]) tree(x, z, 0.75, \'cypress\');')

# --- vehicles: capsule colliders (car-sized) instead of one big circle, more Fiat models in traffic
s = rep(s, """  panda: { name: 'Panda 4x4', max: 26, acc: 9, steer: 1.9, r: 1.7, len: 3.6 },
  golf: { name: 'Utilitaria', max: 30, acc: 11, steer: 1.8, r: 1.8, len: 4 },
  ape: { name: 'Ape Piaggio', max: 15, acc: 6, steer: 2.3, r: 1.4, len: 3 },
  trattore: { name: 'Trattore', max: 11, acc: 4, steer: 1.6, r: 1.9, len: 3.6 },""",
"""  panda: { name: 'Panda 4x4', max: 26, acc: 9, steer: 1.9, r: 1.7, len: 3.45, hw: 0.76 },
  golf: { name: 'Panda Young', max: 30, acc: 11, steer: 1.8, r: 1.8, len: 3.45, hw: 0.76 },
  ape: { name: 'Ape Piaggio', max: 15, acc: 6, steer: 2.3, r: 1.4, len: 3, hw: 0.66 },
  trattore: { name: 'Trattore', max: 11, acc: 4, steer: 1.6, r: 1.9, len: 3.0, hw: 0.8 },
  cinquecento: { name: 'Fiat 500', max: 22, acc: 8, steer: 2.1, r: 1.5, len: 2.97, hw: 0.68 },
  multipla: { name: 'Fiat Multipla', max: 28, acc: 9, steer: 1.7, r: 1.9, len: 4.0, hw: 0.9 },""")
s = rep(s, "this.radius = this.spec.r;", "this.radius = this.spec.r; this.hw = this.spec.hw || 0.8;")
s = rep(s, "  if (type === 'panda' || type === 'golf') {\n", "  if (type === 'panda' || type === 'golf' || type === 'cinquecento' || type === 'multipla') {\n")
s = rep(s, "const type = Math.random() < 0.6 ? pick(['panda', 'golf']) :", "const type = Math.random() < 0.6 ? pick(['panda', 'golf', 'cinquecento', 'multipla', 'panda']) :")
s = rep(s, "  const hitB = collideCircle(c.pos, c.radius, c.pos.y + 0.3);", "  const hitB = carCollideWorld(c);")
s = rep(s, """    if (o === c) continue; const dx = o.pos.x - c.pos.x, dz = o.pos.z - c.pos.z, d = Math.hypot(dx, dz), rr = c.radius + o.radius;
    if (d < rr && d > 0.01) { const push = (rr - d) / 2; c.pos.x -= dx / d * push; c.pos.z -= dz / d * push; o.pos.x += dx / d * push; o.pos.z += dz / d * push;""",
"""    if (o === c) continue; const cd = carCarDist(c, o), rr = c.hw + o.hw, d = Math.hypot(cd.dx, cd.dz) || 1, dx = cd.dx, dz = cd.dz;
    if (cd.d < rr) { const push = (rr - cd.d) / 2; c.pos.x -= dx / d * push; c.pos.z -= dz / d * push; o.pos.x += dx / d * push; o.pos.z += dz / d * push; o.place();""")
s = rep(s, "    if (d < c.radius + a.radius) {\n      if (isEnemy(a))", "    if (carPointDist(c, a.pos.x, a.pos.z).d < c.hw + a.radius) {\n      if (isEnemy(a))")
s = rep(s, """    if (c === player.inCar) continue; const ddx = a.pos.x - c.pos.x, ddz = a.pos.z - c.pos.z, d = Math.hypot(ddx, ddz), rr = c.radius + 0.4;
    if (d < rr && d > 0.01) {""", """    if (c === player.inCar) continue; const cp = carPointDist(c, a.pos.x, a.pos.z), ddx = cp.dx, ddz = cp.dz, d = cp.d, rr = c.hw + 0.4;
    if (d < rr && d > 0.01) {""")
s = rep(s, "const dx = x - c.pos.x, dz = z - c.pos.z; if (dx * dx + dz * dz < c.radius * c.radius && y < c.pos.y + 1.8) {",
        "if (carPointDist(c, x, z).d < c.hw + 0.1 && y < c.pos.y + 1.8) {")

# LAYOUT_V2: case lontane dagli ingressi (chiesa di Semonzo, cimitero) e vetta del Grappa spianata.
# world.glb e tools/out/layout.json sono costruiti con questo layout: se lo cambi, rigenerali entrambi.
LAYOUT_V2 = True
# --- ingressi liberi: niente case davanti al sagrato di Semonzo e al cancello del cimitero, né sugli oggetti delle quest
if LAYOUT_V2: s = rep(s, "  drapedArea(-30, -9.6, 16, 6, 'cobble', 0xd8cfc0, 0.11, 0.25);     // plateatico osteria\n",
        "  drapedArea(-30, -9.6, 16, 6, 'cobble', 0xd8cfc0, 0.11, 0.25);     // plateatico osteria\n"
        "  if (HD) { reserved.push({ x0: -199, x1: -177, z0: -30, z1: -10 }, { x0: 45, x1: 79, z0: -25, z1: -4 }); // sagrato di Semonzo, ingresso del cimitero\n"
        "    for (const [qx, qz] of [[206, 50], [-226, 78.5], [66, -30], [13.8, -106.4], [-221, 80]]) reserved.push({ x0: qx - 3, x1: qx + 3, z0: qz - 3, z1: qz + 3 }); }\n")
s = rep(s, "function drapedArea(cx, cz, w, d, key, color, yo = 0.1, uvScale = 0.12) {\n",
        "function drapedArea(cx, cz, w, d, key, color, yo = 0.1, uvScale = 0.12) {\n  if (HD) (HDM.drapes = HDM.drapes || []).push([cx, cz, w, d, yo]);\n")

# --- vetta del Grappa: oltre i 500 m il massiccio si spiana in un altopiano, il Sacrario sta su un piazzale in cima
if LAYOUT_V2: s = rep(s, "  if (z > 250) { const t = z - 250; h += t * 0.12 + Math.sin(x * 0.03) * t * 0.05; }\n  return h;\n}",
        "  if (z > 250) { const t = z - 250; h += t * 0.12 + Math.sin(x * 0.03) * t * 0.05; }\n"
        "  if (HD && h > 500) h = 500 + 40 * (1 - Math.exp(-(h - 500) / 40)); // altopiano\n"
        "  if (HD && SAC.y !== null && z < -560) { const d = Math.hypot(x - SAC.x, z - SAC.z); if (d < SAC.r1) { const t = clamp((SAC.r1 - d) / (SAC.r1 - SAC.r0), 0, 1); h += (SAC.y - h) * t * t * (3 - 2 * t); } }\n"
        "  return h;\n}\n"
        "const SAC = { x: -40, z: -640, r0: 34, r1: 52, y: null }; SAC.y = Hbase(SAC.x, SAC.z); // piazzale del Sacrario sulla cresta: dal paese si staglia contro il cielo")

# --- traffico: svolte agli incroci (hdLaneStep in hd_block.js)
s = rep(s, "  if (c.s >= L.len - 2) { c.lane = L.pair; c.s = 2; lanePoint(c.lane, c.s, _lp); c.pos.x = _lp.x; c.pos.z = _lp.z; const q = lanePoint(c.lane, c.s + 3, {}); c.heading = Math.atan2(q.x - _lp.x, q.z - _lp.z); }\n",
        "  hdLaneStep(c, L);\n")

# --- camminata: braccio opposto alla gamba (prima braccio e gamba dello stesso lato andavano insieme)
s = rep(s, "  else c.armR.rotation.x = -sn * amp * 0.9;", "  else c.armR.rotation.x = sn * amp * 0.9;")
s = rep(s, "Math.sin(a.phase * 3 + performance.now() * 0.01) * 0.3 : sn * amp * 0.9);", "Math.sin(a.phase * 3 + performance.now() * 0.01) * 0.3 : -sn * amp * 0.9);")

# --- quest di Binea: gli oggetti sacri sono i modelli 3D della chiesa (calice/Graal, Bibbia, croce) + campanello e turibolo fatti in Blender
s = rep(s, "  madonna: { name: 'Statuina della Madonna del Carmine', x: 66, z: -30, where: 'al cimitero', txt: 'Qualcuno l\\'aveva messa sulla tomba della suocera. Per farle dispetto.' },",
        "  madonna: { name: 'Croce di legno', x: 66, z: -30, where: 'al cimitero', txt: 'Qualcuno l\\'aveva piantata sulla tomba della suocera. Per sicurezza.' },")
s = rep(s, "  candelabro: { name: 'Candelabro', x: 13.8, z: -106.4, where: 'al capitello di Cassanego', txt: 'Faceva luce ai ladri. Ironia della sorte.' },",
        "  candelabro: { name: 'Calice d\\'oro', x: 13.8, z: -106.4, where: 'al capitello di Cassanego', txt: 'El vecio Toni ci beveva il clinto. Dice che così sa di santo.' },")
s = rep(s, "  libro: { name: 'Libro dei canti', interior: 'bar', where: 'dentro il Bar Sport', txt: 'Pareggiava il biliardino. Da trent\\'anni.' },",
        "  libro: { name: 'Bibbia dell\\'altare', interior: 'bar', where: 'dentro il Bar Sport', txt: 'Pareggiava il biliardino. Da trent\\'anni.' },")
s = rep(s, "t: 'El campanèo! El turibolo! La Madonna del Carmine... la ga un graffio, ma la xe sempre bea.",
        "t: 'El campanèo! El turibolo! El càlice, la Bibia, la crose de legno... la crose la ga un graffio, ma la xe sempre bea.")
s = rep(s, "function addQItem(id, x, z, gold = true) { if (QITEMS.some(i => i.id === id)) return; const g = makeItemMesh(gold);",
        "function addQItem(id, x, z, gold = true) { if (QITEMS.some(i => i.id === id)) return; const g = HD ? hdItemMesh(id, gold) : makeItemMesh(gold);")
s = rep(s, "function collectBinea(id) {\n  const b = GS.q.binea; if (b.items.includes(id)) return; b.items.push(id); removeQItem(id); sfx('unlock');",
        "function collectBinea(id) {\n  const b = GS.q.binea; if (b.items.includes(id)) return; b.items.push(id); removeQItem(id); sfx('unlock'); if (HD) hdItemCollected(id);")


HD_BLOCK = open(os.path.join(ROOT, 'tools', 'hd_block.js'), encoding='utf-8').read() + '\n'
s = rep(s, '/* =====================================================================\n   DAY / NIGHT', HD_BLOCK + '/* =====================================================================\n   DAY / NIGHT')
s = rep(s, 'MATS.facade.emissiveIntensity = nK * 0.95; MATS.lamp.emissiveIntensity = nK * 1.3;',
        'MATS.facade.emissiveIntensity = nK * 0.95; MATS.lamp.emissiveIntensity = nK * 1.3;\n'
        '  if (HDM.winLit) { HDM.winLit.emissiveIntensity = nK * 0.95; HDM.lamp.emissiveIntensity = nK * 1.3; }\n'
        '  if (HDM.sacrario) HDM.sacrario.forEach(m => m.emissiveIntensity = nK * 0.45);')

s = rep(s, 'function makeChar(o) {\n  const root = new THREE.Group()', 'function makeCharProc(o) {\n  const root = new THREE.Group()')
# scheletro dei personaggi: va definito prima che il gioco crei il giocatore
HD_RIG = open(os.path.join(ROOT, 'tools', 'hd_rig.js'), encoding='utf-8').read()
s = rep(s, '\nconst P = {\n  bepi:', '\n' + HD_RIG + '\nconst P = {\n  bepi:')
s = rep(s, '    scene.add(this.mesh); cars.push(this);\n', '    scene.add(this.mesh); cars.push(this);\n    if (HD) hdAddDriver(this);\n')
s = rep(s, '    this.wheelRot += this.speed * 0.05; for (const w of this.wheels) w.rotation.x = this.wheelRot;\n',
        '    this.wheelRot += this.speed * 0.05; for (const w of this.wheels) w.rotation.x = this.wheelRot;\n    if (this.seatDriver) hdSeatUpdate(this);\n')
s = rep(s, "build: buildBar }", "build: buildBarHD }")
s = rep(s, "build: buildChiesa }", "build: buildChiesaHD }")
for k, fn in [('farmacia', 'buildFarmacia'), ('tabacchi', 'buildTabacchi'), ('pizzeria', 'buildPizzeria'), ('scuola', 'buildScuola'),
              ('alimentari', 'buildAlimentari'), ('cubamia', 'buildCubaMia'), ('malga', 'buildMalga')]:
    s = rep(s, 'build: ' + fn + ' }', "build: () => hdDressRoom(" + fn + "(), '" + k + "') }")
s = rep(s, 'function makeCarMesh(type, color) {\n', 'function makeCarMesh(type, color) {\n  if (HD) { const hc = hdCar(type, color); if (hc) return hc; }\n')

# --- boot: wait for the map (and the vehicle models) before spawning traffic and showing the title
s = rep(s, "  for (let i = 0; i < (LOWQ ? 5 : 8); i++) spawnTrafficCar(false);\n  GS.night = isNightT(GS.time); applyTime();\n"
           "  GS.mode = 'title'; $('loading').classList.add('hidden'); $('title').classList.remove('hidden');\n  requestAnimationFrame(loop);",
        "  GS.night = isNightT(GS.time); applyTime();\n  requestAnimationFrame(loop);\n"
        "  loadHD(p => { $('loading').textContent = 'Carico Borso… ' + Math.round(p * 100) + '% (scaldo la grappa)'; })\n"
        "    .then(() => { for (let i = 0; i < (LOWQ ? 5 : 8); i++) spawnTrafficCar(false); GS.mode = 'title'; $('loading').classList.add('hidden'); $('title').classList.remove('hidden'); loadHDInteriors(); })\n"
        "    .catch(e => { console.error(e); $('loading').textContent = 'Non riesco a caricare la mappa HD. Apri il gioco da un server web (vedi docs/LEGGIMI.txt).'; });")

# --- multiplayer (tools/hd_net.js + agganci in tools/net_patches.py)
exec(open(os.path.join(ROOT, 'tools', 'net_patches.py'), encoding='utf-8').read())

os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
open(os.path.join(ROOT, 'docs', 'index.html'), 'w', encoding='utf-8').write(s)
print('docs/index.html', len(s))
