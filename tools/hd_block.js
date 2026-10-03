/* =====================================================================
   HD: mondo, veicoli, personaggi e interni costruiti in Blender
   (models/*.glb + textures/*.png) — inserito da tools/make_hd.py
   ===================================================================== */
// Sant'Eulalia: chiesa dell'asset church.glb, scalata x2.4 (navata + campanile sul retro), allineata a models/church_se.glb
function seChurch() {
  const y = H(170, -42) - 0.3;
  addCollider(164.5, -50.4, 175.5, -29.6, y + 16, 'church');
  addCollider(155.7, -51.1, 162.4, -44.9, y + 26, 'tower');
}

/* ---------- collisioni dei veicoli: capsula = segmento lungo l'asse + raggio pari a mezza larghezza ---------- */
const _cv = new THREE.Vector3();
function carSeg(c) { const f = c.fwd(), hl = Math.max(0, c.spec.len / 2 - c.hw); return [c.pos.x - f.x * hl, c.pos.z - f.z * hl, c.pos.x + f.x * hl, c.pos.z + f.z * hl]; }
function segClosest(s, px, pz) { const dx = s[2] - s[0], dz = s[3] - s[1], l2 = dx * dx + dz * dz || 1, t = clamp(((px - s[0]) * dx + (pz - s[1]) * dz) / l2, 0, 1); return [s[0] + dx * t, s[1] + dz * t]; }
function carPointDist(c, x, z) { const q = segClosest(carSeg(c), x, z), dx = x - q[0], dz = z - q[1]; return { d: Math.hypot(dx, dz), dx, dz }; }
function segCross(a, b) {
  const o = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const A = [a[0], a[1]], B = [a[2], a[3]], C = [b[0], b[1]], D = [b[2], b[3]];
  return o(A, B, C) * o(A, B, D) < 0 && o(C, D, A) * o(C, D, B) < 0;
}
function carCarDist(a, b) { // distanza tra le capsule e direzione da a verso b
  const s = carSeg(a), t = carSeg(b);
  if (segCross(s, t)) return { d: 0, dx: b.pos.x - a.pos.x, dz: b.pos.z - a.pos.z };
  let best = null;
  const tryP = (px, pz, seg, sg) => { const q = segClosest(seg, px, pz), dx = (px - q[0]) * sg, dz = (pz - q[1]) * sg, d = Math.hypot(dx, dz); if (!best || d < best.d) best = { d, dx, dz }; };
  tryP(s[0], s[1], t, -1); tryP(s[2], s[3], t, -1); tryP(t[0], t[1], s, 1); tryP(t[2], t[3], s, 1);
  if (best.d < 1e-4) { best.dx = b.pos.x - a.pos.x; best.dz = b.pos.z - a.pos.z; }
  return best;
}
function carCollideWorld(c) {
  const f = c.fwd(), hl = Math.max(0, c.spec.len / 2 - c.hw); let hit = false;
  for (let k = -1; k <= 1; k++) {
    _cv.set(c.pos.x + f.x * hl * k, 0, c.pos.z + f.z * hl * k); const ox = _cv.x, oz = _cv.z;
    if (collideCircle(_cv, c.hw, c.pos.y + 0.3)) { hit = true; c.pos.x += _cv.x - ox; c.pos.z += _cv.z - oz; }
  }
  return hit;
}

/* ---------- altezza del suolo uguale a quella disegnata (terreno a triangoli di world.glb, asfalto rialzato) ----------
   Stessa griglia e stessa diagonale di blender/build_world.py (terrain_grid/Tmesh/Hs): così ruote e piedi
   poggiano sull'asfalto e sul prato che si vedono, non sulla funzione H() liscia che sta qualche cm sotto. */
