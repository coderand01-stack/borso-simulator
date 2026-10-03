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

