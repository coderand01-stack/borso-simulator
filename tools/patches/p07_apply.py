"""One-off: wires traffic/ground (p04), Binea items (p06), Sacrario and metal materials into tools/hd_block.js."""
P = r'C:\Coding\borso-simulator\tools\patches'
p = r'C:\Coding\borso-simulator\tools\hd_block.js'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


# traffic + ground height before the material helpers, items before the interiors
rep("/* ---------- colori e materiali ---------- */", open(P + r'\p04_traffic.js', encoding='utf-8').read() + "/* ---------- colori e materiali ---------- */")
rep("/* ---------- interni ---------- */", open(P + r'\p06_items.js', encoding='utf-8').read() + "/* ---------- interni ---------- */")

# metal parts (items, Sacrario bronze) are shiny
rep("  const paint = m.name === 'Paint', glass = m.name === 'Glass';\n  return new THREE.MeshPhongMaterial({ name: m.name, map: m.map, color: m.color.clone().convertLinearToSRGB(), vertexColors: vc,\n    shininess: paint ? 50 : glass ? 80 : 6, specular: paint ? 0x333333 : glass ? 0x666666 : 0x0d0d0d,",
    "  const paint = m.name === 'Paint', glass = m.name === 'Glass', metal = /^Metal/.test(m.name);\n  return new THREE.MeshPhongMaterial({ name: m.name, map: m.map, color: m.color.clone().convertLinearToSRGB(), vertexColors: vc,\n    shininess: paint ? 50 : glass ? 80 : metal ? 70 : 6, specular: paint ? 0x333333 : glass ? 0x666666 : metal ? 0x8a8070 : 0x0d0d0d,")

# loading: ground height first, then items + Sacrario with the other small models
rep("function loadHD(onProgress) {\n  const tx = hdTextures();", "function loadHD(onProgress) {\n  hdSurfaceInit();\n  const tx = hdTextures();")
rep("  let done = 0; parts.forEach(p => p.then(() => { done++; prog.other = done / parts.length; tick(); }));",
    "  parts.push(hdLoad('models/items.glb').then(g => { if (!g) return; hdPrepAsset(g.scene); HDM.items = {}; g.scene.traverse(o => { if (/^item_/.test(o.name) && !/^item_/.test(o.parent && o.parent.name || '')) HDM.items[o.name] = o; }); }));\n"
    "  parts.push(hdLoad('models/sacrario.glb').then(g => { if (!g) return; hdSacrario(g.scene); }));\n"
    "  let done = 0; parts.forEach(p => p.then(() => { done++; prog.other = done / parts.length; tick(); }));")
rep("// interni in sottofondo dopo il titolo",
    "// Sacrario del Monte Grappa, sulla vetta fuori dall'area di gioco: meno nebbia del resto, illuminato di notte\n"
    "function hdSacrario(root) {\n"
    "  const mat = new THREE.MeshLambertMaterial({ vertexColors: true, emissive: 0xfff2d8, emissiveIntensity: 0 });\n"
    "  mat.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <fog_fragment>', '#ifdef USE_FOG\\n  gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor, smoothstep(fogNear, fogFar, fogDepth) * 0.55);\\n#endif'); };\n"
    "  root.traverse(o => { if (!o.isMesh) return; hdFixColors(o.geometry); o.material = mat; o.castShadow = false; o.receiveShadow = false; });\n"
    "  root.updateMatrixWorld(true); root.traverse(o => { o.matrixAutoUpdate = false; });\n"
    "  world.add(root); HDM.sacrario = [mat];\n"
    "}\n"
    "// interni in sottofondo dopo il titolo")

# chiesa: options were swallowed by a comment; altar slots show the real objects
rep("  const R = hdRoom({ name: 'Chiesa di Semonzo', w: 23.3, d: 38.0, h: 18, door: false, // la porta del modello è a z=19.45: l'uscita cade davanti bg: 0x0c0a0e, hemi: 0.55, amb: 0.3, sky: 0xfff0d8,\n",
    "  // door: false -> la porta del modello è a z=19.45, l'uscita cade davanti\n  const R = hdRoom({ name: 'Chiesa di Semonzo', w: 23.3, d: 38.0, h: 18, door: false, bg: 0x0c0a0e, hemi: 0.55, amb: 0.3, sky: 0xfff0d8,\n")
rep("  R.slots = {}; for (const k in ALTAR_SLOTS) { const [x, c] = ALTAR_SLOTS[k]; const m = new THREE.Mesh(bxg(0.22, 0.3, 0.22), lm(c)); m.position.set(x * 1.1, 1.27, -9.95); m.visible = false; R.S.add(m); R.slots[k] = m; }",
    "  R.slots = {}; for (const k in ALTAR_SLOTS) { // gli oggetti ritrovati tornano sull'altare\n"
    "    const [x, c] = ALTAR_SLOTS[k]; let m = hdItemModel(k, HD_ITEM[k][2]);\n"
    "    if (m) { m.position.set(x * 1.15, 1.115, -9.95); if (k === 'libro') m.rotation.y = 0.35; } else { m = new THREE.Mesh(bxg(0.22, 0.3, 0.22), lm(c)); m.position.set(x * 1.1, 1.27, -9.95); }\n"
    "    m.visible = false; R.S.add(m); R.slots[k] = m;\n  }")

# bar: the Bible really is under the foosball table while the quest needs it
rep("  R.hot(9.3, 2.3, 'Prendi il libro sotto il biliardino', () => collectBinea('libro'), 1.4, () => GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro'));\n  return R;",
    "  R.hot(9.3, 2.3, 'Prendi la Bibbia sotto il biliardino', () => collectBinea('libro'), 1.4, () => GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro'));\n"
    "  R.bible = hdItemModel('libro', 0.3); if (R.bible) { R.bible.position.set(9.0, 0.005, 1.45); R.bible.rotation.y = 0.6; R.S.add(R.bible); }\n"
    "  R.onEnter = () => { if (R.bible) R.bible.visible = GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro'); };\n  return R;")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
