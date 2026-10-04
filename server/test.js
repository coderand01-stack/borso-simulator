/* Prova del server: due giocatori, stanza, inoltro, eventi mirati, cambio host. `npm test` */
'use strict';
process.env.PORT = process.env.PORT || '8799';
const { server } = require('./index.js');
const WebSocket = require('ws');
const URL = `ws://127.0.0.1:${process.env.PORT}/ws`;
const assert = (c, m) => { if (!c) { console.error('FALLITO:', m); process.exit(1); } console.log('ok -', m); };

function client() {
  const ws = new WebSocket(URL), q = [], waiters = [];
  ws.on('message', d => { const m = JSON.parse(d); const i = waiters.findIndex(w => w.f(m)); if (i >= 0) waiters.splice(i, 1)[0].r(m); else q.push(m); });
  return {
    ws, send: o => ws.send(JSON.stringify(o)),
    wait: (f, ms = 2000) => new Promise((r, j) => { const i = q.findIndex(f); if (i >= 0) return r(q.splice(i, 1)[0]); const w = { f, r }; waiters.push(w); setTimeout(() => j(new Error('timeout')), ms); }),
    open: () => new Promise(r => ws.on('open', r)),
  };
}

(async () => {
  await new Promise(r => setTimeout(r, 200));
  const a = client(); await a.open();
  a.send({ t: 'join', proto: 1, name: 'Zazza<script>', create: true, look: { shirt: 123, evil: 'x' } });
  const wa = await a.wait(m => m.t === 'welcome');
  assert(wa.host === wa.id && /^[A-Z0-9]{4}$/.test(wa.room), 'crea stanza ed è host');
  assert(wa.name === 'Zazzascript', 'nome ripulito');

  const b = client(); await b.open();
  b.send({ t: 'join', proto: 1, name: 'Bepi', room: wa.room.toLowerCase() });
  const wb = await b.wait(m => m.t === 'welcome');
  assert(wb.host === wa.id && wb.peers.length === 1 && wb.peers[0].look.shirt === 123 && wb.peers[0].look.evil === undefined, 'entra nella stanza, vede il primo giocatore');
  await a.wait(m => m.t === 'peer+' && m.id === wb.id);

  b.send({ t: 'p', x: 1, z: 2 });
  const pa = await a.wait(m => m.t === 'p');
  assert(pa.id === wb.id && pa.x === 1, 'stato del giocatore inoltrato');

  a.send({ t: 'w', k: 1 }); const w = await b.wait(m => m.t === 'w'); assert(w.k === 1, 'mondo dall\'host inoltrato');
  b.send({ t: 'w', k: 2 }); await a.wait(m => m.t === 'w', 300).then(() => assert(false, 'il mondo di un non-host non deve passare'), () => assert(true, 'mondo da non-host ignorato'));

  b.send({ t: 'ev', to: 'host', e: 'hit', d: { n: 5 } }); const ev = await a.wait(m => m.t === 'ev'); assert(ev.from === wb.id && ev.e === 'hit', 'evento all\'host');
  a.send({ t: 'snap', d: { mission: 3 } });
  a.send({ t: 'vis', v: false }); const h = await b.wait(m => m.t === 'host'); assert(h.id === wb.id && h.snap.mission === 3, 'host in secondo piano: passa all\'altro con lo stato salvato');

  const c = client(); await c.open(); c.send({ t: 'join', proto: 1, name: 'X', room: 'ZZZZ' }); const e = await c.wait(m => m.t === 'err'); assert(e.code === 'noroom', 'stanza inesistente');
  b.ws.close(); const hh = await a.wait(m => m.t === 'host' && m.id === wa.id); assert(hh.id === wa.id, 'l\'host esce: torna al primo');

  const r = await fetch(`http://127.0.0.1:${process.env.PORT}/health`).then(r => r.json()); assert(r.ok && r.players === 1, 'health');
  console.log('tutto ok'); a.ws.close(); c.ws.close(); server.close(); process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