function hdGridLines(a, b, da, db, si, so, prio) {
  const reg = []; for (let v = a; v < da; v += so) reg.push(v); for (let v = da; v < db; v += si) reg.push(v); for (let v = db; v <= b + 1e-6; v += so) reg.push(v);
  const pr = [...new Set(prio.filter(p => p >= a && p <= b).concat([a, b]))].sort((x, y) => x - y), out = pr.slice();
  for (const v of reg) { let m = 1e9; for (const p of pr) m = Math.min(m, Math.abs(v - p)); if (m > 1.2) out.push(v); }
  return out.sort((x, y) => x - y);
}
function hdSurfaceInit() {
  if (HDM.surf) return;
  const H0 = H, px = [], pz = [];
  for (let i = 0; i <= 7; i++) px.push(-700 + 200 * i); for (let k = -11; k < 8; k++) px.push(42 * k); px.push(-480, 320);
  for (let j = 0; j <= 6; j++) pz.push(-780 + 200 * j); for (let k = -1; k < 9; k++) pz.push(31 * k); pz.push(-40);
  const XS = hdGridLines(-700, 700, -485, 330, 5, 20, px), ZS = hdGridLines(-780, 420, -420, 280, 5, 20, pz), nz = ZS.length;
  const HN = new Float32Array(XS.length * nz); for (let i = 0; i < XS.length; i++) for (let j = 0; j < nz; j++) HN[i * nz + j] = H0(XS[i], ZS[j]);
  const find = (A, v) => { let lo = 0, hi = A.length - 1; if (v <= A[0]) return 0; if (v >= A[hi]) return hi - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (A[m] > v) hi = m; else lo = m; } return lo; };
  const T = (x, z) => {
    const i = find(XS, x), j = find(ZS, z), x0 = XS[i], z0 = ZS[j], u = (x - x0) / (XS[i + 1] - x0), v = (z - z0) / (ZS[j + 1] - z0);
    const ha = HN[i * nz + j], hb = HN[i * nz + j + 1], hc = HN[(i + 1) * nz + j + 1], hd = HN[(i + 1) * nz + j];
    return v >= u ? ha + v * (hb - ha) + u * (hc - hb) : ha + u * (hd - ha) + v * (hc - hd);
  };
  // rialzo di strade e piazze (1 m per cella): asfalto = Hs + yo, banchina che scende di 7 cm, -1 = prato
  const GX0 = -490, GZ0 = -390, GW = 820, GD = 670, OFF = new Float32Array(GW * GD).fill(-1);
  const put = (x, z, v) => { const i = Math.round(x - GX0), j = Math.round(z - GZ0); if (i >= 0 && j >= 0 && i < GW && j < GD && v > OFF[j * GW + i]) OFF[j * GW + i] = v; };
  ROADS.forEach((r, ri) => {
    const d = r.dense, hw = r.w / 2, yo = r.yo + ri * 0.003;
    for (let k = 0; k < d.length - 1; k++) {
      const ax = d[k][0], az = d[k][1], bx = d[k + 1][0], bz = d[k + 1][1], dx = bx - ax, dz = bz - az, l2 = dx * dx + dz * dz || 1, m = hw + 0.9;
      for (let x = Math.floor(Math.min(ax, bx) - m); x <= Math.max(ax, bx) + m; x++) for (let z = Math.floor(Math.min(az, bz) - m); z <= Math.max(az, bz) + m; z++) {
        const t = clamp(((x - ax) * dx + (z - az) * dz) / l2, 0, 1), dd = Math.hypot(x - ax - dx * t, z - az - dz * t);
        if (dd <= m) put(x, z, dd <= hw ? yo : yo - 0.07 * (dd - hw) / 0.9);
      }
    }
  });
  for (const [cx, cz, w, dd, yo] of HDM.drapes) for (let x = Math.ceil(cx - w / 2); x <= cx + w / 2; x++) for (let z = Math.ceil(cz - dd / 2); z <= cz + dd / 2; z++) put(x, z, yo);
  HDM.surf = { H0, T, OFF };
  H = function (x, z) { // eslint-disable-line no-func-assign
    const i = Math.round(x - GX0), j = Math.round(z - GZ0), o = i >= 0 && j >= 0 && i < GW && j < GD ? OFF[j * GW + i] : -1, t = T(x, z);
    return o < 0 ? t : Math.max(H0(x, z), t) + o;
  };
}

/* ---------- traffico: agli incroci le auto svoltano su una curva di raccordo invece di fare inversione sul posto ---------- */
function hdLaneDir(L, s) { const a = lanePoint(L, s - 1, {}), b = lanePoint(L, s + 1, {}), l = Math.hypot(b.x - a.x, b.z - a.z) || 1; return { x: (b.x - a.x) / l, z: (b.z - a.z) / l }; }
function hdNearestS(L, x, z) { let bd = 1e9, bs = 0; for (let i = 0; i < L.pts.length; i++) { const d = Math.hypot(L.pts[i][0] - x, L.pts[i][1] - z); if (d < bd) { bd = d; bs = L.cum[i]; } } return { d: bd, s: bs }; }
function hdJunctions() {
  HDM.junc = new Map();
  for (const L of LANES) {
    const out = [], E = L.pts[L.pts.length - 1];
    for (const M of LANES) {
      if (M === L || M === L.pair) continue;
      const n = hdNearestS(M, E[0], E[1]); // la corsia finisce su un'altra strada: svolta obbligata a destra o a sinistra
      if (n.d < 8 && n.s + 7 < M.len - 6) out.push({ s: L.len - 7, to: M, ts: n.s + 7, end: true });
      if (M.road !== L.road) { // un'altra strada parte da qui: svolta facoltativa
        const S0 = M.pts[0], k = hdNearestS(L, S0[0], S0[1]);
        if (k.d < 8 && k.s > 12 && k.s < L.len - 12) out.push({ s: k.s - 7, to: M, ts: 7, end: false });
      }
    }
    HDM.junc.set(L, out);
  }
}
function hdTurn(c, L, s, M, ts, ctl) {
  const p0 = lanePoint(L, s, {}), p3 = lanePoint(M, ts, {}), d0 = hdLaneDir(L, s), d3 = hdLaneDir(M, ts);
  const k = ctl || Math.hypot(p3.x - p0.x, p3.z - p0.z) * 0.42;
  const P = [[p0.x, p0.z], [p0.x + d0.x * k, p0.z + d0.z * k], [p3.x - d3.x * k, p3.z - d3.z * k], [p3.x, p3.z]], pts = [];
  for (let i = 0; i <= 16; i++) {
    const t = i / 16, a = (1 - t) ** 3, b = 3 * (1 - t) ** 2 * t, cc = 3 * (1 - t) * t * t, d = t ** 3;
    pts.push([a * P[0][0] + b * P[1][0] + cc * P[2][0] + d * P[3][0], a * P[0][1] + b * P[1][1] + cc * P[2][1] + d * P[3][1]]);
  }
  const cum = [0]; for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  c.lane = { pts, cum, len: cum[cum.length - 1], conn: true, next: M, ns: ts, road: M.road, pair: M.pair };
  c.s = c._ps = Math.max(0, c.s - s);
}
function hdLaneStep(c, L) {
  const s0 = c._ps === undefined ? c.s : c._ps; c._ps = c.s;
  if (L.conn) { if (c.s >= L.len - 0.05) { c.lane = L.next; c.s = c._ps = L.ns; } return; }
  if (!HDM.junc) hdJunctions();
  const ex = HDM.junc.get(L) || [], ends = [];
  for (const e of ex) {
    if (e.end) { ends.push(e); continue; }
    if (s0 < e.s && c.s >= e.s && Math.random() < 0.35) { hdTurn(c, L, e.s, e.to, e.ts); return; }
  }
  if (ends.length) { if (c.s >= ends[0].s) { const e = pick(ends); hdTurn(c, L, e.s, e.to, e.ts); } return; }
  if (c.s < L.len - 3) return;
  // strada senza uscita (bordo della mappa, cima del Grappa): lontano dagli occhi si gira sul posto, vicino fa inversione
  const pp = playerPos();
  if (Math.hypot(c.pos.x - pp.x, c.pos.z - pp.z) > 90) {
    c.lane = L.pair; c.s = c._ps = 2; lanePoint(c.lane, 2, _lp); c.pos.x = _lp.x; c.pos.z = _lp.z;
    const q = lanePoint(c.lane, 5, {}); c.heading = Math.atan2(q.x - _lp.x, q.z - _lp.z);
  } else hdTurn(c, L, L.len - 3, L.pair, 3, 7);
}

