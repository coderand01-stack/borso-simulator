"""Multiplayer hooks for docs/index.html, applied by tools/make_hd.py after the HD patches.

The network layer itself is tools/hd_net.js; here the original game code gets the few hooks it needs
(who "the player" is for the AI, requests from guests to the host, events broadcast by the host, the
host keeping the world alive while its own player is inside, in a dialog or paused).
Exec'd by make_hd.py with `s`, `rep`, `ROOT`, `os` in scope.
"""

# ---- stato di rete: dichiarato presto, prima che il gioco crei il giocatore
s = rep(s, "const HDM = { pendingChars: [], cars: {} };",
        "const HDM = { pendingChars: [], cars: {} };\n"
        "const NET = { on: false, host: false, id: null, ws: null, room: '', peers: new Map(), rep: new Map(), inbox: [], out: {}, prog: {}, pend: {}, focus: null, sim: false, toastTo: null, hitBy: null, remoteCall: false, making: false, nextId: 1, tick: 0, sentA: new Set(), sentC: new Set() };\n"
        "const netGuest = () => NET.on && !NET.host, netHost = () => NET.on && NET.host;")

# ---- angoli: calcolo diretto invece del ciclo (un valore enorme o infinito bloccava la pagina)
s = rep(s, "function angDiff(a, b) { let d = b - a; while (d > Math.PI) d -= TAU; while (d < -Math.PI) d += TAU; return d; }",
        "function angDiff(a, b) { let d = (b - a) % TAU; if (d > Math.PI) d -= TAU; else if (d < -Math.PI) d += TAU; return isFinite(d) ? d : 0; }")

# ---- menu online, indicatore, chat
s = rep(s, '    <button class="bsign alt" id="btnHelp">Comandi</button>\n  </div>',
        '    <button class="bsign" id="btnOnline" style="background:var(--grappa);outline-color:var(--grappa)">🌐 Gioca online</button>\n'
        '    <button class="bsign alt" id="btnHelp">Comandi</button>\n  </div>')
s = rep(s, '<div id="help" class="overlay hidden"',
        '<div id="online" class="overlay hidden" style="background:rgba(8,12,18,.78)">\n'
        '  <div class="panel onlinePanel">\n'
        '    <h3>Borso con gli amici</h3>\n'
        '    <p style="margin:0 0 10px">Crea una stanza e dai il codice agli amici, oppure entra con il loro codice. Il mondo è condiviso: maranza, ladri, missioni e quest. Schei e armi restano tuoi.</p>\n'
        '    <label>Il tuo nome<input id="onName" maxlength="16" placeholder="Bepi" autocomplete="nickname"></label>\n'
        '    <label>Colori di Bepi</label><div id="onLooks"></div>\n'
        '    <label>Codice stanza<input id="onRoom" maxlength="6" placeholder="es. B7KQ" autocapitalize="characters" style="text-transform:uppercase"></label>\n'
        '    <div id="onStatus"></div>\n'
        '  </div>\n'
        '  <div class="brownbtns" style="margin-top:12px">\n'
        '    <button class="bsign" id="btnOnCreate">Crea stanza</button>\n'
        '    <button class="bsign" id="btnOnJoin" style="background:var(--grappa);outline-color:var(--grappa)">Entra</button>\n'
        '    <button class="bsign alt" id="btnOnBack">Indietro</button>\n'
        '  </div>\n'
        '</div>\n\n'
        '<div id="help" class="overlay hidden"')
s = rep(s, '  <div id="toasts"></div>',
        '  <div id="toasts"></div>\n'
        '  <div id="netHud" class="chip hidden"></div>\n'
        '  <button id="btnChat" class="netChatBtn">💬</button>\n'
        '  <div id="chatBox" class="hidden"><input id="chatInput" maxlength="140" placeholder="Scrivi e premi Invio (Esc per chiudere)"></div>')
s = rep(s, '    <button class="bsign alt" id="btnJour2">Diario delle missioni</button>',
        '    <div id="pausePlayers" class="netOnly"></div>\n'
        '    <button class="bsign alt netOnly" id="btnCopyRoom">🔗 Copia il link della stanza</button>\n'
        '    <button class="bsign alt" id="btnJour2">Diario delle missioni</button>')
