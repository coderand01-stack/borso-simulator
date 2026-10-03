"""One-off source patch for tools/make_hd.py: HD block from tools/hd_block.js + wiring for chars, drivers, interiors."""
p = r'C:\Coding\borso-simulator\tools\make_hd.py'
s = open(p, encoding='utf-8').read()

a = s.index('HD_BLOCK = r"""')
b = s.index('"""\n', a + 20) + 4
s = s[:a] + "HD_BLOCK = open(os.path.join(ROOT, 'tools', 'hd_block.js'), encoding='utf-8').read() + '\\n'\n" + s[b:]

anchor = "s = rep(s, 'function makeCarMesh(type, color) {\\n'"
assert s.count(anchor) == 1, 'anchor'
extra = r'''s = rep(s, 'function makeChar(o) {\n', 'function makeCharProc(o) {\n')
s = rep(s, '    scene.add(this.mesh); cars.push(this);\n', '    scene.add(this.mesh); cars.push(this);\n    if (HD) hdAddDriver(this);\n')
s = rep(s, '    this.wheelRot += this.speed * 0.05; for (const w of this.wheels) w.rotation.x = this.wheelRot;\n',
        '    this.wheelRot += this.speed * 0.05; for (const w of this.wheels) w.rotation.x = this.wheelRot;\n    if (this.seatDriver) hdSeatUpdate(this);\n')
s = rep(s, "build: buildBar }", "build: buildBarHD }")
s = rep(s, "build: buildChiesa }", "build: buildChiesaHD }")
for k, fn in [('farmacia', 'buildFarmacia'), ('tabacchi', 'buildTabacchi'), ('pizzeria', 'buildPizzeria'), ('scuola', 'buildScuola'),
              ('alimentari', 'buildAlimentari'), ('cubamia', 'buildCubaMia'), ('malga', 'buildMalga')]:
    s = rep(s, 'build: ' + fn + ' }', "build: () => hdDressRoom(" + fn + "(), '" + k + "') }")
'''
s = s.replace(anchor, extra + anchor)
old_then = "spawnTrafficCar(false); GS.mode = 'title'; $('loading').classList.add('hidden'); $('title').classList.remove('hidden'); })"
assert s.count(old_then) == 1, 'then'
s = s.replace(old_then, "spawnTrafficCar(false); GS.mode = 'title'; $('loading').classList.add('hidden'); $('title').classList.remove('hidden'); loadHDInteriors(); })")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