/* ---------- colori e materiali ---------- */
function srgbFromLinear(v) { return v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055; }
function hdFixColors(geo) {
  // Blender esporta COLOR_0 in spazio lineare; il gioco lavora in sRGB come l'originale.
  const c = geo.attributes.color; if (!c || c.userData && c.userData.srgb) return;
  const a = c.array, n = c.count, is = c.itemSize, out = new Float32Array(n * 3);
  const k = a instanceof Uint8Array ? 1 / 255 : a instanceof Uint16Array ? 1 / 65535 : 1;
  for (let i = 0; i < n; i++) for (let j = 0; j < 3; j++) out[i * 3 + j] = srgbFromLinear(a[i * is + j] * k);
  const att = new THREE.BufferAttribute(out, 3); att.userData = { srgb: true }; geo.setAttribute('color', att);
}
// materiale di un asset (glTF PBR) -> Phong/Lambert come il resto del gioco
function hdAssetMat(m, geo) {
  if (m.map) m.map.encoding = THREE.LinearEncoding;
  if (geo && geo.attributes.color && !(geo.attributes.color.userData && geo.attributes.color.userData.srgb)) {
    // alcuni asset esportano COLOR_0 tutto nero (attributo vuoto): in quel caso va ignorato
    const a = geo.attributes.color.array, st = Math.max(1, Math.floor(a.length / 3000)); let sum = 0, n = 0;
    const k = a instanceof Uint8Array ? 1 / 255 : a instanceof Uint16Array ? 1 / 65535 : 1;
    for (let i = 0; i < a.length; i += st) { sum += a[i] * k; n++; }
    if (sum / n < 0.06) geo.deleteAttribute('color');
  }
  const vc = !!(geo && geo.attributes.color); if (vc) hdFixColors(geo);
  const paint = m.name === 'Paint', glass = m.name === 'Glass', metal = /^Metal/.test(m.name);
  return new THREE.MeshPhongMaterial({ name: m.name, map: m.map, color: m.color.clone().convertLinearToSRGB(), vertexColors: vc,
    shininess: paint ? 50 : glass ? 80 : metal ? 70 : 6, specular: paint ? 0x333333 : glass ? 0x666666 : metal ? 0x8a8070 : 0x0d0d0d,
    transparent: m.transparent || glass, opacity: glass ? 0.55 : m.opacity, side: m.side, alphaTest: m.alphaTest, depthWrite: glass ? false : m.depthWrite });
}
function hdPrepAsset(root, shadows = true) {
  root.traverse(o => {
    if (!o.isMesh) return;
    o.material = Array.isArray(o.material) ? o.material.map(m => hdAssetMat(m, o.geometry)) : hdAssetMat(o.material, o.geometry);
    o.castShadow = shadows && !LOWQ; o.receiveShadow = !LOWQ;
  });
  return root;
}

let HD_TEX = null;
function hdTextures() {
  if (HD_TEX) return HD_TEX;
  const texL = new THREE.TextureLoader(), aniso = Math.min(renderer.capabilities.getMaxAnisotropy(), LOWQ ? 4 : 8);
  const T = n => { const t = texL.load('textures/' + n + '.png'); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.flipY = false; t.anisotropy = aniso; return t; };
  HD_TEX = {}; ['grass', 'asphalt_main', 'asphalt_small', 'cobble', 'plaster', 'stone', 'roof', 'wood', 'detail', 'window', 'window_em', 'tile'].forEach(n => HD_TEX[n] = T(n));
  return HD_TEX;
}
function hdLoader() {
  if (HDM.gl) return HDM.gl;
  const draco = new THREE.DRACOLoader(); draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.4.1/');
  HDM.gl = new THREE.GLTFLoader(); HDM.gl.setDRACOLoader(draco);
  return HDM.gl;
}
function hdLoad(url, onProgress) { return new Promise(res => hdLoader().load(url, g => res(g), e => { if (onProgress && e.total) onProgress(e.loaded / e.total); }, err => { console.warn('HD: manca ' + url, err); res(null); })); }

