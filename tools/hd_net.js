/* =====================================================================
   MULTIPLAYER (tools/hd_net.js, inserito da tools/make_hd.py)
   ---------------------------------------------------------------------
   Un giocatore della stanza (l'host) simula il mondo condiviso come in singolo: maranza, ladri,
   civili, traffico, missioni, orologio. Lo trasmette 10 volte al secondo; gli altri (ospiti) ne
   mostrano una copia interpolata e gli mandano le loro azioni (colpi, auto prese, quest, ronda).
   Il server (cartella server/) inoltra i messaggi e, se l'host esce o mette il gioco in secondo
   piano, nomina un altro host: questo trasforma le sue copie in personaggi veri e continua.
   Avanzamento condiviso: missione, fase, quest (Binea, Brayner, tedeschi, grappa).
   Personale: schei, armi, salute, inventario, potenziamenti, lavoretti.
   ===================================================================== */
const NET_PROTO = 1;
const NET_PATHS = ['mission', 'phase', 'ladriStopped', 'q.binea', 'q.brayner', 'q.ted', 'q.grappa'];
const NET_LOOKS = [ // colori di Bepi tra cui scegliere
  { shirt: 0xa63a2e, sleeve: 0x8a2f26, hatColor: 0x2f5d3a }, { shirt: 0x2f5d8a, sleeve: 0x244a70, hatColor: 0xc8302a },
  { shirt: 0x3a7a3a, sleeve: 0x2e622e, hatColor: 0xe8c547 }, { shirt: 0xe8c547, sleeve: 0xc9a832, hatColor: 0x2a2a2a },
  { shirt: 0x6a3a8a, sleeve: 0x55306f, hatColor: 0xf2f2ec }, { shirt: 0xf2f2ec, sleeve: 0xd8d8d0, hatColor: 0x8e1b2b },
];
function netServerUrl() {
  const q = new URLSearchParams(location.search).get('server');
  if (q) return q.replace(/\/$/, '') + (/\/ws$/.test(q) ? '' : '/ws');
  if (/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return 'ws://localhost:8787/ws';
  return NET_DEFAULT_SERVER;
}
const NET_DEFAULT_SERVER = 'wss://borso-simulator.onrender.com/ws';

/* ---------------- utilità ---------------- */
const r2 = v => Math.round(v * 100) / 100, r1 = v => Math.round(v * 10) / 10;
function netSendRaw(o) { if (NET.ws && NET.ws.readyState === 1) NET.ws.send(JSON.stringify(o)); }
// eventi raggruppati per destinatario e spediti una volta per fotogramma
function netEv(to, e, d) { if (!NET.on) return; (NET.out[to] || (NET.out[to] = [])).push([e, d === undefined ? 0 : d]); }
function netFlush() { for (const to in NET.out) { const b = NET.out[to]; if (b.length) netSendRaw({ t: 'ev', to, e: 'b', d: b }); } NET.out = {}; }
function netNid(o) { if (!o.nid) o.nid = NET.nextId++; return o.nid; }
const netCirc = (a, b) => { let d = (a - b) % 24; if (d > 12) d -= 24; else if (d < -12) d += 24; return isFinite(d) ? d : 0; };
function netProgGet(p) { let o = GS; for (const k of p.split('.')) o = o[k]; return o; }
function netProgSet(p, v) {
  const k = p.split('.'); let o = GS; for (let i = 0; i < k.length - 1; i++) o = o[k[i]];
  const last = k[k.length - 1], cur = o[last];
  if (v && typeof v === 'object' && !Array.isArray(v) && cur && typeof cur === 'object') { // sul posto: le funzioni del gioco tengono riferimenti a GS.q.binea & co.
    for (const key of Object.keys(cur)) if (!(key in v)) delete cur[key];
    Object.assign(cur, JSON.parse(JSON.stringify(v)));
  } else o[last] = v;
}
function netProgAll() { const d = {}; for (const p of NET_PATHS) d[p] = JSON.parse(JSON.stringify(netProgGet(p))); return d; }
function netProgMark() { for (const p of NET_PATHS) NET.prog[p] = JSON.stringify(netProgGet(p)); }
function netApplyProg(d) { for (const p in d) if (NET_PATHS.includes(p)) { netProgSet(p, d[p]); NET.prog[p] = JSON.stringify(netProgGet(p)); } }
// avanzamento ricevuto: le voci che ho appena cambiato io restano mie finché l'host non conferma la mia modifica
function netOnProg(m, from) {
  const d = {};
  for (const p in m.d) {
    const pend = NET.pend[p];
    if (pend) { if (m.by === NET.id && m.q >= pend) delete NET.pend[p]; else continue; }
    if (JSON.stringify(netProgGet(p)) !== NET.prog[p]) continue; // cambiata qui e non ancora spedita: parte al prossimo giro
    d[p] = m.d[p];
  }
  netApplyProg(d);
}

/* ---------------- giocatori: locale e remoti ---------------- */
function netDoorPos(key) { const d = INTERIORS[key] && INTERIORS[key].door; return d ? new THREE.Vector3(d.x, H(d.x, d.z), d.z) : new THREE.Vector3(LOC.osteria.door.x, 0, LOC.osteria.door.z); }
function netLocalP() {
  const c = player.inCar;
  return { id: NET.id, local: true, pos: GS.inside ? netDoorPos(GS.inside.key) : c ? c.pos : player.a.pos, yaw: c ? c.heading : player.a.yaw, inCar: !!c, dead: player.dead, inside: !!GS.inside, peer: null };
}
function netPeerP(q) { return { id: q.id, pos: q.inside ? netDoorPos(q.inside) : q.pos, yaw: q.yaw, inCar: !!q.car, dead: q.dead, inside: !!q.inside, peer: q }; }
function netPlayers(outdoorOnly) {
  const out = [];
  if (!(outdoorOnly && (GS.inside || GS.mode === 'title'))) out.push(netLocalP());
  for (const q of NET.peers.values()) if (q.st && !(outdoorOnly && q.inside)) out.push(netPeerP(q));
  return out;
}
function netMinDist(x, z) { let b = 1e9; for (const p of netPlayers(true)) b = Math.min(b, Math.hypot(p.pos.x - x, p.pos.z - z)); return b === 1e9 ? 0 : b; } // tutti al chiuso: non sparisce niente
function netNearestP(pos, alive) {
  let best = null, bd = 1e9;
  for (const p of netPlayers(true)) { if (alive && p.dead) continue; const d = Math.hypot(p.pos.x - pos.x, p.pos.z - pos.z); if (d < bd) { bd = d; best = p; } }
  return best || netLocalP();
}
function netNearestPlayerId(pos) { return NET.on ? netNearestP(pos, true).id : null; }
function netFocusFor(a) {
  const want = a.kind === 'helper' ? a.owner : a.follower ? a.followId : null;
  if (want) { if (want === NET.id) return netLocalP(); const q = NET.peers.get(want); if (q && q.st) return netPeerP(q); }
  if (a.kind === 'helper' && !a.owner) return netLocalP();
  return netNearestP(a.pos, true);
}
// usate dalle IA (patch in make_hd.py): "il giocatore" è quello su cui l'IA è concentrata
const fpDead = () => NET.focus ? NET.focus.dead : player.dead;
const fpInCar = () => NET.focus ? NET.focus.inCar : !!player.inCar;
const fpYaw = () => NET.focus ? NET.focus.yaw : (player.inCar ? player.inCar.heading : player.a.yaw);
function netNearestFoe(a, maxD) {
  let best = null, bd = maxD;
  for (const p of netPlayers(true)) {
    if (p.dead || (p.local && player.fly)) continue;
    const d = Math.hypot(p.pos.x - a.pos.x, p.pos.z - a.pos.z);
    if (d < bd) { bd = d; best = { pos: p.pos, isPlayer: true, remote: p.peer, d }; }
  }
  for (const h of player.helpers) { if (h.dead) continue; const d = Math.hypot(h.pos.x - a.pos.x, h.pos.z - a.pos.z); if (d < bd * 0.8) { bd = d; best = { pos: h.pos, agent: h, d }; } }
  return best;
}
function netHurtFoe(foe, dmg) { if (foe.remote) netEv(foe.remote.id, 'hurt', { d: dmg }); else hurtPlayer(dmg); }
function netHelperCount() { return NET.on && !NET.host ? agents.filter(a => a.kind === 'helper' && !a.dead && !a.removed && a._def && a._def.ow).length : player.helpers.length; }
function netMyHelpers() {
  if (!NET.on) return player.helpers.length;
  if (NET.host) return player.helpers.filter(h => !h.owner).length;
  return agents.filter(a => a.kind === 'helper' && !a.removed && a._def && a._def.ow === NET.id).length;
}

/* ---------------- avatar dei giocatori remoti ---------------- */
function netNameSprite(name) {
  const cv = document.createElement('canvas'); cv.width = 256; cv.height = 64; const g = cv.getContext('2d');
  g.font = "800 34px 'Barlow Condensed',Arial"; const w = Math.min(244, g.measureText(name).width + 28);
  g.fillStyle = 'rgba(12,16,22,.78)'; g.beginPath(); if (g.roundRect) g.roundRect(128 - w / 2, 8, w, 46, 12); else g.rect(128 - w / 2, 8, w, 46); g.fill();
  g.fillStyle = '#E8C547'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(name, 128, 32);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), depthTest: false, transparent: true }));
  s.scale.set(1.6, 0.4, 1); s.position.y = 2.45; s.renderOrder = 998; return s;
}
function netLook(look) { return Object.assign({}, P.bepi, look || {}); }
function netAddPeer(id, name, look, last) {
  if (id === NET.id || NET.peers.has(id)) return;
  const q = { id, name, look: netLook(look), st: null, buf: [], pos: new THREE.Vector3(), yaw: 0, car: null, inside: '', dead: false, at: 0 };
  q.av = { kind: 'peer', name, c: makeChar(q.look), pos: q.pos, yaw: 0, speed: 0, phase: 0, sitting: false, aiming: false, attackAnim: 0, riding: false, dead: false, deadT: 0, scale: 1, removed: false, bubble: null, room: undefined };
  q.label = netNameSprite(name); q.av.c.root.add(q.label);
  q.av.c.root.visible = false; scene.add(q.av.c.root);
  NET.peers.set(id, q);
  if (last) netPeerState(q, last);
  netHudUpdate();
}
function netRemovePeer(id) {
  const q = NET.peers.get(id); if (!q) return;
  if (q.av.c.root.parent) q.av.c.root.parent.remove(q.av.c.root);
  if (q.glider) scene.remove(q.glider);
  q.av.removed = true; NET.peers.delete(id);
  if (NET.host) { // le sue auto restano parcheggiate, la sua ronda torna a casa, i seguaci cercano un altro giocatore
    for (const c of cars) if (c.remoteBy === id) { c.remoteBy = null; c.parked = true; c.speed = 0; }
    for (const h of player.helpers.slice()) if (h.owner === id) helperGoHome(h, false);
    for (const a of agents) if (a.followId === id) a.followId = netNearestPlayerId(a.pos);
  }
  netHudUpdate();
}
function netPeerState(q, m) {
  const now = performance.now();
  q.buf.push({ t: now, x: m.x, y: m.y, z: m.z, r: m.r, s: m.s }); if (q.buf.length > 6) q.buf.shift();
  q.st = m; q.inside = m.in || ''; q.dead = !!(m.f & 1); q.car = m.c || null;
  if (m.at !== q.at) { q.at = m.at; q.av.attackAnim = 1; }
}
function netUpdatePeers(dt) {
  const now = performance.now() - 110;
  for (const c of cars) c._peerDriven = false;
  for (const q of NET.peers.values()) if (q.car && !q.inside) { const c = netCarByNid(q.car[0]); if (c) c._peerDriven = true; }
  for (const q of NET.peers.values()) {
    if (!q.st) continue;
    const b = q.buf; let i = b.length - 1; while (i > 0 && b[i - 1].t > now) i--;
    const s1 = b[i], s0 = b[Math.max(0, i - 1)], k = s1.t === s0.t ? 1 : clamp((now - s0.t) / (s1.t - s0.t), 0, 1);
    q.pos.set(lerp(s0.x, s1.x, k), lerp(s0.y, s1.y, k), lerp(s0.z, s1.z, k)); q.yaw = lerpAngle(s0.r, s1.r, k);
    const av = q.av, f = q.st.f || 0;
    av.speed = lerp(s0.s, s1.s, k); av.yaw = q.yaw; av.sitting = !!(f & 2); av.aiming = !!(f & 4); av.riding = !!(f & 16);
    if ((f & 1) && !av.dead) { av.dead = true; av.deadT = 0; } else if (!(f & 1) && av.dead) { av.dead = false; av.c.body.rotation.x = 0; av.c.body.position.y = 0; }
    // dove si trova: in strada, nel mio stesso locale o in un altro
    const mine = GS.inside ? GS.inside.key : '';
    const parent = q.inside ? (q.inside === mine ? GS.inside.S : null) : (mine ? null : scene);
    av.room = q.inside ? (q.inside === mine ? GS.inside : 'altrove') : undefined;
    if (parent && av.c.root.parent !== parent) parent.add(av.c.root);
    av.c.root.visible = !!parent && !q.car;
    if (av.c.root.visible) animChar(av, dt);
    // auto guidata da lui: la posizione arriva da lui
    if (q.car && !q.inside) {
      const c = netCarByNid(q.car[0]);
      if (c && c !== player.inCar) { c.pos.x = q.car[1]; c.pos.z = q.car[2]; c.heading = q.car[3]; c.speed = q.car[4]; c.driver = false; c.parked = false; if (NET.host) { c.remoteBy = q.id; c.ai = false; } c.place(); }
    }
    // in volo: vela sopra la testa
    if (f & 8) {
      if (!q.glider) { q.glider = makeGlider(0x2fb8ff, 0); scene.add(q.glider); }
      q.glider.visible = !q.inside; q.glider.position.set(q.pos.x, q.pos.y + 7.4, q.pos.z); q.glider.rotation.set(0, q.yaw, 0);
      av.c.root.visible = !q.inside;
    } else if (q.glider) { scene.remove(q.glider); q.glider = null; }
  }
}
function netCarByNid(n) { if (!n) return null; for (const c of cars) if (c.nid === n) return c; return null; }

