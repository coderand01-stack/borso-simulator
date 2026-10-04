/* Borso Simulator — server multiplayer.
 *
 * Il mondo condiviso lo simula uno dei giocatori (l'"host" della stanza): il server non conosce le regole del
 * gioco, tiene solo le stanze, sceglie l'host (e lo sostituisce se esce o mette il gioco in secondo piano),
 * inoltra i messaggi e conserva in memoria l'ultimo stato salvato dall'host (avanzamento e orologio), così chi
 * entra dopo o il nuovo host ripartono da lì.
 *
 * Variabili d'ambiente:
 *   PORT              porta HTTP (Render la imposta da sé)
 *   ALLOWED_ORIGINS   origini ammesse, separate da virgola (es. https://utente.github.io). Vuoto = tutte.
 *   MAX_PLAYERS       giocatori per stanza (default 6)
 */
'use strict';
const http = require('http');
const { WebSocketServer } = require('ws');

const PORT = +process.env.PORT || 8787;
const ORIGINS = (process.env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim().replace(/\/$/, '')).filter(Boolean);
const MAX_PLAYERS = Math.max(2, +process.env.MAX_PLAYERS || 6);
const ROOM_TTL = 10 * 60 * 1000;      // una stanza vuota resta in memoria 10 minuti (per chi si riconnette)
const PROTO = 1;
const LIMIT = { snap: 256 * 1024, other: 64 * 1024 };
const LOOK_KEYS = ['shirt', 'sleeve', 'pants', 'hat', 'hatColor', 'skin', 'shoes', 'hair', 'mustache', 'beard', 'glasses', 'vest', 'scale'];

const rooms = new Map();
let nextId = 1;
const started = Date.now();

/* ---------------- HTTP: stato e sveglia (Render spegne i servizi gratuiti inattivi) ---------------- */
const server = http.createServer((req, res) => {
  const url = (req.url || '/').split('?')[0];
  if (url === '/' || url === '/health') {
    let players = 0; for (const r of rooms.values()) players += r.players.size;
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ ok: true, game: 'borso-simulator', proto: PROTO, rooms: rooms.size, players, uptime: Math.round((Date.now() - started) / 1000) }));
    return;
  }
  res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('not found');
});

function originOk(origin) {
  if (!ORIGINS.length || !origin) return true; // nessuna lista = tutti; i client non-browser non mandano Origin
  const o = origin.replace(/\/$/, '');
  return ORIGINS.includes(o) || /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(o);
}

const wss = new WebSocketServer({ noServer: true, maxPayload: 512 * 1024 });
server.on('upgrade', (req, socket, head) => {
  if ((req.url || '').split('?')[0] !== '/ws' || !originOk(req.headers.origin)) { socket.write('HTTP/1.1 403 Forbidden\r\n\r\n'); socket.destroy(); return; }
  wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws, req));
});

/* ---------------- utilità ---------------- */
const CODE_CH = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
function newCode() {
  for (let k = 0; k < 50; k++) { let c = ''; for (let i = 0; i < 4; i++) c += CODE_CH[Math.floor(Math.random() * CODE_CH.length)]; if (!rooms.has(c)) return c; }
  return String(Date.now() % 100000);
}
const clean = (s, n) => String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f<>]/g, '').trim().slice(0, n);
function cleanLook(l) {
  const o = {}; if (!l || typeof l !== 'object') return o;
  for (const k of LOOK_KEYS) { const v = l[k]; if (typeof v === 'number' && isFinite(v)) o[k] = v; else if (typeof v === 'boolean') o[k] = v; else if (typeof v === 'string' && v.length < 16) o[k] = v; }
  return o;
}
function send(p, obj) { if (p.ws.readyState === 1) p.ws.send(typeof obj === 'string' ? obj : JSON.stringify(obj)); }
function broadcast(room, obj, except) { const s = typeof obj === 'string' ? obj : JSON.stringify(obj); for (const p of room.players.values()) if (p !== except) send(p, s); }
function peerInfo(p) { return { id: p.id, name: p.name, look: p.look, last: p.last }; }

// host: il primo arrivato con la scheda in primo piano; se l'host va in secondo piano passa a un altro
function electHost(room, avoidCurrent) {
  const cur = room.players.get(room.host);
  if (cur && cur.visible && !avoidCurrent) return;
  const list = [...room.players.values()].sort((a, b) => a.joinedAt - b.joinedAt);
  const next = list.find(o => o.visible && o !== cur) || cur || list[0] || null; // nessuno in primo piano: resta com'è
  const id = next ? next.id : null;
  if (id === room.host) return;
  room.host = id;
  if (id) broadcast(room, { t: 'host', id, snap: room.snap });
}