/* ---------- caricamento: mondo + veicoli + personaggi (subito), interni (in sottofondo) ---------- */
function loadHD(onProgress) {
  hdSurfaceInit();
  const tx = hdTextures();
  const lam = o => new THREE.MeshLambertMaterial(Object.assign({ vertexColors: true }, o));
  const off = f => ({ polygonOffset: true, polygonOffsetFactor: f, polygonOffsetUnits: f });
  const mats = {
    M_Terrain: lam({ map: tx.grass }),
    M_RoadMain: lam(Object.assign({ map: tx.asphalt_main }, off(-3))),
    M_RoadSmall: lam(Object.assign({ map: tx.asphalt_small }, off(-3))),
    M_Cobble: lam(Object.assign({ map: tx.cobble }, off(-2))),
    M_Plaster: lam({ map: tx.plaster }), M_Stone: lam({ map: tx.stone }), M_Roof: lam({ map: tx.roof }),
    M_Wood: lam({ map: tx.wood }), M_Detail: lam({ map: tx.detail }),
    M_Window: lam({ map: tx.window, vertexColors: false }),
    M_WindowLit: lam({ map: tx.window, vertexColors: false, emissive: 0xffffff, emissiveMap: tx.window_em, emissiveIntensity: 0 }),
    M_Plain: lam({}), M_Foliage: lam({}),
    M_LampGlow: lam({ emissive: 0xffd28a, emissiveIntensity: 0 }),
    M_Glow: new THREE.MeshBasicMaterial({ vertexColors: true }),
  };
  HDM.mats = mats; HDM.winLit = mats.M_WindowLit; HDM.lamp = mats.M_LampGlow;
  const prog = { w: 0, other: 0 }; const tick = () => onProgress && onProgress(prog.w * 0.75 + prog.other * 0.25);
  const pWorld = hdLoad('models/world.glb', p => { prog.w = p; tick(); }).then(g => {
    if (!g) throw new Error('world.glb');
    g.scene.traverse(o => {
      if (!o.isMesh) return;
      hdFixColors(o.geometry);
      const pickM = m => mats[m.name] || m;
      o.material = Array.isArray(o.material) ? o.material.map(pickM) : pickM(o.material);
      const terrain = /^T_/.test(o.name);
      o.castShadow = !LOWQ && !terrain; o.receiveShadow = !LOWQ;
    });
    g.scene.updateMatrixWorld(true); g.scene.traverse(o => { o.matrixAutoUpdate = false; });
    world.add(g.scene); HDM.root = g.scene;
  });
  const parts = [['panda', 'models/panda.glb'], ['trattore', 'models/trattore.glb'], ['cinquecento', 'models/cinquecento.glb'], ['multipla', 'models/multipla.glb']].map(([k, u]) =>
    hdLoad(u).then(g => { if (g) HDM.cars[k] = hdPrepAsset(g.scene); }));
  parts.push(hdLoad('models/church_se.glb').then(g => { if (!g) return; hdPrepAsset(g.scene); g.scene.updateMatrixWorld(true); g.scene.traverse(o => { o.matrixAutoUpdate = false; }); world.add(g.scene); }));
  parts.push(hdLoad('models/chars.glb').then(g => { if (!g) { HDM.charFail = true; hdSkinPending(); return; } const P = {}; g.scene.traverse(o => { if (o.isMesh) P[o.name] = o.geometry; }); HDM.charParts = P; hdSkinPending(); }));
  parts.push(hdLoad('models/items.glb').then(g => { if (!g) return; hdPrepAsset(g.scene); HDM.items = {}; g.scene.traverse(o => { if (/^item_/.test(o.name) && !/^item_/.test(o.parent && o.parent.name || '')) HDM.items[o.name] = o; }); }));
  parts.push(hdLoad('models/sacrario.glb').then(g => { if (!g) return; hdSacrario(g.scene); }));
  let done = 0; parts.forEach(p => p.then(() => { done++; prog.other = done / parts.length; tick(); }));
  return Promise.all([pWorld, ...parts]);
}
// Sacrario del Monte Grappa, sulla vetta fuori dall'area di gioco: meno nebbia del resto, illuminato di notte
function hdSacrario(root) {
  const mat = new THREE.MeshLambertMaterial({ vertexColors: true, emissive: 0xfff2d8, emissiveIntensity: 0 });
  mat.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <fog_fragment>', '#ifdef USE_FOG\n  gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor, smoothstep(fogNear, fogFar, fogDepth) * 0.55);\n#endif'); };
  root.traverse(o => { if (!o.isMesh) return; hdFixColors(o.geometry); o.material = mat; o.castShadow = false; o.receiveShadow = false; });
  root.updateMatrixWorld(true); root.traverse(o => { o.matrixAutoUpdate = false; });
  world.add(root); HDM.sacrario = [mat];
}
// interni in sottofondo dopo il titolo: finché non arrivano si usano le stanze originali
function loadHDInteriors() {
  hdLoad('models/rooms.glb').then(g => {
    if (!g) return;
    const tx = hdTextures(), mats = {
      R_Wood: { map: tx.wood }, R_Floor: { map: tx.wood }, R_Plaster: { map: tx.plaster }, R_Stone: { map: tx.stone }, R_Tile: { map: tx.tile }, R_Plain: {},
    };
    g.scene.traverse(o => {
      if (!o.isMesh) return;
      hdFixColors(o.geometry);
      const conv = m => {
        if (m.name === 'R_Sky' || m.name === 'R_Bulb') return new THREE.MeshBasicMaterial({ vertexColors: true });
        if (m.name === 'R_Glass') return new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: 0.8 });
        return new THREE.MeshLambertMaterial(Object.assign({ vertexColors: true }, mats[m.name] || {}));
      };
      o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
    });
    HDM.rooms = {}; g.scene.traverse(o => { const m = /^room_([a-z]+)$/.exec(o.name); if (m) HDM.rooms[m[1]] = o; });
    if (HDM.rooms.osteria) hdDressRoom({ S: interior }, 'osteria');
    for (const k in ROOMS) if (k !== 'osteria' && HDM.rooms[k] && !ROOMS[k].hd && GS.inside !== ROOMS[k]) delete ROOMS[k];
  });
  hdLoad('models/room_chiesa.glb').then(g => { if (g) { HDM.roomChiesa = hdPrepAsset(g.scene, false); if (ROOMS.chiesa && GS.inside !== ROOMS.chiesa) delete ROOMS.chiesa; } });
  hdLoad('models/room_bar.glb').then(g => { if (g) { HDM.roomBar = hdPrepAsset(g.scene, false); if (ROOMS.bar && GS.inside !== ROOMS.bar) delete ROOMS.bar; } });
}