/* ---------------- stato del giocatore locale (12 al secondo) ---------------- */
function netSendSelf() {
  const a = player.a, c = player.inCar, p = c ? c.pos : a.pos;
  let f = 0; if (player.dead) f |= 1; if (a.sitting) f |= 2; if (a.aiming) f |= 4; if (player.fly) f |= 8; if (a.riding) f |= 16;
  if (a.attackAnim > (NET.lastAtk || 0) + 0.2) NET.atk = (NET.atk || 0) + 1; NET.lastAtk = a.attackAnim;
  const m = { t: 'p', x: r2(p.x), y: r2(p.y), z: r2(p.z), r: r2(c ? c.heading : a.yaw), s: r1(c ? 0 : a.speed), f, at: NET.atk || 0, in: GS.inside ? GS.inside.key : '', hp: Math.round(player.hp) };
  if (c) m.c = [netNid(c), r2(c.pos.x), r2(c.pos.z), r2(c.heading), r1(c.speed)];
  netSendRaw(m);
}

/* ---------------- host: stato del mondo (10 al secondo) ---------------- */
function netAgentDef(a) {
  const pr = a.c && a.c.preset, d = { n: a.nid, k: a.kind, x: r2(a.pos.x), z: r2(a.pos.z), p: pr };
  if (a.name) d.nm = a.name; if (a.boss) d.b = 1; if (a.bossType) d.bt = a.bossType; if (a.scooter) d.sc = 1;
  if (a.qid) d.q = a.qid; if (a.kid) d.kd = a.kid; if (a.fixed) d.fx = 1; if (a.sit) d.si = 1; if (a.bocce) d.bo = 1; if (a.mission) d.mi = 1; if (a.quest) d.qu = 1; if (a.qguard) d.qg = a.qguard;
  if (a.kind === 'helper') { d.ow = a.owner || NET.id; d.ra = a.ranged ? 1 : 0; d.ix = a.idx; d.fa = a.family; }
  if (a.followId) d.fo = a.followId; if (a.maxHp) d.hm = a.maxHp; if (a.homeYaw !== undefined) d.hy = r2(a.homeYaw);
  if (a.home) d.ho = [r2(a.home.x), r2(a.home.z)]; if (a.target && a.target.door) d.th = houses.indexOf(a.target); if (a.state) d.st = a.state;
  if (a.lines) d.ln = a.lines; if (a.kidMode) d.km = a.kidMode; if (a.walkSp) d.ws = r2(a.walkSp);
  return d;
}
function netAgentState(a) {
  let f = 0; if (a.dead) f |= 1; if (a.sitting) f |= 2; if (a.aiming) f |= 4; if (a.riding) f |= 8; if (a.robbing) f |= 16; if (!a.c.root.visible) f |= 32; if (a.follower) f |= 64;
  if (a.attackAnim > (a._atkSent || 0) + 0.05) f |= 128; a._atkSent = a.attackAnim;
  if (a.state === 'home' && a.kind === 'helper') f |= 256;
  return [a.nid, r2(a.pos.x), r2(a.pos.y), r2(a.pos.z), r2(a.yaw), r1(a.speed), f, a.maxHp ? Math.round(clamp(a.hp / a.maxHp, 0, 1) * 100) : 100];
}
function netCarState(c) {
  let f = 0; if (c.parked) f |= 1; if (c.driver) f |= 2; if (c.remoteBy || c === player.inCar) f |= 4; if (c.ai) f |= 8;
  return [c.nid, r2(c.pos.x), r2(c.pos.z), r2(c.heading), r1(c.speed), f];
}
function netHostTick() {
  const full = performance.now() - (NET.lastFull || 0) > 3000 || NET.forceFull; if (full) { NET.lastFull = performance.now(); NET.forceFull = false; }
  const A = [], NA = [], seen = new Set();
  for (const a of agents) { if (a.removed) continue; const fresh = !a.nid || !NET.sentA.has(a.nid); netNid(a); seen.add(a.nid); if (fresh || full) NA.push(netAgentDef(a)); A.push(netAgentState(a)); }
  const RA = [...NET.sentA].filter(n => !seen.has(n)); NET.sentA = seen;
  const C = [], NC = [], seenC = new Set();
  for (const c of cars) { const fresh = !c.nid || !NET.sentC.has(c.nid); netNid(c); seenC.add(c.nid); if (fresh || full) NC.push({ n: c.nid, ty: c.type, co: c.color, bp: c.isBepi ? 1 : 0 }); C.push(netCarState(c)); }
  const RC = [...NET.sentC].filter(n => !seenC.has(n)); NET.sentC = seenC;
  const ms = MS.spawned ? { s: 1, t: MS.targets.filter(a => !a.removed).map(netNid), tot: MS.total, st: MS.stopped, b: MS.boss && !MS.boss.removed ? netNid(MS.boss) : 0 } : { s: 0 };
  netSendRaw({ t: 'w', k: ++NET.tick, full: full ? 1 : 0, tm: Math.round(GS.time * 10000) / 10000, dy: GS.day, a: A, na: NA, ra: RA, c: C, nc: NC, rc: RC, ms });
}
function netHostSnap() { netSendRaw({ t: 'snap', d: { prog: netProgAll(), tm: GS.time, dy: GS.day } }); }