/* ---------------- connessioni ---------------- */
wss.on('connection', ws => {
  const p = { id: 'p' + (nextId++), ws, name: 'Bepi', look: {}, last: null, visible: true, joinedAt: Date.now(), room: null, tokens: 200, tokT: Date.now(), dropped: 0 };
  ws.on('pong', () => { ws._dead = false; });
  ws.on('message', (buf, isBinary) => {
    if (isBinary) return;
    // limite di frequenza: 200 messaggi di scorta, 120 al secondo
    const now = Date.now(); p.tokens = Math.min(200, p.tokens + (now - p.tokT) * 0.12); p.tokT = now;
    if (p.tokens < 1) { if (++p.dropped > 600) ws.close(1008, 'troppi messaggi'); return; }
    p.tokens -= 1;
    let m; try { m = JSON.parse(buf.toString()); } catch (e) { return; }
    if (!m || typeof m.t !== 'string') return;
    if (buf.length > (m.t === 'snap' ? LIMIT.snap : LIMIT.other)) return;
    handle(p, m, buf);
  });
  ws.on('close', () => leave(p));
  ws.on('error', () => {});
});

function handle(p, m, buf) {
  if (m.t === 'ping') { send(p, { t: 'pong', c: m.c, s: Date.now() }); return; }
  if (!p.room) {
    if (m.t !== 'join') return;
    if (m.proto !== PROTO) { send(p, { t: 'err', code: 'proto', msg: 'Versione del gioco diversa da quella del server: ricarica la pagina.' }); return; }
    p.name = clean(m.name, 16) || 'Bepi'; p.look = cleanLook(m.look); p.visible = m.visible !== false;
    let room;
    if (m.create) {
      room = { code: newCode(), players: new Map(), host: null, snap: null, emptySince: 0 };
      rooms.set(room.code, room);
    } else {
      room = rooms.get(clean(m.room, 8).toUpperCase());
      if (!room) { send(p, { t: 'err', code: 'noroom', msg: 'Stanza non trovata. Controlla il codice.' }); return; }
      if (room.players.size >= MAX_PLAYERS) { send(p, { t: 'err', code: 'full', msg: `Stanza piena (massimo ${MAX_PLAYERS} giocatori).` }); return; }
    }
    if ([...room.players.values()].some(o => o.name.toLowerCase() === p.name.toLowerCase())) p.name = (p.name.slice(0, 13) + ' ' + (room.players.size + 1)).trim();
    p.room = room; room.players.set(p.id, p); room.emptySince = 0;
    if (!room.host || !room.players.has(room.host)) room.host = p.id;
    send(p, { t: 'welcome', id: p.id, name: p.name, room: room.code, host: room.host, proto: PROTO, max: MAX_PLAYERS, peers: [...room.players.values()].filter(o => o !== p).map(peerInfo), snap: room.snap });
    broadcast(room, { t: 'peer+', id: p.id, name: p.name, look: p.look }, p);
    log(`${room.code}: entra ${p.name} (${p.id}), ${room.players.size} giocatori, host ${room.host}`);
    return;
  }
  const room = p.room, isHost = room.host === p.id;
  switch (m.t) {
    case 'p': { // stato del giocatore (12 al secondo)
      m.id = p.id; p.last = m; broadcast(room, m, p); break;
    }
    case 'w': { // stato del mondo dall'host (10 al secondo)
      if (isHost) broadcast(room, buf.toString(), p); break;
    }
    case 'snap': { // avanzamento condiviso, salvato dall'host ogni pochi secondi
      if (isHost && m.d && typeof m.d === 'object') room.snap = m.d; break;
    }
    case 'ev': { // eventi: a tutti, all'host o a un giocatore
      m.from = p.id; const s = JSON.stringify(m);
      if (m.to === 'host') { const h = room.players.get(room.host); if (h && h !== p) send(h, s); }
      else if (m.to && m.to !== 'all') { const o = room.players.get(m.to); if (o) send(o, s); }
      else broadcast(room, s, p);
      break;
    }
    case 'chat': {
      const text = clean(m.text, 140); if (text) broadcast(room, { t: 'chat', id: p.id, name: p.name, text }, p); break;
    }
    case 'vis': {
      p.visible = !!m.v; electHost(room, isHost && !p.visible); break;
    }
    case 'look': {
      p.look = cleanLook(m.look); broadcast(room, { t: 'look', id: p.id, look: p.look }, p); break;
    }
  }
}

function leave(p) {
  const room = p.room; if (!room) return;
  room.players.delete(p.id); p.room = null;
  broadcast(room, { t: 'peer-', id: p.id });
  if (room.host === p.id) { room.host = null; electHost(room); }
  if (!room.players.size) room.emptySince = Date.now();
  log(`${room.code}: esce ${p.name} (${p.id}), ${room.players.size} giocatori, host ${room.host}`);
}

function log(s) { console.log(new Date().toISOString().slice(11, 19), s); }

/* ---------------- pulizia: connessioni morte e stanze vuote ---------------- */
setInterval(() => {
  for (const ws of wss.clients) { if (ws._dead) { ws.terminate(); continue; } ws._dead = true; ws.ping(); }
  const now = Date.now();
  for (const [code, r] of rooms) if (!r.players.size && r.emptySince && now - r.emptySince > ROOM_TTL) rooms.delete(code);
}, 20000);

server.listen(PORT, () => log(`Borso Simulator server in ascolto sulla porta ${PORT}${ORIGINS.length ? ' (origini: ' + ORIGINS.join(', ') + ')' : ''}`));
module.exports = { server, rooms };