/* ---------- veicoli: modelli, colore, conducente seduto ---------- */
const HD_CAR_MODEL = { panda: 'panda', golf: 'panda', cinquecento: 'cinquecento', multipla: 'multipla', trattore: 'trattore' };
const HD_SEAT = { // [x, y, z, scala] del guidatore seduto (coordinate locali, avanti = +z, sinistra = +x); la testa resta sotto il tetto
  panda: [0.33, 0.09, -0.15, 0.72], golf: [0.33, 0.09, -0.15, 0.72], cinquecento: [0.27, 0.07, -0.25, 0.62], multipla: [0.36, 0.15, 0.0, 0.8], trattore: [0, 0.58, -0.5, 0.85],
};
function hdCar(type, color) {
  const t = HDM.cars[HD_CAR_MODEL[type]]; if (!t) return null;
  const g = new THREE.Group(), m = t.clone(true), wheels = []; g.add(m);
  m.traverse(o => {
    if (o.isMesh && o.material.name === 'Paint') { o.material = o.material.clone(); o.material.color.set(color); }
    if (/^wheel/.test(o.name)) wheels.push(o);
  });
  return { g, wheels };
}
function hdSeatPose(c) {
  c.legL.rotation.x = c.legR.rotation.x = -1.5; c.body.position.y = -0.42;
  c.armL.rotation.x = c.armR.rotation.x = -1.05; c.armL.rotation.z = 0.12; c.armR.rotation.z = -0.12;
}
function hdAddDriver(car) {
  const seat = HD_SEAT[car.type]; if (!seat || !HDM.cars[HD_CAR_MODEL[car.type]]) return;
  const mk = preset => { const c = makeChar(preset); hdSeatPose(c); c.root.position.set(seat[0], seat[1], seat[2]); c.root.scale.setScalar(seat[3]); car.mesh.add(c.root); return c; };
  const farmer = car.type === 'trattore' ? Object.assign(vecioPreset(), { hat: 'cap', hatColor: pick([0x2f5d3a, 0xc8302a, 0x3a3a3a]), vest: undefined, shirt: pick([0x3a5a8a, 0x6a5a4a, 0x8a3a2a]) })
    : pick([vecioPreset, giovanePreset, signoraPreset])();
  car.seatDriver = mk(farmer);
  car.seatBepi = mk(P.bepi);
  hdSeatUpdate(car);
}
function hdSeatUpdate(car) {
  const mine = player.inCar === car;
  car.seatDriver.root.visible = car.driver && !mine;
  car.seatBepi.root.visible = mine && !player.fps;
}