/* ---------------- ospite: copie del mondo ---------------- */
const NET_DUMMY = { root: new THREE.Group(), hand: new THREE.Group(), body: new THREE.Group(), legL: new THREE.Group(), legR: new THREE.Group(), armL: new THREE.Group(), armR: new THREE.Group() };
function netMakeReplica(d) {
  NET.making = true; const a = new Agent(d.k, d.p || vecioPreset(), d.x || 0, d.z || 0); NET.making = false;
  agents.push(a); a.net = true; a.nid = d.n; a._def = d; a._buf = [];
  netDefApply(a, d);
  if (d.sc) { a.riding = true; a.scooter = mkScooter(); a.c.root.add(a.scooter); }
  if (d.k === 'helper') {
    if (d.ra) { const m = mkWeaponModel(3); m.rotation.x = Math.PI / 2; a.c.hand.add(m); }
    else { const g = new THREE.Group(); part(bxg(0.05, 1.5, 0.05), lm(0x7a5232), 0, 0, 0.3, g); for (const s of [-0.08, 0, 0.08]) part(bxg(0.02, 0.3, 0.02), lm(0x888888), s, 0.85, 0.3, g); g.rotation.x = 0.4; a.c.hand.add(g); }
  }
  if (d.q) { QN[d.q] = a; a.mark = new THREE.Sprite(markMat); a.mark.scale.set(0.8, 0.8, 1); a.mark.renderOrder = 999; a.mark.visible = false; scene.add(a.mark); }
  NET.rep.set(d.n, a); return a;
}
function netDefApply(a, d) {
  a._def = d; a.name = d.nm; a.boss = !!d.b; a.bossType = d.bt || null; a.qid = d.q; a.kid = d.kd; a.fixed = !!d.fx; a.sit = !!d.si; a.bocce = !!d.bo;
  a.mission = !!d.mi; a.quest = !!d.qu; a.qguard = d.qg; a.lines = d.ln || null; a.kidMode = d.km || null; a.owner = d.ow; a.followId = d.fo;
  if (d.hm) a.maxHp = d.hm; if (d.hy !== undefined) a.homeYaw = d.hy; if (d.ho) a.home = { x: d.ho[0], z: d.ho[1] };
}
function netGuestWorld(m) {
  const now = performance.now();
  NET.lastW = now;
  for (const d of m.na || []) { const a = NET.rep.get(d.n); if (a && !a.removed) netDefApply(a, d); else netMakeReplica(d); }
  if (m.full) { const keep = new Set((m.a || []).map(s => s[0])); for (const [n, a] of NET.rep) if (!keep.has(n)) netDropReplica(n, a); }
  for (const n of m.ra || []) { const a = NET.rep.get(n); if (a) netDropReplica(n, a); }
  for (const s of m.a || []) { const a = NET.rep.get(s[0]); if (!a) continue; a._buf.push({ t: now, s }); if (a._buf.length > 5) a._buf.shift(); }
  // auto
  for (const d of m.nc || []) if (!netCarByNid(d.n)) { NET.making = true; const c = new Car(d.ty, d.co, null, 0); NET.making = false; c.net = true; c.nid = d.n; c.isBepi = !!d.bp; c._buf = []; c.lane = null; }
  const keepC = m.full ? new Set((m.c || []).map(s => s[0])) : null;
  for (const c of cars.slice()) if (c.net && c !== player.inCar && ((m.rc || []).includes(c.nid) || (keepC && !keepC.has(c.nid)))) { scene.remove(c.mesh); cars.splice(cars.indexOf(c), 1); }
  for (const s of m.c || []) { const c = netCarByNid(s[0]); if (!c || c === player.inCar) continue; if (!c._buf) c._buf = []; c._buf.push({ t: now, s }); if (c._buf.length > 5) c._buf.shift(); }
  // missione in corso
  const ms = m.ms || {}; MS.spawned = !!ms.s; MS.targets = (ms.t || []).map(n => NET.rep.get(n)).filter(Boolean); MS.total = ms.tot || 0; MS.stopped = ms.st || 0; MS.boss = ms.b ? NET.rep.get(ms.b) || null : null;
  // orologio dell'host
  if (Math.abs(netCirc(GS.time, m.tm)) > 0.03) GS.time = m.tm; GS.day = m.dy; NET.expTm = GS.time; NET.expAt = now;
}
function netDropReplica(n, a) {
  NET.rep.delete(n);
  if (a.dead && !a.puffed) { a.puffed = true; puff(a.pos.x, a.pos.y + 0.8, a.pos.z); }
  if (a.mark) scene.remove(a.mark);
  removeAgent(a);
}
function netInterp(buf, now) { let i = buf.length - 1; while (i > 0 && buf[i - 1].t > now) i--; const s1 = buf[i], s0 = buf[Math.max(0, i - 1)]; return [s0.s, s1.s, s1.t === s0.t ? 1 : clamp((now - s0.t) / (s1.t - s0.t), 0, 1)]; }
function netGuestAgents(dt) {
  const now = performance.now() - 120;
  for (const a of NET.rep.values()) {
    if (a.removed || !a._buf.length) continue;
    const [s0, s1, k] = netInterp(a._buf, now), f = s1[6];
    a.pos.set(lerp(s0[1], s1[1], k), lerp(s0[2], s1[2], k), lerp(s0[3], s1[3], k)); a.yaw = lerpAngle(s0[4], s1[4], k); a.speed = lerp(s0[5], s1[5], k);
    if ((f & 1) && !a.dead) { a.dead = true; a.deadT = 0; a.speed = 0; }
    a.sitting = !!(f & 2); a.aiming = !!(f & 4); a.robbing = !!(f & 16); a.follower = !!(f & 64);
    if ((f & 128) && a._atkT !== s1) { a._atkT = s1; a.attackAnim = 1; }
    if (!(f & 8) && a.riding) { a.riding = false; if (a.scooter) { a.c.root.remove(a.scooter); a.scooter = null; emit(a.pos.x, a.pos.y + 0.3, a.pos.z, 8, [0x222222, 0x66ffcc], 3, 0.15, 0.6); } }
    a.c.root.visible = !(f & 32);
    a.hp = (a.maxHp || 100) * s1[7] / 100;
    if (a.kind === 'ladro' && a._def.th >= 0 && houses[a._def.th]) houses[a._def.th].robbing = a.robbing ? 1 : 0;
    a.c.body.rotation.x = (f & 256) ? 0.35 : (a.dead ? a.c.body.rotation.x : 0);
    animChar(a, dt);
    if (a.boss && bossShown === a) updateBossBar(a);
  }
  for (const c of cars) {
    if (c === player.inCar) { c._buf = []; continue; }
    if (!c.net || !c._buf || !c._buf.length) continue;
    if ([...NET.peers.values()].some(q => q.car && q.car[0] === c.nid)) continue; // la guida un altro giocatore
    const [s0, s1, k] = netInterp(c._buf, now), f = s1[5];
    c.pos.x = lerp(s0[1], s1[1], k); c.pos.z = lerp(s0[2], s1[2], k); c.heading = lerpAngle(s0[3], s1[3], k); c.speed = lerp(s0[4], s1[4], k);
    c.parked = !!(f & 1); c.driver = !!(f & 2) && !(f & 4); c.ai = !!(f & 8); c.taken = !!(f & 4);
    c.place();
  }
}
// richieste dell'ospite all'host per creare personaggi: le proprietà assegnate subito dopo vengono raccolte e spedite
function netSpawnProxy(fn, args) {
  const x = args.x, z = args.z;
  const pr = { kind: args.kind || (fn === 'ladro' ? 'ladro' : 'maranza'), pos: new THREE.Vector3(x, H(x, z), z), removed: false, bubble: null, scale: 1, c: NET_DUMMY, _proxy: true, hp: 60, maxHp: 60, dead: false };
  const skip = new Set(Object.keys(pr));
  queueMicrotask(() => {
    const props = {};
    for (const k of Object.keys(pr)) if (!skip.has(k)) { const v = pr[k]; if (v === null || ['number', 'string', 'boolean'].includes(typeof v)) props[k] = v; }
    netEv('host', 'spawn', Object.assign({ fn, props }, args));
  });
  return pr;
}
function netHitReq(a, amt, src) { netEv('host', 'hit', { n: a.nid, d: Math.round(amt * 10) / 10, s: src === 'car' ? 'car' : 'player' }); if (isEnemy(a)) a._hitT = performance.now(); }