s = rep(s, '.panel h3{', '.onlinePanel label{display:block;font-weight:800;color:var(--prosecco);margin:10px 0 4px}\n'
        '.onlinePanel input{display:block;width:100%;box-sizing:border-box;margin-top:4px;font:inherit;font-size:20px;padding:8px 10px;border-radius:8px;border:2px solid #555;background:#f7f7f2;color:#141414}\n'
        '#onLooks{display:flex;gap:10px;flex-wrap:wrap}.lookBtn{width:44px;height:44px;border-radius:50%;border:6px solid #333;cursor:pointer}.lookBtn.on{outline:3px solid #fff;outline-offset:2px}\n'
        '#onStatus{min-height:22px;margin-top:10px;font-weight:700}\n'
        '#netHud{position:absolute;left:50%;transform:translateX(-50%);top:calc(var(--st) + 10px);font-size:15px;pointer-events:none}\n'
        '.netChatBtn{position:absolute;right:16px;top:calc(var(--st) + 150px);width:44px;height:44px;border-radius:50%;border:2px solid #fff;background:rgba(12,16,22,.7);font-size:20px;display:none;pointer-events:auto}\n'
        'body.net .netChatBtn{display:block}#pausePlayers{display:none;text-align:center;font-weight:700}body.net #pausePlayers{display:block}.netOnly{display:none}body.net .netOnly{display:block}\n'
        '#chatBox{position:absolute;left:50%;transform:translateX(-50%);bottom:calc(var(--sb) + 22%);width:min(560px,92vw);pointer-events:auto}\n'
        '#chatBox input{width:100%;box-sizing:border-box;font:inherit;font-size:19px;padding:10px 12px;border-radius:8px;border:2px solid var(--prosecco);background:rgba(12,16,22,.9);color:#fff}\n'
        '.bubble.peer{background:#dff3ff}\n'
        '.panel h3{')

# ---- salvataggio separato online
s = rep(s, "const SAVE_KEY = 'borsoSim_v1';", "let SAVE_KEY = 'borsoSim_v1'; // online: 'borsoSim_mp'")

# ---- "il giocatore" per l'IA dell'host è quello su cui l'agente è concentrato
s = rep(s, "function playerPos() { return player.inCar ? player.inCar.pos : player.a.pos; }",
        "function playerPos() { if (NET.focus) return NET.focus.pos; return player.inCar ? player.inCar.pos : player.a.pos; }")
s = rep(s, "function nearestFoeFor(a, maxD) { // what enemies attack: player or helpers\n",
        "function nearestFoeFor(a, maxD) { // what enemies attack: player or helpers\n  if (NET.on) return netNearestFoe(a, maxD);\n")
s = rep(s, "    if (foe.isPlayer) hurtPlayer(cfg.melee); else damage(foe.agent, cfg.melee, 'enemy');",
        "    if (foe.isPlayer) netHurtFoe(foe, cfg.melee); else damage(foe.agent, cfg.melee, 'enemy');")
s = rep(s, "const lead = foe.isPlayer && player.inCar ? player.inCar.fwd() : null,", "const lead = foe.isPlayer && !foe.remote && player.inCar ? player.inCar.fwd() : null,")
s = rep(s, "if (foe.isPlayer) hurtPlayer(16); else damage(foe.agent, 25, 'enemy');", "if (foe.isPlayer) netHurtFoe(foe, 16); else damage(foe.agent, 25, 'enemy');")
s = rep(s, "if (foe.isPlayer) hurtPlayer(14); else damage(foe.agent, 20, 'enemy');", "if (foe.isPlayer) netHurtFoe(foe, 14); else damage(foe.agent, 20, 'enemy');")
s = rep(s, "if (foe && !player.dead && (dp < aggro || a.alerted))", "if (foe && !fpDead() && (dp < aggro || a.alerted))")
s = rep(s, "const spotted = (!player.dead && dp <", "const spotted = (!fpDead() && dp <")
s = rep(s, "yaw = player.inCar ? player.inCar.heading : player.a.yaw;\n    const fx = pp.x - Math.sin(yaw) * 2.6", "yaw = fpYaw();\n    const fx = pp.x - Math.sin(yaw) * 2.6")
s = rep(s, "if (dp < 6 && a.chatT <= 0 && !player.inCar)", "if (dp < 6 && a.chatT <= 0 && !fpInCar())")
s = rep(s, "  if (player.inCar) { a.c.root.visible = false; a.pos.copy(pp); a.hid = true; return; }", "  if (fpInCar()) { a.c.root.visible = false; a.pos.copy(pp); a.hid = true; return; }")
s = rep(s, "const i = Object.keys(QN).indexOf(a.qid) % 4, yaw = player.a.yaw, side", "const i = Object.keys(QN).indexOf(a.qid) % 4, yaw = fpYaw(), side")
s = rep(s, "if (d < 1.6 && !player.inCar) { a.fleeing = false; a.speed = 0; talk([",
        "if (d < 1.6 && !fpInCar()) { a.fleeing = false; a.speed = 0; if (NET.focus && NET.focus.peer) netEv(NET.focus.id, 'sofia'); else talk([")