/* ---------- personaggi: parti modellate in Blender (models/chars.glb) ---------- */
const CHAR_SLOTS = ['skin', 'shirt', 'sleeve', 'pants', 'shoes', 'hair', 'hat', 'vest', 'white', 'dark', 'skirt', 'gold', 'bag', 'sack', 'apron', 'glasses', 'sole', 'mouth', 'balaclava', 'belt', 'iris'];
function charPalette(o) {
  return { skin: o.skin || 0xe0b48f, shirt: o.shirt, sleeve: o.sleeve || o.shirt, pants: o.pants, shoes: o.shoes || 0x2a2a2a, hair: o.hair || 0x3a2a1a, hat: o.hatColor || 0x333333,
    vest: o.vest || o.shirt, white: 0xf4f4f0, dark: 0x161616, skirt: o.skirt || o.pants, gold: 0xf3c742, bag: o.borselloColor || 0x1a1a1a, sack: 0xc9b48a, apron: 0xf6f6f2,
    glasses: 0x111111, sole: o.bigShoes ? 0xf6f6f6 : 0x3a3330, mouth: 0x8a4038, balaclava: 0x151515, belt: 0x2a1e16, iris: 0x4a3a2a };
}
function charPartList(o) {
  const head = ['head'];
  if (o.balaclava) head.push('balaclava');
  else {
    switch (o.hat) {
      case 'cap': head.push('hat_cap', 'hair_short'); break;
      case 'capBack': head.push('hat_capBack', 'hair_short'); break;
      case 'coppola': head.push('hat_coppola', 'hair_bald'); break;
      case 'scarf': head.push('hat_scarf'); break;
      case 'helmet': head.push('hat_helmet', 'hair_short'); break;
      case 'tuft': head.push('hair_tuft'); break;
      case 'hair': head.push(o.skirt ? 'hair_long' : 'hair_short'); break;
      case 'beanie': head.push('hat_beanie', 'hair_short'); break;
      default: head.push('hair_bald');
    }
    if (o.mustache) head.push('mustache');
    if (o.beard) head.push('beard');
    if (o.glasses) head.push('glasses');
  }
  const body = [o.stripes ? 'torso_track' : 'torso', 'neck'];
  if (o.stripes) body.push('torsostripes');
  if (o.vest) body.push('vest');
  if (o.apron) body.push('apron');
  if (o.chain) body.push('chain');
  if (o.borsello) body.push('borsello');
  if (o.sack) body.push('sack');
  if (o.skirt) body.push('skirt');
  const leg = s => [(o.skirt ? 'stocking_' : 'leg_') + s, (o.bigShoes ? 'bigshoe_' : 'shoe_') + s].concat(o.stripes ? ['legstripe_' + s] : []);
  const arm = s => ['arm_' + s, 'hand_' + s].concat(o.stripes ? ['armstripe_' + s] : []);
  return { head, body, legL: leg('L'), legR: leg('R'), armL: arm('L'), armR: arm('R') };
}
/* ---------- oggetti sacri della quest di Binea (models/items.glb) ---------- */
// [modello, misura nel mondo (m, lato più lungo), misura sull'altare]
const HD_ITEM = { campanello: ['item_campanello', 0.95, 0.24], turibolo: ['item_turibolo', 1.3, 0.62], madonna: ['item_croce', 1.2, 0.5], candelabro: ['item_calice', 0.95, 0.27], libro: ['item_bibbia', 0.95, 0.3] };
function hdItemModel(id, size) {
  const e = HD_ITEM[id], src = e && HDM.items && HDM.items[e[0]]; if (!src) return null;
  if (!src.userData.box) src.userData.box = new THREE.Box3().setFromObject(src);
  const b = src.userData.box, sz = b.getSize(new THREE.Vector3()), k = size / Math.max(sz.x, sz.y, sz.z);
  const m = src.clone(true); m.scale.setScalar(k); m.position.set(-(b.min.x + b.max.x) / 2 * k, -b.min.y * k, -(b.min.z + b.max.z) / 2 * k);
  const g = new THREE.Group(); g.add(m); return g;
}
const HD_BEAM = new THREE.MeshBasicMaterial({ color: 0xffd86a, transparent: true, opacity: 0.16, depthWrite: false, blending: THREE.AdditiveBlending });
function hdItemMesh(id, gold) {
  const m = HD_ITEM[id] && hdItemModel(id, HD_ITEM[id][1]); if (!m) return makeItemMesh(gold);
  const g = new THREE.Group(); m.position.y = -0.55; g.add(m);
  const r = new THREE.Mesh(new THREE.TorusGeometry(0.75, 0.035, 6, 28), new THREE.MeshBasicMaterial({ color: 0xffe9a8 })); r.rotation.x = Math.PI / 2; r.position.y = -0.75; g.add(r);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.4, 26, 10, 1, true), HD_BEAM); beam.position.y = 12.5; g.add(beam); // si vede da lontano
  return g;
}
function hdItemCollected(id) { if (id === 'libro' && ROOMS.bar && ROOMS.bar.bible) ROOMS.bar.bible.visible = false; }