/* ---------------- proiettili, premi, raccolte ---------------- */
function netProjOut(type, ox, oy, oz, vx, vy, vz, dmg, owner, opt) {
  if (NET.remoteCall) return;
  const w = owner === 'enemy' ? (NET.host ? 'e' : null) : 'r'; if (!w) return;
  netEv('all', 'pj', [type, r2(ox), r2(oy), r2(oz), r2(vx), r2(vy), r2(vz), Math.round(dmg), w, opt.grav === undefined ? 9 : opt.grav, opt.life || 3, opt.explode || 0]);
}
function netRewardRemote(a, cash) {
  if (!NET.host || !a._lastBy || a._lastBy === NET.id) return false;
  netEv(a._lastBy, 'rew', { c: cash, k: a.kind, b: a.boss ? 1 : 0, nm: a.name || '' });
  return true;
}
function netGotReward(d) {
  GS.kills++; GS.money += d.c; if (GS.q.perm.santino) GS.money += Math.ceil(d.c * 0.25);
  toast(d.k === 'ladro' ? `Ladro fermato! +${d.c} schei (e una dentiera restituita)` : d.b ? `${d.nm} rieducato! +${d.c} schei` : `Maranza rieducato +${d.c} schei`);
  if (!player.unlocked[4] && GS.kills >= 20) unlockWeapon(4, 6, 'Zazza ti manda un regalo: il Bazooka a Grappa! (20 rieducati)');
  if (Math.random() < 0.25) setTimeout(() => say(player.a, pick(['Torna dalla mamma!', 'Questa la gavevi meritada', 'Un altro rieducà!', 'Borso ringrazia', 'E adesso a messa!']), 2), 400);
  hitMarker();
}
function netSofiaCaught() {
  talk([{ w: 'Sofia', t: 'Va bene, va bene, mi arrendo! Hai il fiato di un ventenne... di un ventenne che fuma.' }, { w: 'Bepi', t: 'Fumavo, bocia. Adesso bevo e basta.', act: () => kidFollow('sofia') }]);
}