s = rep(s, "function nearPlayer(i) { const p = playerPos(), a = player.a.yaw + Math.PI", "function nearPlayer(i) { const p = playerPos(), a = fpYaw() + Math.PI")
s = rep(s, "function makeFollower(a) { a.follower = true; a.fixed = false; a.state = 'follow'; }",
        "function makeFollower(a) { a.follower = true; a.fixed = false; a.state = 'follow'; if (NET.on && !a.net) a.followId = netNearestPlayerId(a.pos); }")
# le auto frenano anche per gli altri giocatori
s = rep(s, "  if (!player.dead && test(pp, player.inCar ? 2.6 : 1.8)) { block = true; blocker = 'player'; }",
        "  if (!player.dead && test(pp, player.inCar ? 2.6 : 1.8)) { block = true; blocker = 'player'; }\n"
        "  if (!block && NET.on) for (const q of NET.peers.values()) if (q.st && !q.inside && test(q.pos, q.car ? 2.6 : 1.8)) { block = true; break; }")

# ---- ospite: chiede all'host di creare i personaggi; le copie non si simulano
s = rep(s, "function spawnAgent(kind, preset, x, z) { const a = new Agent(kind, preset, x, z); agents.push(a); return a; }",
        "function spawnAgent(kind, preset, x, z) { if (netGuest() && !NET.making) return netSpawnProxy('agent', { kind, preset, x, z }); const a = new Agent(kind, preset, x, z); agents.push(a); return a; }")
s = rep(s, "function spawnMaranza(x, z, o = {}) {\n", "function spawnMaranza(x, z, o = {}) {\n  if (netGuest()) return netSpawnProxy('maranza', { x, z, o });\n")
s = rep(s, "function spawnLadro(x, z, house, o = {}) {\n", "function spawnLadro(x, z, house, o = {}) {\n  if (netGuest()) return netSpawnProxy('ladro', { x, z, o, th: houses.indexOf(house) });\n")
s = rep(s, "function damage(a, amt, src) {\n  if (!a || a.dead) return;\n",
        "function damage(a, amt, src) {\n  if (!a || a.dead) return;\n"
        "  if (netGuest() && a.net) { netHitReq(a, amt, src); a.hitT = 0.18; return; }\n"
        "  if (netHost()) a._lastBy = NET.hitBy || (src === 'helper' && NET.focus && NET.focus.id) || NET.id;\n")
# premio a chi ha colpito (online), il resto della morte resta all'host
s = rep(s, "  GS.kills++;\n  const cash = ", "  const cash = ")
s = rep(s, "  GS.money += cash; if (GS.q.perm.santino) GS.money += Math.ceil(cash * 0.25);\n  if (a.kind === 'ladro') GS.ladriStopped++;\n"
           "  toast(a.kind === 'ladro' ? `Ladro fermato! +${cash} schei (e una dentiera restituita)` : a.boss ? `${a.name} rieducato! +${cash} schei` : `Maranza rieducato +${cash} schei`);",
        "  if (a.kind === 'ladro') GS.ladriStopped++;\n"
        "  if (!netRewardRemote(a, cash)) { const sim0 = NET.sim; NET.sim = false; GS.kills++;\n"
        "  GS.money += cash; if (GS.q.perm.santino) GS.money += Math.ceil(cash * 0.25);\n"
        "  toast(a.kind === 'ladro' ? `Ladro fermato! +${cash} schei (e una dentiera restituita)` : a.boss ? `${a.name} rieducato! +${cash} schei` : `Maranza rieducato +${cash} schei`); NET.sim = sim0; }")
s = rep(s, "  if (src === 'player' && Math.random() < 0.25) setTimeout(() => say(player.a,", "  if (src === 'player' && (!NET.on || a._lastBy === NET.id) && Math.random() < 0.25) setTimeout(() => say(player.a,")

