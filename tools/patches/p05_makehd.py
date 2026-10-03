"""One-off: adds the round-2 fixes to tools/make_hd.py (traffic, ground height, entrances, Binea items, rig, Sacrario)."""
p = r'C:\Coding\borso-simulator\tools\make_hd.py'
s = open(p, encoding='utf-8').read()
anchor = "HD_BLOCK = open(os.path.join(ROOT, 'tools', 'hd_block.js'), encoding='utf-8').read() + '\\n'\n"
assert s.count(anchor) == 1
block = r'''# --- ingressi liberi: niente case davanti al sagrato di Semonzo e al cancello del cimitero, né sugli oggetti delle quest
s = rep(s, "  drapedArea(-30, -9.6, 16, 6, 'cobble', 0xd8cfc0, 0.11, 0.25);     // plateatico osteria\n",
        "  drapedArea(-30, -9.6, 16, 6, 'cobble', 0xd8cfc0, 0.11, 0.25);     // plateatico osteria\n"
        "  if (HD) { reserved.push({ x0: -199, x1: -177, z0: -30, z1: -10 }, { x0: 45, x1: 79, z0: -25, z1: -4 }); // sagrato di Semonzo, ingresso del cimitero\n"
        "    for (const [qx, qz] of [[206, 50], [-226, 78.5], [66, -30], [13.8, -106.4], [-221, 80]]) reserved.push({ x0: qx - 3, x1: qx + 3, z0: qz - 3, z1: qz + 3 }); }\n")
s = rep(s, "function drapedArea(cx, cz, w, d, key, color, yo = 0.1, uvScale = 0.12) {\n",
        "function drapedArea(cx, cz, w, d, key, color, yo = 0.1, uvScale = 0.12) {\n  if (HD) (HDM.drapes = HDM.drapes || []).push([cx, cz, w, d, yo]);\n")

# --- vetta del Grappa: oltre i 500 m il massiccio si spiana in un altopiano, il Sacrario sta su un piazzale in cima
s = rep(s, "  if (z > 250) { const t = z - 250; h += t * 0.12 + Math.sin(x * 0.03) * t * 0.05; }\n  return h;\n}",
        "  if (z > 250) { const t = z - 250; h += t * 0.12 + Math.sin(x * 0.03) * t * 0.05; }\n"
        "  if (HD && h > 500) h = 500 + 40 * (1 - Math.exp(-(h - 500) / 40)); // altopiano\n"
        "  if (HD && SAC.y !== null && z < -560) { const d = Math.hypot(x - SAC.x, z - SAC.z); if (d < SAC.r1) { const t = clamp((SAC.r1 - d) / (SAC.r1 - SAC.r0), 0, 1); h += (SAC.y - h) * t * t * (3 - 2 * t); } }\n"
        "  return h;\n}\n"
        "const SAC = { x: -40, z: -640, r0: 40, r1: 75, y: null }; SAC.y = Hbase(SAC.x, SAC.z); // piazzale del Sacrario del Grappa")

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

'''
s = s.replace(anchor, block + '\n' + anchor)
# il patch del bagliore notturno sta dopo HD_BLOCK: va applicato dopo quello
open(p, 'w', encoding='utf-8').write(s)
print('ok')