/* ---------------- ricezione ---------------- */
function netOnMessage(m) {
  switch (m.t) {
    case 'p': { const q = NET.peers.get(m.id); if (q) netPeerState(q, m); break; }
    case 'w': if (!NET.host) netGuestWorld(m); break;
    case 'ev': if (m.e === 'b') for (const [e, d] of m.d) netOnEvent(e, d, m.from); else netOnEvent(m.e, m.d, m.from); break;
    case 'peer+': netAddPeer(m.id, m.name, m.look); toast(`🌐 ${m.name} è entrato a Borso`); if (NET.host) { NET.forceFull = true; netHostSnap(); netEv('all', 'prog', { d: netProgAll() }); } break;
    case 'peer-': { const q = NET.peers.get(m.id); if (q) toast(`🌐 ${q.name} è uscito`); netRemovePeer(m.id); break; }
    case 'host': netSetHost(m.id === NET.id, m.snap); break;
    case 'chat': { const q = NET.peers.get(m.id); if (q) { say(q.av, m.text, 5); netChatLog(m.name, m.text); } break; }
    case 'look': { const q = NET.peers.get(m.id); if (q) { const st = q.st; netRemovePeer(m.id); netAddPeer(m.id, q.name, m.look, st); } break; }
    case 'pong': NET.rtt = performance.now() - m.c; break;
    case 'err': netStatus(m.msg, true); break;
  }
}
function netOnEvent(e, d, from) {
  NET.remoteCall = true;
  try {
    switch (e) {
      case 'pj': spawnProj(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8] === 'e' ? 'enemy' : 'remote', { grav: d[9], life: d[10], explode: d[11], net: true }); break;
      case 'hurt': hurtPlayer(d.d); break;
      case 'rew': netGotReward(d); break;
      case 'say': { const a = NET.rep.get(d.n); if (a) say(a, d.tx, d.du); break; }
      case 'radio': radio(d.w, d.tx, d.du); break;
      case 'toast': toast(d.tx, d.du); break;
      case 'sfx': sfx(d.nm, { x: d.x, y: H(d.x, d.z), z: d.z }); break;
      case 'mdone': completeMission(d.m); netProgMark(); break;
      case 'ending': if (GS.mode === 'play') startEnding(); break;
      case 'qdrop': questDrop(d.id, d.x, d.z); break;
      case 'pk+': spawnPickup(d.ty, d.x, d.z); pickups[pickups.length - 1].nid = d.n; break;
      case 'pk-': { const i = pickups.findIndex(k => k.nid === d.n); if (i >= 0) { scene.remove(pickups[i].g); pickups.splice(i, 1); } if (NET.host) netEv('all', 'pk-', d); break; }
      case 'prog': if (NET.host) { netApplyProg(d.d); netEv('all', 'prog', { d: d.d, by: from, q: d.q }); syncQuestItems(); netAfterRemoteProg(from); } else { netOnProg(d, from); syncQuestItems(); } break;
      case 'carDeny': { const c = netCarByNid(d.n); if (c && player.inCar === c) { c.speed = 0; exitCar(); toast('Qualcun altro è già al volante.'); } break; }
      case 'sofia': netSofiaCaught(); break;
      // ---- solo host ----
      case 'hit': if (NET.host) netOnHit(d, from); break;
      case 'spawn': if (NET.host) netOnSpawn(d, from); break;
      case 'recruit': if (NET.host) netOnRecruit(d, from); break;
      case 'carTake': if (NET.host) netOnCarTake(d, from); break;
      case 'carDrop': if (NET.host) { const c = netCarByNid(d.n); if (c && c.remoteBy === from) { c.remoteBy = null; c.parked = true; c.speed = 0; c.pos.x = d.x; c.pos.z = d.z; c.heading = d.h; c.place(); } } break;
      case 'acmd': if (NET.host) { const a = agents.find(x => x.nid === d.n); if (a) { Object.assign(a, d.s); if (d.s.fleeing) a.chaser = from; } } break;
      case 'time': if (NET.host) { GS.time = d.tm; if (d.dy > GS.day) GS.day = d.dy; checkDayNight(); } break;
    }
  } catch (err) { console.warn('NET evento', e, err); }
  NET.remoteCall = false;
}
function netOnHit(d, from) {
  const a = agents.find(x => x.nid === d.n); if (!a || a.dead || a.removed) return;
  NET.hitBy = from; NET.sim = true; damage(a, d.d, d.s); NET.sim = false; NET.hitBy = null;
}
function netOnSpawn(d, from) {
  NET.sim = true; let a = null;
  if (d.fn === 'maranza') a = spawnMaranza(d.x, d.z, d.o || {});
  else if (d.fn === 'ladro') a = spawnLadro(d.x, d.z, houses[d.th] || pick(houses), d.o || {});
  else if (d.fn === 'agent') a = spawnAgent(d.kind, d.preset || vecioPreset(), d.x, d.z);
  NET.sim = false;
  if (a && d.props) for (const k in d.props) if (!['nid', 'net', 'removed', 'pos', 'c'].includes(k)) a[k] = d.props[k];
}
function netOnRecruit(d, from) {
  const h = houses[d.hi]; if (!h) return;
  if (player.helpers.filter(x => x.owner === from).length >= 3) { netEv(from, 'toast', { tx: `🚪 ${h.family}: «Sì ma ghe ne gavè za tre, xe na ronda o na processione?»` }); return; }
  NET.toastTo = from; NET.sim = true;
  const a = recruitHelper(h); a.owner = from; missionOnRecruit();
  NET.sim = false; NET.toastTo = null;
}
function netOnCarTake(d, from) {
  const c = netCarByNid(d.n); if (!c) return;
  if ((c.remoteBy && c.remoteBy !== from) || c === player.inCar) { netEv(from, 'carDeny', { n: d.n }); return; }
  c.remoteBy = from; c.ai = false; c.driver = false; c.parked = false;
}
function netCarTake(c) {
  if (NET.host) return !c.remoteBy;
  if (c.taken || [...NET.peers.values()].some(q => q.car && q.car[0] === c.nid)) { toast('Qualcun altro è già al volante.'); return false; }
  netEv('host', 'carTake', { n: netNid(c) }); return true;
}
// l'host ha ricevuto avanzamento da un ospite: personaggi delle quest vicino a chi ha parlato
function netAfterRemoteProg(from) {
  const q = NET.peers.get(from);
  if (q && q.st) {
    let pos = q.pos; if (q.inside && INTERIORS[q.inside]) { const dd = INTERIORS[q.inside].door; pos = new THREE.Vector3(dd.x, H(dd.x, dd.z), dd.z); }
    NET.focus = { id: q.id, pos, yaw: q.yaw, inCar: !!q.car, dead: q.dead, inside: false, peer: q };
  }
  syncQuestNPCs(); NET.focus = null;
}

