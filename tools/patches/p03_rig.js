/* ---------- scheletro: ossa al posto dei gruppi rigidi, mesh unica con skinning ----------
   Le ossa hanno gli stessi nomi e pivot dei vecchi gruppi (body, legL, armR, head, hand...), quindi il codice
   del gioco che le ruota non cambia; in più ci sono ginocchia, caviglie, gomiti, polsi e busto, animati in hdPose(). */
const RIG = [ // nome, padre, posizione rispetto al padre (a riposo nessuna rotazione)
  ['body', null, 0, 0, 0], ['hip', 'body', 0, 0.92, 0],
  ['legL', 'hip', -0.13, 0, 0], ['shinL', 'legL', 0, -0.44, 0], ['footL', 'shinL', 0, -0.38, 0],
  ['legR', 'hip', 0.13, 0, 0], ['shinR', 'legR', 0, -0.44, 0], ['footR', 'shinR', 0, -0.38, 0],
  ['chest', 'body', 0, 1.08, 0], ['head', 'chest', 0, 0.52, 0],
  ['armL', 'chest', -0.36, 0.47, 0], ['foreL', 'armL', 0, -0.29, 0], ['handL', 'foreL', 0, -0.31, 0],
  ['armR', 'chest', 0.36, 0.47, 0], ['foreR', 'armR', 0, -0.29, 0], ['handR', 'foreR', 0, -0.31, 0],
];
const RIG_I = {}, RIG_ABS = {};
RIG.forEach(([n, p, x, y, z], i) => { RIG_I[n] = i; const q = p ? RIG_ABS[p] : [0, 0, 0]; RIG_ABS[n] = [q[0] + x, q[1] + y, q[2] + z]; });
const RIG_INV = RIG.map(([n]) => new THREE.Matrix4().makeTranslation(-RIG_ABS[n][0], -RIG_ABS[n][1], -RIG_ABS[n][2]));
const RIG_GROUP_OFF = { body: [0, 0, 0], head: [0, 1.6, 0], legL: [-0.13, 0.92, 0], legR: [0.13, 0.92, 0], armL: [-0.36, 1.55, 0], armR: [0.36, 1.55, 0] };
const ss01 = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
// pesi dello skinning [osso, peso, osso, peso], dalla parte e dall'altezza nello spazio del corpo
function rigWeights(k, name, y) {
  if (k === 'head') return [RIG_I.head, 1, 0, 0];
  if (k === 'body') { const t = ss01(1.0, 1.16, y); return [RIG_I.chest, t, RIG_I.hip, 1 - t]; }
  const s = k.slice(-1);
  if (k[0] === 'l') { if (/shoe/.test(name)) return [RIG_I['foot' + s], 1, 0, 0]; const t = ss01(0.42, 0.56, y); return [RIG_I['leg' + s], t, RIG_I['shin' + s], 1 - t]; }
  if (/^hand/.test(name)) return [RIG_I['hand' + s], 1, 0, 0];
  const t = ss01(1.2, 1.33, y); return [RIG_I['arm' + s], t, RIG_I['fore' + s], 1 - t];
}
function hdRig(o) {
  const root = new THREE.Group(), c = { root }, bones = [];
  for (const [n, p, x, y, z] of RIG) { const b = new THREE.Bone(); b.name = n; b.position.set(x, y, z); (p ? c[p] : root).add(b); c[n] = b; bones.push(b); }
  c.body.scale.setScalar(o.scale || 1);
  c.hand = new THREE.Group(); c.hand.position.set(0, -0.39, 0.05); c.foreR.add(c.hand); // attacco delle armi
  c.skeleton = new THREE.Skeleton(bones, RIG_INV);
  return c;
}
const _hdPc = new THREE.Color(), HD_PART_NI = {};
function hdMergeSkinned(L, pal) {
  const P = HDM.charParts, list = [];
  for (const k in L) for (const n of L[k]) { const g = P[n]; if (!g) continue; list.push([k, n, HD_PART_NI[n] || (HD_PART_NI[n] = g.index ? g.toNonIndexed() : g)]); }
  let n = 0; list.forEach(e => n += e[2].attributes.position.count);
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), col = new Float32Array(n * 3), si = new Uint16Array(n * 4), sw = new Float32Array(n * 4); let o = 0;
  for (const [k, name, g] of list) {
    const p = g.attributes.position, nm = g.attributes.normal, uv = g.attributes.uv, off = RIG_GROUP_OFF[k];
    for (let i = 0; i < p.count; i++, o++) {
      const y = p.getY(i) + off[1];
      pos[o * 3] = p.getX(i) + off[0]; pos[o * 3 + 1] = y; pos[o * 3 + 2] = p.getZ(i) + off[2];
      nor[o * 3] = nm.getX(i); nor[o * 3 + 1] = nm.getY(i); nor[o * 3 + 2] = nm.getZ(i);
      const slot = CHAR_SLOTS[Math.floor(uv.getX(i))] || 'skin', kk = 1 - uv.getY(i); // glTF capovolge la V
      _hdPc.setHex(pal[slot] === undefined ? 0xff00ff : pal[slot]);
      col[o * 3] = Math.min(1, _hdPc.r * kk); col[o * 3 + 1] = Math.min(1, _hdPc.g * kk); col[o * 3 + 2] = Math.min(1, _hdPc.b * kk);
      const w = rigWeights(k, name, y); si[o * 4] = w[0]; sw[o * 4] = w[1]; si[o * 4 + 1] = w[2]; sw[o * 4 + 1] = w[3];
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3)); geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  geo.setAttribute('skinIndex', new THREE.BufferAttribute(si, 4)); geo.setAttribute('skinWeight', new THREE.BufferAttribute(sw, 4));
  geo.computeBoundingSphere(); geo.boundingSphere.radius += 0.3;
  return geo;
}
const HD_CHAR_MAT = new THREE.MeshLambertMaterial({ vertexColors: true, skinning: true });
HDM.live = new Set(); HDM.frame = 0;
function hdSkin(c) {
  const m = new THREE.SkinnedMesh(hdMergeSkinned(charPartList(c.preset), charPalette(c.preset)), HD_CHAR_MAT);
  m.castShadow = !LOWQ; c.root.add(m); m.bind(c.skeleton, new THREE.Matrix4()); c.torso = m;
  m.onBeforeRender = () => { c._seen = HDM.frame; if (!c._on) { c._on = true; HDM.live.add(c); } };
}
// se chars.glb non arriva: i cubi del personaggio originale, appesi alle ossa
function hdProcParts(c) {
  const p = makeCharProc(c.preset);
  for (const k of ['body', 'head', 'legL', 'legR', 'armL', 'armR']) for (const ch of p[k].children.slice()) if (ch.isMesh) c[k].add(ch);
}
function hdSkinPending() { for (const c of HDM.pendingChars) HDM.charParts ? hdSkin(c) : hdProcParts(c); HDM.pendingChars.length = 0; }
function makeChar(o) {
  const c = hdRig(o); c.preset = o; c.root.userData.isChar = true;
  if (HDM.charParts) hdSkin(c); else if (HDM.charFail) hdProcParts(c); else HDM.pendingChars.push(c);
  return c;
}
// animazione secondaria, subito prima del render. Il gioco continua a muovere anche e spalle come prima;
// qui si ammorbidiscono i cambi di posa e si piegano ginocchia, caviglie, gomiti, busto e testa.
function hdPose(c, dt, kS, kJ, t) {
  let s = c._a;
  if (!s || HDM.frame - c._last > 3) s = c._a = { v: {}, knee: [0.05, 0.05], fore: [0.18, 0.18], pt: [c.legL.rotation.x, c.legR.rotation.x], lean: 0, px: c.root.position.x, pz: c.root.position.z, ph: s ? s.ph : Math.random() * 6 };
  c._last = HDM.frame;
  const sm = (ob, ax, key) => { const tg = ob.rotation[ax]; let v = s.v[key]; v = v === undefined ? tg : v + (tg - v) * kS; ob.rotation[ax] = v; s.v[key] = v; return v; };
  const tL = sm(c.legL, 'x', 'lx'), tR = sm(c.legR, 'x', 'rx'), aL = sm(c.armL, 'x', 'alx'), aR = sm(c.armR, 'x', 'arx');
  sm(c.armL, 'z', 'alz'); sm(c.armR, 'z', 'arz');
  const legs = [[tL, c.shinL, c.footL], [tR, c.shinR, c.footR]];
  for (let i = 0; i < 2; i++) {
    const [th, shin, foot] = legs[i], vel = (th - s.pt[i]) / dt; s.pt[i] = th;
    let k = 0.05 + clamp(-vel * 0.17, 0, 1.15);        // il ginocchio si piega quando la gamba va avanti
    if (th < -0.9) k = Math.max(k, Math.min(1.6, -th)); // seduto
    s.knee[i] += (k - s.knee[i]) * kJ;
    shin.rotation.x = s.knee[i]; foot.rotation.x = clamp(-(th + s.knee[i]) * 0.6, -0.6, 0.6);
  }
  const arms = [[aL, c.foreL], [aR, c.foreR]];
  for (let i = 0; i < 2; i++) {
    const r = -arms[i][0], f = 0.18 + 0.6 * ss01(0, 0.9, r) * (1 - ss01(1.2, 1.55, r)); // braccio teso quando mira o colpisce
    s.fore[i] += (f - s.fore[i]) * kJ; arms[i][1].rotation.x = -s.fore[i];
  }
  const dx = c.root.position.x - s.px, dz = c.root.position.z - s.pz; s.px = c.root.position.x; s.pz = c.root.position.z;
  const sp = Math.min(8, Math.hypot(dx, dz) / dt), idle = 1 - ss01(0.2, 1, sp);
  s.lean += (Math.min(0.13, sp * 0.017) - s.lean) * kJ;
  const tw = (tL - tR) * 0.08;
  c.chest.rotation.set(s.lean + Math.sin(t * 2.1 + s.ph) * 0.012, tw, 0);
  c.hip.rotation.y = -tw * 0.6;
  c.head.rotation.set(-s.lean * 0.6 + Math.sin(t * 0.7 + s.ph) * 0.03 * idle, -tw * 0.8 + Math.sin(t * 0.37 + s.ph) * 0.25 * idle, 0);
}
function hdAnimChars() {
  const now = performance.now(), dt = Math.min(0.1, (now - (HDM.lastT || now)) / 1000); HDM.lastT = now; HDM.frame++;
  if (dt <= 0) return;
  const kS = 1 - Math.exp(-20 * dt), kJ = 1 - Math.exp(-14 * dt), t = now / 1000;
  for (const c of HDM.live) { if (HDM.frame - c._seen > 120) { HDM.live.delete(c); c._on = false; continue; } hdPose(c, dt, kS, kJ, t); }
}
{ const r0 = renderer.render.bind(renderer); renderer.render = (sc, cm) => { hdAnimChars(); r0(sc, cm); }; }