# ---- proiettili: quelli degli altri si vedono ma non fanno danno; quelli nemici li controlla ognuno su di sé
s = rep(s, "  projectiles.push(pr); return pr;", "  projectiles.push(pr); if (NET.on && !opt.net) netProjOut(type, ox, oy, oz, vx, vy, vz, dmg, owner, opt); return pr;")
s = rep(s, "      } else {\n        // enemy projectiles -> player & helpers\n        if (!player.dead) {",
        "      } else if (pr.owner === 'enemy') {\n        // enemy projectiles -> player & helpers\n        if (!player.dead && !GS.inside) {")
s = rep(s, "  for (const a of agents.slice()) {\n    const d = Math.hypot(a.pos.x - x, a.pos.z - z); if (d > r || a.dead) continue;",
        "  if (owner !== 'remote') for (const a of agents.slice()) {\n    const d = Math.hypot(a.pos.x - x, a.pos.z - z); if (d > r || a.dead) continue;")
s = rep(s, "  if (owner !== 'player' && dpl < r && !player.inCar) hurtPlayer(dmg * 0.3);", "  if (owner !== 'player' && owner !== 'remote' && dpl < r && !player.inCar && !GS.inside) hurtPlayer(dmg * 0.3);")

# ---- raccolte condivise
s = rep(s, "  pickups.push({ type, g, x, z, y, t: 45 });",
        "  const pk = { type, g, x, z, y, t: 45 }; pickups.push(pk);\n"
        "  if (netHost() && !NET.remoteCall) { pk.nid = NET.nextId++; netEv('all', 'pk+', { n: pk.nid, ty: type, x: Math.round(x * 100) / 100, z: Math.round(z * 100) / 100 }); }")
s = rep(s, "      sfx('pickup'); scene.remove(k.g); pickups.splice(i, 1); continue;",
        "      sfx('pickup'); if (NET.on && k.nid) netEv(NET.host ? 'all' : 'host', 'pk-', { n: k.nid }); scene.remove(k.g); pickups.splice(i, 1); continue;")
s = rep(s, "function questDrop(id, x, z) { if (id === 'grappa1803' && (GS.q.grappa.s > 0 || GS.q.inv.grappa1803)) return;",
        "function questDrop(id, x, z) { if (id === 'grappa1803' && (GS.q.grappa.s > 0 || GS.q.inv.grappa1803)) return; if (netHost() && !NET.remoteCall) netEv('all', 'qdrop', { id, x, z });")

# ---- messaggi della simulazione dell'host: li vedono tutti
s = rep(s, "function say(a, text, dur = 3) {\n  if (!a || a.removed) return;\n",
        "function say(a, text, dur = 3) {\n  if (!a || a.removed) return;\n"
        "  if (NET.sim && NET.host && a !== player.a && !a._proxy && a.kind !== 'peer' && agents.includes(a)) netEv('all', 'say', { n: netNid(a), tx: text, du: dur });\n")
s = rep(s, "function toast(msg, dur = 3.4) {\n",
        "function toast(msg, dur = 3.4) {\n"
        "  if (NET.toastTo) { netEv(NET.toastTo, 'toast', { tx: msg, du: dur }); return; }\n"
        "  if (NET.sim && NET.host) netEv('all', 'toast', { tx: msg, du: dur });\n")
s = rep(s, "function radio(who, txt, dur = 5) { $('radioWho')",
        "function radio(who, txt, dur = 5) { if (NET.sim && NET.host) netEv('all', 'radio', { w: who, tx: txt, du: dur }); $('radioWho')")
s = rep(s, "function sfx(name, pos, vol = 1) {\n",
        "function sfx(name, pos, vol = 1) {\n"
        "  if (NET.sim && NET.host && pos && pos.x !== undefined && name !== 'blip') netEv('all', 'sfx', { nm: name, x: Math.round(pos.x * 10) / 10, z: Math.round(pos.z * 10) / 10 });\n")

# ---- missioni: le decide l'host, i premi li prendono tutti
s = rep(s, "function completeMission(m) {\n  resetMS(); sfx('win');", "function completeMission(m) {\n  if (netHost() && !NET.remoteCall) netEv('all', 'mdone', { m });\n  resetMS(); sfx('win');")
s = rep(s, "function startEnding() {\n  if (GS.mode !== 'play') return; GS.mode = 'cine';",
        "function startEnding() {\n  if (GS.mode !== 'play') return; if (NET.on && !NET.remoteCall) netEv('all', 'ending'); GS.mode = 'cine';")