/* ---------------- avanzamento condiviso, orologio ---------------- */
function netProgTick() {
  const changed = {}; let any = false;
  for (const p of NET_PATHS) { const s = JSON.stringify(netProgGet(p)); if (s !== NET.prog[p]) { NET.prog[p] = s; changed[p] = JSON.parse(s); any = true; } }
  if (!any) return;
  if (NET.host) { netEv('all', 'prog', { d: changed }); syncQuestItems(); return; }
  const q = NET.pseq = (NET.pseq || 0) + 1; for (const p in changed) NET.pend[p] = q;
  netEv('host', 'prog', { d: changed, q });
}
function netGuestClock() {
  if (NET.expAt === undefined) return;
  const exp = NET.expTm + (performance.now() - NET.expAt) / 15000;
  if (Math.abs(netCirc(GS.time, exp)) > 0.25) { netEv('host', 'time', { tm: GS.time, dy: GS.day }); NET.expTm = GS.time; NET.expAt = performance.now(); }
}

/* ---------------- host: simulazione del mondo anche fuori dal gioco in strada ---------------- */
function netAgentsSim(dt) {
  NET.sim = true;
  for (const a of agents.slice()) {
    if (a.removed) continue;
    NET.focus = netFocusFor(a);
    const far = netMinDist(a.pos.x, a.pos.z) > 200;
    if (far && !a.mission && !a.quest && (mmFrame & 3)) continue;
    const adt = far && !a.mission ? dt * 4 : dt;
    if (a.kind === 'maranza' || a.kind === 'boss') updMaranza(a, adt);
    else if (a.kind === 'ladro') updLadro(a, adt);
    else if (a.kind === 'helper') updHelper(a, adt);
    else if (a.kind === 'kid' || a.follower) updFollower(a, adt);
    else updCiv(a, adt);
  }
  NET.focus = null; NET.sim = false;
}
function netSpawnTick(dt) {
  const ps = netPlayers(true); if (!ps.length) return; // nessuno in strada
  const p = ps[(NET.spawnI = ((NET.spawnI || 0) + 1)) % ps.length];
  NET.focus = p; NET.sim = true; updateSpawns(dt); NET.sim = false; NET.focus = null;
}
function netHostSim(dt) {
  if (GS.mode === 'play' && !GS.inside) return; // ci pensa il ciclo normale
  if (GS.mode !== 'play') { GS.time += dt / 15; if (GS.time >= 24) GS.time -= 24; checkDayNight(); }
  netAgentsSim(dt);
  if (GS.mode !== 'dead') for (const c of cars) if (c !== player.inCar && !c.remoteBy) updateCarAI(c, dt);
  updateProjectiles(dt);
  NET.sim = true; updateMission(dt); NET.sim = false; netSpawnTick(dt);
}
function netGuestMission() {
  const pp = playerPos();
  if (GS.mission === 5) { const d = LOC.osteria.door; if (!player.inCar && Math.hypot(pp.x - d.x, pp.z - d.z) < 2.5) startEnding(); }
  if (MS.boss && !MS.boss.dead && !MS.boss.removed) { const d = Math.hypot(MS.boss.pos.x - pp.x, MS.boss.pos.z - pp.z); if (d < 45 && bossShown !== MS.boss) showBossBar(MS.boss); else if (d > 70 && bossShown) hideBossBar(); }
  else if (bossShown && (bossShown.dead || bossShown.removed)) hideBossBar();
}

/* ---------------- un fotogramma di rete (chiamato all'inizio del ciclo) ---------------- */
function netFrame(dt) {
  if (!NET.on) return;
  const now = performance.now();
  // auto lasciata (scesa, morto, decollo...): torna all'host con la posizione in cui è stata lasciata
  if (NET.myCar && player.inCar !== NET.myCar) { const c = NET.myCar; c._buf = []; if (!NET.host) netEv('host', 'carDrop', { n: c.nid, x: r2(c.pos.x), z: r2(c.pos.z), h: r2(c.heading) }); }
  NET.myCar = player.inCar;
  NET.inbox.splice(0).forEach(netOnMessage);
  if (NET.host) netHostSim(dt);
  else {
    if (GS.mode !== 'play' && GS.mode !== 'title') { GS.time += dt / 15; if (GS.time >= 24) GS.time -= 24; checkDayNight(); }
    netGuestAgents(dt); netGuestClock();
  }
  netUpdatePeers(dt);
  if (GS.mode !== 'title' && now - (NET.lastP || 0) > 80) { NET.lastP = now; netSendSelf(); }
  if (NET.host && now - (NET.lastTick || 0) > 100) { NET.lastTick = now; netHostTick(); }
  if (NET.host && now - (NET.lastSnap || 0) > 4000) { NET.lastSnap = now; netHostSnap(); }
  if (now - (NET.lastProg || 0) > 300) { NET.lastProg = now; netProgTick(); }
  if (now - (NET.lastPing || 0) > 5000) { NET.lastPing = now; netSendRaw({ t: 'ping', c: now }); }
  if (!NET.host && NET.lastW && now - NET.lastW > 6000 && !NET.warnedW) { NET.warnedW = true; toast('🌐 L\'host non risponde: attendo…'); }
  if (NET.lastW && now - NET.lastW < 1000) NET.warnedW = false;
  netFlush();
}
// fuori dal ciclo (scheda in secondo piano, requestAnimationFrame fermo): l'host continua piano
setInterval(() => { if (NET.on && document.hidden) { const now = performance.now(); const dt = Math.min(0.25, (now - (NET.bgT || now)) / 1000); NET.bgT = now; if (NET.host) netFrame(dt); else { NET.inbox.splice(0).forEach(netOnMessage); netSendSelf(); netFlush(); } } else NET.bgT = performance.now(); }, 250);