/* ---------- interni ---------- */
// stanze originali: le primitive statiche vengono nascoste e sostituite dalla versione Blender (rooms.glb)
function hdDressRoom(R, key) {
  const src = HDM.rooms && HDM.rooms[key]; if (!src) return R;
  const dyn = new Set([R.ball, ...(R.tiles || []), doorPivot, bottle1803, interior.userData.flame, R.outPlane, walkGroup, cineGroup].filter(Boolean));
  if (R.slots) Object.values(R.slots).forEach(s => dyn.add(s));
  const walk = o => {
    if (dyn.has(o) || (o.userData && o.userData.isChar)) return;
    if (o.isMesh && !o.material.isMeshBasicMaterial && !(o.material.map && o.material.map.isCanvasTexture)) o.visible = false;
    for (const ch of o.children) walk(ch);
  };
  walk(R.S);
  R.S.add(src.clone(true)); R.hd = true;
  return R;
}
// stanza senza geometria procedurale (la grafica arriva da un .glb)
function hdRoom(o, model) {
  const S = new THREE.Scene(); S.background = new THREE.Color(o.bg || 0x15100c);
  const R = { S, w: o.w, d: o.d, h: o.h, boxes: [], hots: [], npcs: [], name: o.name, anim: [], hd: true };
  S.add(new THREE.HemisphereLight(o.sky || 0xfff2dc, 0x3a3020, o.hemi || 0.62)); S.add(new THREE.AmbientLight(0xffffff, o.amb || 0.22));
  (o.lights || []).forEach(l => { const p = new THREE.PointLight(l[3] || 0xffe2b8, l[4] || 0.9, l[5] || 14, 1.4); p.position.set(l[0], l[1], l[2]); S.add(p); R.anim.push(p); });
  R.B = (x0, x1, z0, z1, top = 2.5) => R.boxes.push({ x0, x1, z0, z1, top });
  R.sign = (lines, opt, x, y, z, ry, w, h) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: signTex('shop', lines, opt) })); m.position.set(x, y, z); m.rotation.y = ry; S.add(m); return m; };
  R.npc = (name, preset, x, z, yaw, opt) => rNPC(R, name, preset, x, z, yaw, opt);
  R.hot = (x, z, label, act, r = 1.5, cond) => { const h = { x, z, label, act, r, cond }; R.hots.push(h); return h; };
  R.spawn = { x: 0, z: o.d / 2 - 1.3 };
  if (o.door !== false) { const door = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 2.5), new THREE.MeshBasicMaterial({ color: 0xcfe4f4 })); door.position.set(0, 1.25, o.d / 2 - 0.02); door.rotation.y = Math.PI; S.add(door); R.outPlane = door; }
  S.add(model.clone(true));
  return R;
}
// Chiesa di Semonzo: interno dall'asset old_church (navata gotica 40 m), panche church_bench, croce, Graal e Bibbia
function buildChiesaHD() {
  if (!HDM.roomChiesa) return buildChiesa();
  // door: false -> la porta del modello è a z=19.45, l'uscita cade davanti
  const R = hdRoom({ name: 'Chiesa di Semonzo', w: 23.3, d: 38.0, h: 18, door: false, bg: 0x0c0a0e, hemi: 0.55, amb: 0.3, sky: 0xfff0d8,
    lights: [[0, 9, 2, 0xfff0d0, 1.0, 30], [0, 8, -11, 0xffe8c0, 1.2, 22], [0, 7, 14, 0xfff0d8, 0.8, 22], [-8, 5, -4, 0xffd8a0, 0.5, 12], [8, 5, -4, 0xffd8a0, 0.5, 12]] }, HDM.roomChiesa);
  for (const z of [19.2, 12.3, 5.4, -1.5, -8.55]) for (const x of [-5.8, 5.8]) R.B(x - 0.75, x + 0.75, z - 0.75, z + 0.75, 18); // colonne
  R.B(-4.9, -0.75, -3.65, 6.45, 1.0); R.B(0.75, 4.9, -3.65, 6.45, 1.0); // panche
  R.B(-3.6, 3.6, -14.1, -6.9, 1.2); // presbiterio e altare
  R.B(-11.65, -7.2, -20.2, -15.2, 18); R.B(7.2, 11.65, -20.2, -15.2, 18); // abside
  R.B(7.9, 10.1, -2.7, -1.3, 2.6); R.B(-9.75, -8.25, -6.35, -5.65, 1.0); // confessionale, lumini
  R.slots = {}; for (const k in ALTAR_SLOTS) { // gli oggetti ritrovati tornano sull'altare
    const [x, c] = ALTAR_SLOTS[k]; let m = hdItemModel(k, HD_ITEM[k][2]);
    if (m) { m.position.set(x * 1.15, 1.115, -9.95); if (k === 'libro') m.rotation.y = 0.35; } else { m = new THREE.Mesh(bxg(0.22, 0.3, 0.22), lm(c)); m.position.set(x * 1.1, 1.27, -9.95); }
    m.visible = false; R.S.add(m); R.slots[k] = m;
  }
  const lum = new THREE.PointLight(0xffa040, 0.7, 4, 1.6); lum.position.set(-9, 1.4, -6); R.S.add(lum);
  for (let i = 0; i < 10; i++) { const f = new THREE.Mesh(bxg(0.03, 0.06, 0.03), new THREE.MeshBasicMaterial({ color: 0xffb040 })); f.position.set(-9.55 + (i % 5) * 0.27, 1.12, -6.15 + Math.floor(i / 5) * 0.3); R.S.add(f); }
  R.npc('Don Gastone', PR.don, 0, -6.2, 0, { lines: ['Benvenuto, figliolo. Il Vescovo arriva domenica. Prega con me. O almeno spazza.', 'Binea comanda. Io benedico. Funziona così da trent\'anni.'], noFace: true });
  R.kidNPC = [];
  [[-1.6, -3.2], [1.6, -3.2], [-3.8, -3.2], [3.8, -3.2], [-1.6, -2.05]].forEach(([x, z]) => { const n = R.npc('Ragazzo', kidPreset(), x, z, Math.PI, { sit: true, lines: ['Binea ci guarda...', 'Shhh!', 'Quando finisce?'] }); n.c.root.rotation.y = Math.PI; R.kidNPC.push(n); });
  R.hot(0, -5.0, 'Parla con Don Gastone', () => talk([{ w: 'Don Gastone', t: pick(['Il Signore vede tutto, Bepi. Anche quando tiri le ciabatte. Però ride.', 'Binea? È in sagrestia a ordinare le candele. In ordine alfabetico.', 'I maranza rieducati non sono peccato. Ho controllato.']) }]), 1.8);
  R.hot(-9, -4.9, 'Accendi un lumino (1 schei)', () => { if (GS.money < 1) { toast('Serve almeno 1 schei.'); return; } GS.money--; heal(10, '🕯️ Lumino acceso. L\'anima si scalda: +10 salute.'); sfx('pickup'); }, 1.4);
  R.hot(9, -0.6, 'Confessati', () => talk([{ w: 'Don Gastone', t: `Quanti maranza hai rieducato? ${GS.kills}? Tre Ave Maria e un\'ombra. L\'ombra la offri tu.` }]), 1.4);
  R.onEnter = () => { for (const k in R.slots) R.slots[k].visible = GS.q.binea.items.includes(k) && GS.q.binea.s >= 2; const n = Object.values(GS.q.binea.kids).filter(v => v === 2).length; R.kidNPC.forEach((k, i) => { k.show = () => i < n; }); };
  return R;
}
// Bar Sport: interno dall'asset old_bar + biliardino modellato in Blender
function buildBarHD() {
  if (!HDM.roomBar) return buildBar();
  const R = hdRoom({ name: 'Bar Sport', w: 28.82, d: 10.9, h: 3.9, bg: 0x1a120c, hemi: 0.6, amb: 0.3,
    lights: [[4, 3.3, -1.5, 0xffe2b8, 1.0, 12], [0, 3.3, 3, 0xffe2b8, 0.9, 10], [9, 3.3, 1, 0xffe2b8, 0.8, 10], [-3, 3.2, 2, 0xffd8a8, 0.6, 8]] }, HDM.roomBar);
  R.B(-14.41, -4.72, -5.45, 5.45, 4); R.B(6.1, 14.41, 2.1, 5.45, 4); // fuori dalla sala
  R.B(-0.6, 9.1, -1.71, -0.79, 1.1); R.B(-0.6, 0.55, -5.0, -0.79, 1.1); R.B(9.1, 10.5, -3.7, -1.0, 1.1); // bancone a L
  R.B(-4.72, -3.3, 1.1, 2.1, 1.8); R.B(-4.72, -3.6, -1.2, -0.2, 1.6); // cabinato, juke-box
  for (const [x, z] of [[0.9, 3.2], [-3.05, 4.2], [4.0, 4.2]]) R.B(x - 0.55, x + 0.55, z - 0.55, z + 0.55, 0.8); // tavoli
  R.B(8.6, 10.0, 0.9, 1.7, 0.9); // biliardino
  R.sign(['FORZA BORSO', 'anche quando perdiamo (sempre)'], { bg: '#a8202a', fg: '#ffffff', border: '#ffffff', W: 512, H: 160 }, -4.66, 2.4, 3.4, Math.PI / 2, 2.4, 0.74);
  R.sign(['BORSO CALCIO 0', 'SAN ZENONE 7'], { bg: '#1a3a1a', fg: '#ffffff', W: 512, H: 160 }, -4.66, 2.4, -2.9, Math.PI / 2, 1.3, 0.75);
  R.npc('Gianni', PR.gianni, 4, -2.6, 0, { lines: ['Spritz? Caffè corretto? A ste ore xe uguale.', 'Ghe go el biliardino rotto da trent\'ani. Xe parte del fascino.'], noFace: true });
  R.npc('Mattia', kidPreset(), 9.3, 2.4, Math.PI, { id: 'kid_mattia', show: () => GS.q.binea.s === 2 && !GS.q.binea.kids.mattia, lines: ['Ancora una partita!'], talk: () => kidTalk('mattia') });
  R.npc('Ugo', vecioPreset(), 4.75, 4.2, -Math.PI / 2, { sit: true, lines: ['Ai mii tempi el Borso el vinceva. Ma ai mii tempi i gera tuti morti de fame, quindi i coreva.'] });
  R.hot(4, -0.2, 'Bancone: parla con Gianni', barShop, 1.7);
  R.hot(9.3, 2.3, 'Gioca a biliardino (2 schei)', () => { if (GS.money < 2) { toast('Servono 2 schei.'); return; } GS.money -= 2; if (Math.random() < 0.45) { GS.money += 5; toast('⚽ Gol del portiere! Vinci 5 schei. Ugo grida «roba da Champions».'); } else toast('⚽ Hai perso 10 a 2. Contro te stesso. Il biliardino ha questo potere.'); sfx('thud'); }, 1.3, () => !(GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro')));
  R.hot(9.3, 2.3, 'Prendi la Bibbia sotto il biliardino', () => collectBinea('libro'), 1.4, () => GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro'));
  R.bible = hdItemModel('libro', 0.3); if (R.bible) { R.bible.position.set(9.0, 0.005, 1.45); R.bible.rotation.y = 0.6; R.S.add(R.bible); }
  R.onEnter = () => { if (R.bible) R.bible.visible = GS.q.binea.s === 1 && !GS.q.binea.items.includes('libro'); };
  return R;
}