s = rep(s, "    if (!MS.spawned && Math.hypot(pp.x - L.x, pp.z - L.z) < 75) spawnMissionWave(m);",
        "    if (!MS.spawned && (NET.on ? netMinDist(L.x, L.z) : Math.hypot(pp.x - L.x, pp.z - L.z)) < 75) spawnMissionWave(m);")
s = rep(s, "if (GS.phase === 2 && !MS.spawned && Math.hypot(pp.x - LOC.cassanego.x, pp.z - LOC.cassanego.z) < 85)",
        "if (GS.phase === 2 && !MS.spawned && (NET.on ? netMinDist(LOC.cassanego.x, LOC.cassanego.z) : Math.hypot(pp.x - LOC.cassanego.x, pp.z - LOC.cassanego.z)) < 85)")
s = rep(s, "Bussa alle porte e recluta la ronda (${player.helpers.length}/2)", "Bussa alle porte e recluta la ronda (${netHelperCount()}/2)")

# ---- comparse e traffico: distanze da tutti i giocatori
s = rep(s, "    const d = Math.hypot(a.pos.x - pp.x, a.pos.z - pp.z);\n    if (d > 165 && ",
        "    const d = NET.on ? netMinDist(a.pos.x, a.pos.z) : Math.hypot(a.pos.x - pp.x, a.pos.z - pp.z);\n    if (d > 165 && ")
s = rep(s, "  for (const c of cars.slice()) { if (!c.ai || c === player.inCar) continue; const d = Math.hypot(c.pos.x - pp.x, c.pos.z - pp.z); if (d > 230)",
        "  for (const c of cars.slice()) { if (!c.ai || c === player.inCar || c.remoteBy) continue; const d = NET.on ? netMinDist(c.pos.x, c.pos.z) : Math.hypot(c.pos.x - pp.x, c.pos.z - pp.z); if (d > 230)")
s = rep(s, "  for (const c of cars.slice()) { if (c.parked && c !== player.inCar && Math.hypot(c.pos.x - pp.x, c.pos.z - pp.z) > 260)",
        "  for (const c of cars.slice()) { if (c.parked && c !== player.inCar && !c.remoteBy && !c.isBepi && (NET.on ? netMinDist(c.pos.x, c.pos.z) : Math.hypot(c.pos.x - pp.x, c.pos.z - pp.z)) > 260)")

# ---- notte e giorno: le comparse le gestisce l'host
s = rep(s, "  for (const a of agents.slice()) if (a.kind === 'maranza' && !a.mission && !a.dead) {", "  if (!netGuest()) for (const a of agents.slice()) if (a.kind === 'maranza' && !a.mission && !a.dead) {")
s = rep(s, "  for (const a of agents) if (a.kind === 'ladro' && !a.dead && !a.mission) { a.state = 'flee'; a.robbing = false; }",
        "  if (!netGuest()) for (const a of agents) if (a.kind === 'ladro' && !a.dead && !a.mission) { a.state = 'flee'; a.robbing = false; }")

# ---- ronda: l'ospite chiede all'host; ognuno al massimo tre compaesani
s = rep(s, "    if (player.helpers.length >= 3) { toast(", "    if (netMyHelpers() >= 3) { toast(")
s = rep(s, "    if (r < 0.6) { recruitHelper(h); missionOnRecruit(); }",
        "    if (r < 0.6) { if (netGuest()) netEv('host', 'recruit', { hi: houses.indexOf(h) }); else { recruitHelper(h); missionOnRecruit(); } }")
s = rep(s, "  for (const h of player.helpers.slice()) helperGoHome(h, false);\n  hideBossBar(); sfx('death');",
        "  for (const h of player.helpers.slice()) if (!h.owner) helperGoHome(h, false);\n  hideBossBar(); sfx('death');")

# ---- auto: una per giocatore, l'host sa chi guida cosa
s = rep(s, "function enterCar(c) {\n  if (c.driver && c.ai) {", "function enterCar(c) {\n  if (NET.on && !netCarTake(c)) return;\n  if (c.driver && c.ai) {")