/* ---------------- ruoli: host e ospite ---------------- */
function netSetHost(isHost, snap) {
  if (isHost === NET.host) return;
  if (isHost) {
    NET.host = true; NET.forceFull = true; NET.sentA = new Set(); NET.sentC = new Set(); NET.pend = {};
    let maxN = NET.nextId;
    // le copie diventano personaggi veri
    for (const a of agents) {
      if (!a.net) continue; a.net = false; maxN = Math.max(maxN, a.nid || 0); const d = a._def || {};
      if (a.dead) continue;
      const home = a.home || { x: a.pos.x, z: a.pos.z };
      if (a.kind === 'maranza' || a.kind === 'boss') { a.home = home; a.state = d.st === 'fight' || d.st === 'flee' ? 'fight' : 'idle'; a.throwT = rand(1, 2.5); a.strafe = Math.random() < 0.5 ? 1 : -1; a.tauntT = rand(2, 8); a.t = 0; }
      else if (a.kind === 'ladro') { a.target = houses[d.th] || pick(houses); a.state = d.st === 'robbing' ? 'approach' : (d.st || 'approach'); a.throwT = rand(1.5, 3); a.rob = 0; a.idleT = rand(3, 7); }
      else if (a.kind === 'helper') { a.state = d.st === 'home' ? 'home' : 'follow'; a.homeT = 6; a.idx = d.ix || 0; a.ranged = !!d.ra; a.cool = 0; a.family = d.fa; a.owner = d.ow === NET.id ? null : d.ow; if (a.state !== 'home') player.helpers.push(a); }
      else if (a.follower || a.kid) { a.state = a.follower ? 'follow' : 'idle'; a.home = home; }
      else if (a.fixed) { a.home = home; a.state = 'idle'; }
      else { a.state = 'walk'; a.t = 0; a.walkSp = d.ws || 1.3; }
    }
    for (const c of cars) {
      if (!c.net) continue; c.net = false; maxN = Math.max(maxN, c.nid || 0);
      if (c === player.inCar) continue;
      const by = [...NET.peers.values()].find(q => q.car && q.car[0] === c.nid);
      if (by) { c.remoteBy = by.id; c.ai = false; continue; }
      if (c.ai && c.driver && !c.parked) { let best = null, bd = 9; for (const L of LANES) { const k = hdNearestS(L, c.pos.x, c.pos.z); if (k.d < bd) { bd = k.d; best = { L, s: k.s }; } } if (best) { c.lane = best.L; c.s = best.s; } else { c.parked = true; c.ai = false; } }
    }
    NET.nextId = maxN + 1000; NET.rep.clear();
    netProgMark(); syncQuestNPCs(); syncQuestItems();
    toast('🌐 Adesso sei tu a far girare il mondo di Borso (host).', 4);
  } else {
    // non più host: il mondo arriva dal nuovo host, qui si tiene solo l'auto che si sta guidando
    NET.host = false; NET.pend = {};
    for (const a of agents.slice()) { if (a.mark) scene.remove(a.mark); removeAgent(a); }
    for (const id in QN) delete QN[id];
    for (const c of cars.slice()) { if (c === player.inCar) { c.net = true; netNid(c); continue; } scene.remove(c.mesh); cars.splice(cars.indexOf(c), 1); }
    for (const p of projectiles.slice()) scene.remove(p.mesh); projectiles.length = 0;
    player.helpers.length = 0; NET.rep.clear(); resetMS(); hideBossBar();
  }
  netHudUpdate();
}

/* ---------------- connessione ---------------- */
async function netWake(base, onStatus) { // il piano gratuito di Render spegne il server dopo 15 minuti: la prima chiamata lo risveglia
  const http = base.replace(/^ws/, 'http').replace(/\/ws$/, '') + '/health', t0 = Date.now();
  while (Date.now() - t0 < 100000) {
    try { const r = await fetch(http, { cache: 'no-store' }); if (r.ok) return true; } catch (e) { }
    onStatus(`Sveglio il server… ${Math.round((Date.now() - t0) / 1000)} s (la prima volta può volerci un minuto)`);
    await new Promise(r => setTimeout(r, 3000));
  }
  return false;
}
function netConnect(opts) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(netServerUrl()); let done = false;
    ws.onopen = () => ws.send(JSON.stringify({ t: 'join', proto: NET_PROTO, name: opts.name, look: opts.look, room: opts.room, create: !!opts.create, visible: !document.hidden }));
    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (!done) {
        if (m.t === 'welcome') { done = true; NET.ws = ws; resolve(m); return; }
        if (m.t === 'err') { done = true; ws.close(); reject(new Error(m.msg)); return; }
        return;
      }
      if (m.t === 'w' || m.t === 'p') netOnMessage(m); else NET.inbox.push(m); // stati subito, il resto nel fotogramma
    };
    ws.onerror = () => { if (!done) { done = true; reject(new Error('Server non raggiungibile.')); } };
    ws.onclose = () => { if (done && NET.ws === ws) netLost(); };
  });
}
async function netStart(opts) {
  netStatus('Collegamento…');
  if (!await netWake(netServerUrl(), s => netStatus(s))) throw new Error('Il server non risponde. Riprova tra poco.');
  const w = await netConnect(opts);
  // da qui: partita online. Salvataggio separato da quello in singolo.
  SAVE_KEY = 'borsoSim_mp';
  const had = loadGame();
  if (!had) { Object.assign(GS, { mission: 1, phase: 0, time: 10, day: 1, kills: 0, money: 30 }); player.unlocked = [true, false, false, false, false]; player.ammo = [Infinity, 0, 0, 0, 0]; player.weapon = 0; GS.q = defaultQ(); GS.boost = {}; player.maxHp = 100; }
  GS.introSeen = true;
  Object.assign(NET, { on: true, id: w.id, name: w.name, room: w.room, look: opts.look, host: w.host === w.id, opts });
  if (w.snap && w.snap.prog && (!NET.host || !had)) { netApplyProg(w.snap.prog); NET.gotSnap = true; }
  if (w.snap && w.snap.tm !== undefined) { GS.time = w.snap.tm; GS.day = w.snap.dy || GS.day; }
  netProgMark(); NET.expTm = GS.time; NET.expAt = performance.now();
  // Bepi col colore scelto
  scene.remove(player.a.c.root); player.a.c = makeChar(netLook(opts.look)); scene.add(player.a.c.root); player.model = null; setWeaponModel();
  if (!NET.host) { // il mondo lo manda l'host: via quello locale
    for (const a of agents.slice()) removeAgent(a);
    for (const c of cars.slice()) { scene.remove(c.mesh); cars.splice(cars.indexOf(c), 1); }
    fixedDone = true;
  }
  for (const p of w.peers) netAddPeer(p.id, p.name, p.look, p.last);
  addEventListener('beforeunload', () => { try { NET.ws.close(); } catch (e) { } });
  return w;
}
async function netLost() {
  if (!NET.on || NET.leaving) return;
  netHudUpdate('riconnessione…'); toast('🌐 Connessione persa, riprovo…', 4);
  for (let k = 0; k < 6; k++) {
    await new Promise(r => setTimeout(r, 1500 + k * 2000));
    try {
      const w = await netConnect({ name: NET.name, look: NET.look, room: NET.room });
      const wasHost = NET.host; NET.id = w.id;
      for (const id of [...NET.peers.keys()]) netRemovePeer(id);
      for (const p of w.peers) netAddPeer(p.id, p.name, p.look, p.last);
      NET.host = wasHost; netSetHost(w.host === w.id, w.snap);
      toast('🌐 Di nuovo online.'); netHudUpdate(); return;
    } catch (e) { if (/non trovata/.test(e.message)) break; }
  }
  NET.on = false; for (const id of [...NET.peers.keys()]) netRemovePeer(id);
  toast('🌐 Server irraggiungibile: continui da solo. Per tornare online ricarica la pagina.', 6); netHudUpdate();
}

