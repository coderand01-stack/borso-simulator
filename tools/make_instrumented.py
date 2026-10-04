"""Builds tools/instrumented.html: the original game with probes that record every
world-building call (houses, trees, signs, loose primitives...) and POST the layout
to the dev server as tools/out/layout.json."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# parte dalla versione HD (generata da tools/make_hd.py) così il layout segue le stesse regole del gioco HD
src = open(os.path.join(ROOT, 'docs', 'index.html'), encoding='utf-8').read()

HOOK = r"""
/* ==== LAYOUT PROBE (instrumented build only) ==== */
window.__L = { top: [] };
const __stack = [];
const __GN = new Map([[G.box, 'box'], [G.cyl, 'cyl'], [G.cyl6, 'cyl6'], [G.cone8, 'cone8'], [G.sph, 'sph'], [G.sph1, 'sph1'], [G.pyr, 'pyr'], [G.prism, 'prism']]);
function __ser(v) {
  if (v && v.isTexture) return { tex: v.__spec || null };
  if (Array.isArray(v)) return v.map(__ser);
  if (v && typeof v === 'object') { const o = {}; for (const k in v) o[k] = __ser(v[k]); return o; }
  return v;
}
function __wrap(name, fn) {
  return function (...a) {
    const rec = { fn: name, args: __ser(a), parts: [] };
    (__stack.length ? __stack[__stack.length - 1].parts : __L.top).push(rec);
    __stack.push(rec);
    try { const r = fn.apply(this, a); if (name === 'placeHouse') rec.ret = { door: r.door, top: r.top, family: r.family, town: r.town }; if (name === 'church') rec.ret = { clock: r.clockPos.toArray() }; return r; }
    finally { __stack.pop(); }
  };
}
{ const _mc = makeChar; makeChar = function (o) { const c = _mc(o); c.root.userData.isChar = true; return c; }; }
{ const _st = signTex; signTex = function (kind, lines, opt) { const t = _st(kind, lines, opt); t.__spec = { kind, lines, opt: opt || {} }; return t; }; }
placeHouse = __wrap('placeHouse', placeHouse); tree = __wrap('tree', tree); lamp = __wrap('lamp', lamp); bench = __wrap('bench', bench);
church = __wrap('church', church); placeSign = __wrap('placeSign', placeSign); wallSign = __wrap('wallSign', wallSign); drapedArea = __wrap('drapedArea', drapedArea);
{ const _add = Batch.add; Batch.add = function (geo, key, m, color) {
    let g = __GN.get(geo), p;
    if (!g) { g = geo.type; p = geo.parameters ? { ...geo.parameters } : null; }
    const rec = { prim: g, key, m: Array.from(m.elements).map(v => Math.round(v * 1e5) / 1e5), c: color === undefined ? 0xffffff : color };
    if (p) rec.p = p;
    (__stack.length ? __stack[__stack.length - 1].parts : __L.top).push(rec);
    return _add.call(this, geo, key, m, color);
  }; }
"""

DUMP = r"""
<script>
(function () {
  function dump() {
    const L = window.__L;
    L.roads = ROADS.map(r => ({ name: r.name, w: r.w, yo: r.yo, main: !!r.main, cars: !!r.cars, pts: r.pts, dense: r.dense }));
    L.houses = houses.map(h => ({ x: h.x, z: h.z, door: h.door, fx: h.fx, fz: h.fz, top: h.top, town: h.town, family: h.family }));
    L.colliders = colliders.map(c => [c.x0, c.z0, c.x1, c.z1, c.top, c.tag || '']);
    L.reserved = reserved; L.LOC = LOC; L.WB = WB; L.GRAPPA_T = GRAPPA_T; L.DECK_H = DECK_H;
    L.clocks = campanileClocks.map(p => p.toArray());
    const hs = []; for (let z = -780; z <= 420; z += 20) for (let x = -700; x <= 700; x += 20) hs.push([x, z, (HDM.surf ? HDM.surf.H0 : H)(x, z)]); // H() analitica, non quella del terreno disegnato
    L.hsamples = hs;
    fetch('/save?name=layout.json', { method: 'POST', body: JSON.stringify(L) }).then(r => r.text()).then(t => { document.title = 'DUMP ' + t; dumpRooms(); });
  }
  function dumpRooms() {
    const out = {};
    const texName = m => { if (!m || !m.map) return null; const img = m.map.image; for (const k of ['plank', 'tile', 'stone', 'plaster', 'cobble', 'grass']) if (TEX[k] && TEX[k].image === img) return k; return 'canvas'; };
    const grab = (key, root, R, dyn) => {
      const prims = [], lights = [];
      root.updateMatrixWorld(true);
      const walk = o => {
        if (o.userData && o.userData.isChar) return;
        if (dyn.has(o)) return;
        if (o.isPointLight) lights.push([o.position.x, o.position.y, o.position.z, o.color.getHex(), o.intensity, o.distance]);
        if (o.isMesh) {
          const g = o.geometry, m = o.material;
          prims.push({ t: g.type, p: g.parameters ? { ...g.parameters } : null, m: o.matrixWorld.elements.map(v => Math.round(v * 1e5) / 1e5),
            c: m.color ? m.color.getHex() : 0xffffff, basic: !!m.isMeshBasicMaterial, tex: texName(m), op: m.opacity, em: m.emissive ? m.emissive.getHex() : 0 });
        }
        for (const ch of o.children) walk(ch);
      };
      walk(root);
      out[key] = { w: R.w, d: R.d, h: R.h, prims, lights };
    };
    for (const key in INTERIORS) {
      if (key === 'chiesa' || key === 'bar') continue;
      const R = INTERIORS[key].build();
      const dyn = new Set([R.ball, ...(R.tiles || []), doorPivot, bottle1803, interior.userData.flame, R.outPlane, walkGroup, cineGroup].filter(Boolean));
      if (R.slots) Object.values(R.slots).forEach(s => dyn.add(s));
      grab(key, R.S, R, dyn);
    }
    fetch('/save?name=rooms.json', { method: 'POST', body: JSON.stringify(out) }).then(() => { document.title += ' ROOMS'; });
  }
  if (document.readyState === 'complete') dump(); else addEventListener('load', () => setTimeout(dump, 300));
})();
</script>
</body>"""

out = src.replace('const LOWQ = IS_TOUCH;', 'const LOWQ = false;', 1)
anchor = 'let campanileClocks = [];'
assert anchor in out
out = out.replace(anchor, HOOK + anchor, 1)
idx = out.rfind('</body>')
out = out[:idx] + DUMP + out[idx + len('</body>'):]
open(os.path.join(ROOT, 'tools', 'instrumented.html'), 'w', encoding='utf-8').write(out)
print('ok', len(out))