# ---- quest: i personaggi li crea l'host; Sofia la fa scappare l'host
s = rep(s, "function syncQuestNPCs() {\n", "function syncQuestNPCs() {\n  if (netGuest()) return;\n")
s = rep(s, "else if (id === 'sofia') { if (a) { a.fleeing = true; a.fleeT = 40; a.restT = -1; }",
        "else if (id === 'sofia') { if (a) { if (netGuest()) netEv('host', 'acmd', { n: a.nid, s: { fleeing: true, fleeT: 40, restT: -1 } }); else { a.fleeing = true; a.fleeT = 40; a.restT = -1; } }")
s = rep(s, "  for (const s of LOC.stops || []) out.push({ x: s.x, z: s.z, c: '#4a8aff', s: 'b' });",
        "  for (const s of LOC.stops || []) out.push({ x: s.x, z: s.z, c: '#4a8aff', s: 'b' });\n  if (NET.on) netMapMarks(out);")

# ---- avvio della partita: l'ospite non crea il mondo
s = rep(s, "  GS.night = isNightT(GS.time); spawnFixed(); syncQuestNPCs(); syncQuestItems();\n  for (let i = 0; i < (LOWQ ? 5 : 8); i++) spawnCiv(a.pos, true);\n"
           "  while (cars.filter(c => c.ai).length < (LOWQ ? 5 : 8)) { if (!spawnTrafficCar(false)) break; }",
        "  GS.night = isNightT(GS.time); if (!netGuest()) spawnFixed(); syncQuestNPCs(); syncQuestItems();\n  if (!netGuest()) for (let i = 0; i < (LOWQ ? 5 : 8); i++) spawnCiv(a.pos, true);\n"
           "  if (!netGuest()) while (cars.filter(c => c.ai).length < (LOWQ ? 5 : 8)) { if (!spawnTrafficCar(false)) break; }\n"
           "  document.body.classList.toggle('net', NET.on);")
s = rep(s, "  if (!cars.some(c => c.isBepi)) {", "  if (!netGuest() && !cars.some(c => c.isBepi)) {")

# ---- ciclo principale: rete a ogni fotogramma; l'ospite non simula il mondo, l'host lo simula sempre
s = rep(s, "function loop(now) {\n  requestAnimationFrame(loop);\n  const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;\n",
        "function loop(now) {\n  requestAnimationFrame(loop);\n  const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;\n  if (NET.on) netFrame(dt);\n")
s = rep(s, "      const pp = playerPos();\n      for (const a of agents.slice()) {\n        if (a.removed) continue;\n        const far = Math.abs(a.pos.x - pp.x) + Math.abs(a.pos.z - pp.z) > 200;",
        "      const pp = playerPos();\n      if (NET.on) { if (NET.host) netAgentsSim(dt); } else for (const a of agents.slice()) {\n        if (a.removed) continue;\n        const far = Math.abs(a.pos.x - pp.x) + Math.abs(a.pos.z - pp.z) > 200;")
s = rep(s, "      for (const c of cars) if (c !== player.inCar) updateCarAI(c, dt);\n      if (!player.inCar) engineSound(-1);\n"
           "      updateProjectiles(dt); updatePickups(dt); updateMission(dt); updateSpawns(dt); updateQuests(dt);",
        "      for (const c of cars) if (c !== player.inCar && !c.remoteBy) updateCarAI(c, dt);\n      if (!player.inCar) engineSound(-1);\n"
           "      updateProjectiles(dt); updatePickups(dt);\n"
           "      if (!NET.on) { updateMission(dt); updateSpawns(dt); } else if (NET.host) { NET.sim = true; updateMission(dt); NET.sim = false; netSpawnTick(dt); } else netGuestMission();\n"
           "      updateQuests(dt);")
s = rep(s, "  } else if (GS.mode === 'dead') { animChar(player.a, dt); for (const c of cars) if (c.ai) updateCarAI(c, dt); }",
        "  } else if (GS.mode === 'dead') { animChar(player.a, dt); if (!NET.on) for (const c of cars) if (c.ai) updateCarAI(c, dt); }", count=2)

# ---- il livello di rete (funzioni), prima del giorno/notte come il blocco HD
NET_JS = open(os.path.join(ROOT, 'tools', 'hd_net.js'), encoding='utf-8').read() + '\n'
s = rep(s, '/* =====================================================================\n   DAY / NIGHT', NET_JS + '/* =====================================================================\n   DAY / NIGHT')
# l'interfaccia si collega quando la pagina è pronta
s = rep(s, "  loadHD(p => {", "  netInitUI();\n  loadHD(p => {")