/* ---------------- interfaccia: menu online, indicatore, chat ---------------- */
function netStatus(s, err) { const el = $('onStatus'); if (el) { el.textContent = s; el.style.color = err ? '#ff8a7a' : ''; } }
function netHudUpdate(extra) {
  const el = $('netHud'); if (!el) return;
  if (!NET.on) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  el.textContent = `🌐 ${NET.room} · ${NET.peers.size + 1} giocator${NET.peers.size ? 'i' : 'e'}${NET.host ? ' · host' : ''}${extra ? ' · ' + extra : ''}`;
  const pl = $('pausePlayers'); if (pl) pl.textContent = `Stanza ${NET.room}: ${[NET.name + ' (tu)'].concat([...NET.peers.values()].map(q => q.name)).join(', ')}`;
}
function netMapMarks(out) { for (const q of NET.peers.values()) if (q.st && !q.inside) out.push({ x: q.pos.x, z: q.pos.z, c: '#5ad0ff', s: 'p' }); }
function netChatLog(name, text) { toast(`💬 ${name}: ${text}`, 5); }
function netOpenChat() {
  if (!NET.on || GS.mode !== 'play') return;
  const box = $('chatBox'), inp = $('chatInput'); box.classList.remove('hidden'); inp.value = ''; inp.focus();
  if (document.pointerLockElement) { lockWanted = false; document.exitPointerLock(); }
  GS.mode = 'chat';
}
function netCloseChat(sendIt) {
  const box = $('chatBox'), inp = $('chatInput'); const text = inp.value.trim().slice(0, 140);
  box.classList.add('hidden'); inp.blur(); if (GS.mode === 'chat') GS.mode = 'play';
  if (sendIt && text) { netSendRaw({ t: 'chat', text }); say(player.a, text, 5); }
}
function netInitUI() {
  const look = (() => { try { return +sget('borsoSim_look') || 0; } catch (e) { return 0; } })();
  $('onName').value = sget('borsoSim_name') || '';
  const sw = $('onLooks'); NET_LOOKS.forEach((l, i) => { const b = document.createElement('button'); b.className = 'lookBtn' + (i === look ? ' on' : ''); b.style.background = '#' + l.shirt.toString(16).padStart(6, '0'); b.style.borderColor = '#' + l.hatColor.toString(16).padStart(6, '0'); b.onclick = () => { [...sw.children].forEach(x => x.classList.remove('on')); b.classList.add('on'); sset('borsoSim_look', String(i)); }; sw.appendChild(b); });
  const code = new URLSearchParams(location.search).get('room'); if (code) $('onRoom').value = code.toUpperCase();
  $('btnOnline').onclick = () => { initAudio(); $('title').classList.add('hidden'); $('online').classList.remove('hidden'); netStatus(''); };
  $('btnOnBack').onclick = () => { $('online').classList.add('hidden'); $('title').classList.remove('hidden'); };
  const go = async create => {
    const name = $('onName').value.trim().slice(0, 16) || 'Bepi', room = $('onRoom').value.trim().toUpperCase();
    if (!create && !/^[A-Z0-9]{4,6}$/.test(room)) { netStatus('Scrivi il codice della stanza (4 lettere).', true); return; }
    sset('borsoSim_name', name);
    const li = [...$('onLooks').children].findIndex(b => b.classList.contains('on'));
    $('btnOnCreate').disabled = $('btnOnJoin').disabled = true;
    try {
      await netStart({ name, look: NET_LOOKS[Math.max(0, li)], room, create });
      $('online').classList.add('hidden'); startPlay(false); netHudUpdate();
      if (NET.host) { banner(`Stanza ${NET.room}`, 'Dai il codice agli amici: entrano con «Gioca online»', 5); history.replaceState(null, '', '?room=' + NET.room); }
      else banner(`Stanza ${NET.room}`, 'Sei a Borso con gli amici', 3.5);
    } catch (e) { netStatus(e.message, true); }
    $('btnOnCreate').disabled = $('btnOnJoin').disabled = false;
  };
  $('btnOnCreate').onclick = () => go(true);
  $('btnOnJoin').onclick = () => go(false);
  $('chatInput').addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter') netCloseChat(true); else if (e.key === 'Escape') netCloseChat(false); });
  $('btnChat').onclick = () => netOpenChat();
  $('btnCopyRoom').onclick = () => { const u = location.origin + location.pathname + '?room=' + NET.room; (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(() => toast('Link copiato: mandalo agli amici.'), () => toast('Codice stanza: ' + NET.room)); };
  document.addEventListener('visibilitychange', () => { if (NET.on) netSendRaw({ t: 'vis', v: !document.hidden }); });
  addEventListener('keydown', e => { if (NET.on && GS.mode === 'play' && e.code === 'KeyT' && !e.repeat) { e.preventDefault(); e.stopImmediatePropagation(); netOpenChat(); } }, true);
}
