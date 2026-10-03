"""One-off: swap the rigid character groups in tools/hd_block.js for the skinned rig (p03_rig.js)."""
p = r'C:\Coding\borso-simulator\tools\hd_block.js'
s = open(p, encoding='utf-8').read()
a = s.index('const _hdPc = new THREE.Color();'); b = s.index('/* ---------- interni ---------- */')
s = s[:a] + open(r'C:\Coding\borso-simulator\tools\patches\p03_rig.js', encoding='utf-8').read() + s[b:]
old = "const HD_CHAR_MAT = new THREE.MeshLambertMaterial({ vertexColors: true });\n"
assert s.count(old) == 1; s = s.replace(old, '')
old = "parts.push(hdLoad('models/chars.glb').then(g => { if (!g) return; const P"
assert s.count(old) == 1
s = s.replace(old, "parts.push(hdLoad('models/chars.glb').then(g => { if (!g) { HDM.charFail = true; hdSkinPending(); return; } const P")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
