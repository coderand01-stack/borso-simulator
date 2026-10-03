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

