import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

const viewportEl = document.getElementById('viewport');
const regionListEl = document.getElementById('region-list');
const detailEl = document.getElementById('detail');
const statEl = document.getElementById('stat');
const btnReset = document.getElementById('btn-reset');
const btnUndo = document.getElementById('btn-undo');
const btnRedo = document.getElementById('btn-redo');

const CUBE_SIZE = 1.0;    // 积木方块尺寸（紧密贴合，无缝隙）
const SNAP_DIST = 5;     // 组装吸附阈值：max(|dx|,|dy|,|dz|) < 5 时自动回归原位
const DRAG_PX = 5;       // 鼠标移动超过该像素判定为拖拽，否则视为点击选中

let regions = [];
const regionById = new Map();
let selectedId = null;

// ---------------------------------------------------------------- 渲染器 / 场景
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0xffffff, 1);
viewportEl.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xffffff);

const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 4000);
camera.position.set(0, 0, 1);

const brainGroup = new THREE.Group();
scene.add(brainGroup);

scene.add(new THREE.AmbientLight(0xffffff, 0.68));
const key = new THREE.DirectionalLight(0xffffff, 0.95);
key.position.set(1, 1.6, 1);
scene.add(key);
const fill = new THREE.DirectionalLight(0xbfd4ff, 0.38);
fill.position.set(-1, -0.5, -1);
scene.add(fill);

const boxGeom = new THREE.BoxGeometry(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE);

// 白色屏幕空间描边（OutlinePass：实时计算朝向边界，可透出外层脑区）
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const outlinePass = new OutlinePass(new THREE.Vector2(1, 1), scene, camera);
outlinePass.edgeColor = new THREE.Color(0xffffff);
outlinePass.visibleEdgeColor = new THREE.Color(0xffffff);
outlinePass.hiddenEdgeColor = new THREE.Color(0xffffff);
outlinePass.edgeStrength = 3;
outlinePass.edgeGlow = 0;
outlinePass.edgeThickness = 1.5;
outlinePass.pulsePeriod = 0;
outlinePass.selectedObjects = [];
composer.addPass(outlinePass);
composer.addPass(new OutputPass());

// ---------------------------------------------------------------- 轨道相机
const target = new THREE.Vector3(0, 0, 0);
const targetGoal = new THREE.Vector3(0, 0, 0);
const INITIAL_THETA = -0.5;
const INITIAL_PHI = 1.15;
let INITIAL_RADIUS = 185;
let theta = INITIAL_THETA;
let phi = INITIAL_PHI;
let radius = INITIAL_RADIUS;
let brainRadius = 80;

function updateCamera() {
  const sp = Math.sin(phi);
  camera.position.set(
    target.x + radius * sp * Math.sin(theta),
    target.y + radius * Math.cos(phi),
    target.z + radius * sp * Math.cos(theta)
  );
  camera.lookAt(target);
}

// ---------------------------------------------------------------- 动画补间
const tweens = new Map();
function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
function animateTo(reg, to, dur = 180) {
  tweens.set(reg.id, { from: reg.mesh.position.clone(), to: to.clone(), start: performance.now(), dur });
}

// ---------------------------------------------------------------- 撤销 / 重做 / 重置
let undoStack = [];
let redoStack = [];

function recordMove(reg, from, to) {
  undoStack.push({ id: reg.id, from: from.clone(), to: to.clone() });
  redoStack.length = 0;
  updateButtons();
}

function undo() {
  const m = undoStack.pop();
  if (!m) return;
  redoStack.push(m);
  animateTo(regionById.get(m.id), m.from);
  updateButtons();
}

function redo() {
  const m = redoStack.pop();
  if (!m) return;
  undoStack.push(m);
  animateTo(regionById.get(m.id), m.to);
  updateButtons();
}

function reset() {
  for (const reg of regions) {
    if (reg.mesh) animateTo(reg, new THREE.Vector3(0, 0, 0), 220);
  }
  undoStack.length = 0;
  redoStack.length = 0;
  select(null);
  target.set(0, 0, 0);
  targetGoal.set(0, 0, 0);
  theta = INITIAL_THETA;
  phi = INITIAL_PHI;
  radius = INITIAL_RADIUS;
  updateButtons();
}

function updateButtons() {
  btnUndo.disabled = undoStack.length === 0;
  btnRedo.disabled = redoStack.length === 0;
}

// ---------------------------------------------------------------- 选中 / 高亮
function select(id) {
  selectedId = id;
  for (const reg of regions) {
    if (!reg.mesh) continue;
    const m = reg.mesh.material;
    // 所有脑区保持原色、正常深度；描边由 OutlinePass（白色屏幕空间轮廓）提供
    m.color.copy(reg.colorObj);
    m.emissive.setRGB(0, 0, 0);
    m.transparent = false;
    m.opacity = 1;
    m.depthTest = true;
    m.depthWrite = true;
    reg.mesh.renderOrder = 0;
    m.needsUpdate = true;
  }

  if (id != null) {
    const reg = regionById.get(id);
    outlinePass.selectedObjects = [reg.mesh];
    targetGoal.copy(reg.localCenter).add(reg.mesh.position);
  } else {
    outlinePass.selectedObjects = [];
    targetGoal.set(0, 0, 0);
  }
  updateDetail();
  updateList();
}

// ---------------------------------------------------------------- 拾取
const raycaster = new THREE.Raycaster();
const _box = new THREE.Box3();
const _pt = new THREE.Vector3();

function pick(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1
  );
  raycaster.setFromCamera(ndc, camera);
  const ray = raycaster.ray;

  // 先用包围盒粗筛，再对候选做精确 InstancedMesh 射线检测
  const candidates = [];
  for (const reg of regions) {
    if (!reg.mesh) continue;
    _box.copy(reg.localBox).translate(reg.mesh.position);
    if (ray.intersectBox(_box, _pt)) {
      candidates.push({ reg, dist: ray.origin.distanceTo(_pt) });
    }
  }
  candidates.sort((a, b) => a.dist - b.dist);

  for (const c of candidates) {
    const hits = raycaster.intersectObject(c.reg.mesh, false);
    if (hits.length) return c.reg;
  }
  return null;
}

// ---------------------------------------------------------------- 指针交互
const el = renderer.domElement;
let downRegion = null;
let dragging = false;
let dragRegion = null;
let downX = 0;
let downY = 0;
let lastX = 0;
let lastY = 0;
let rotating = false;

const dragPlane = new THREE.Plane();
const dragStartPoint = new THREE.Vector3();
const dragStartOffset = new THREE.Vector3();
const _dir = new THREE.Vector3();

el.addEventListener('contextmenu', (e) => e.preventDefault());

el.addEventListener('pointerdown', (e) => {
  if (e.button === 2) {
    rotating = true;
    lastX = e.clientX;
    lastY = e.clientY;
    viewportEl.classList.add('dragging');
    return;
  }
  if (e.button === 0) {
    downX = e.clientX;
    downY = e.clientY;
    downRegion = pick(e.clientX, e.clientY);
    dragging = false;
    dragRegion = null;
  }
});

window.addEventListener('pointermove', (e) => {
  if (rotating) {
    theta -= (e.clientX - lastX) * 0.005;
    phi -= (e.clientY - lastY) * 0.005;
    phi = Math.max(0.05, Math.min(Math.PI - 0.05, phi));
    lastX = e.clientX;
    lastY = e.clientY;
    return;
  }
  if (dragging && dragRegion) {
    const rect = el.getBoundingClientRect();
    raycaster.setFromCamera(
      new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1),
      camera
    );
    if (raycaster.ray.intersectPlane(dragPlane, _pt)) {
      dragRegion.mesh.position.copy(dragStartOffset).add(_pt).sub(dragStartPoint);
    }
    return;
  }
  // 尚未进入拖拽状态时判断是否超过拖拽阈值
  if (downRegion && !dragging && e.buttons & 1) {
    const dx = e.clientX - downX;
    const dy = e.clientY - downY;
    if (dx * dx + dy * dy > DRAG_PX * DRAG_PX) {
      dragging = true;
      dragRegion = downRegion;
      tweens.delete(dragRegion.id);
      dragStartOffset.copy(dragRegion.mesh.position);
      _dir.copy(camera.getWorldDirection(new THREE.Vector3()));
      dragPlane.setFromNormalAndCoplanarPoint(_dir, dragRegion.mesh.position);
      const rect = el.getBoundingClientRect();
      raycaster.setFromCamera(
        new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1),
        camera
      );
      raycaster.ray.intersectPlane(dragPlane, dragStartPoint);
    }
  }
});

window.addEventListener('pointerup', (e) => {
  if (e.button === 2) {
    rotating = false;
    viewportEl.classList.remove('dragging');
    return;
  }
  if (e.button !== 0) return;

  if (dragging && dragRegion) {
    const reg = dragRegion;
    const off = reg.mesh.position;
    const finalOff = off.clone();
    if (Math.max(Math.abs(off.x), Math.abs(off.y), Math.abs(off.z)) < SNAP_DIST) {
      finalOff.set(0, 0, 0);
      animateTo(reg, finalOff, 160);
    }
    if (!finalOff.equals(dragStartOffset)) {
      recordMove(reg, dragStartOffset, finalOff);
    }
  } else {
    // 单击积木：仅显示该脑区详细信息（不改变3D高亮）；单击空白：取消选中
    select(downRegion ? downRegion.id : null);
  }
  dragging = false;
  dragRegion = null;
  downRegion = null;
});

el.addEventListener('wheel', (e) => {
  e.preventDefault();
  radius *= 1 + e.deltaY * 0.001;
  radius = Math.max(70, Math.min(600, radius));
}, { passive: false });

// ---------------------------------------------------------------- UI 构建
function buildList() {
  regionListEl.innerHTML = '';
  for (const r of regions) {
    const item = document.createElement('div');
    item.className = 'region-item';
    item.dataset.id = r.id;
    item.innerHTML =
      `<span class="dot" style="background:${r.color}"></span>` +
      `<span class="name">${r.name}</span>` +
      `<span class="count">${r.count}</span>`;
    item.addEventListener('click', () => {
      if (selectedId === r.id) {
        select(null);
      } else {
        select(r.id);
      }
    });
    regionListEl.appendChild(item);
  }
}

function updateList() {
  for (const el of regionListEl.children) {
    el.classList.toggle('active', Number(el.dataset.id) === selectedId);
  }
}

function updateDetail() {
  if (selectedId == null) {
    detailEl.innerHTML = '<div class="detail-empty">点击脑区或右侧列表，查看该脑区的功能与所属任务协作链路</div>';
    return;
  }
  const r = regionById.get(selectedId);
  const funcItems = r.functions.map((f) => `<li>${f}</li>`).join('');
  const chainItems = r.chains.map((c) =>
    `<div class="chain"><div class="chain-name">${c.name}</div><div class="chain-desc">${c.desc}</div></div>`
  ).join('');
  detailEl.innerHTML =
    `<div class="detail-head">` +
      `<span class="dot" style="background:${r.color}"></span>` +
      `<h3>${r.name}</h3>` +
      `<span class="en">${r.en}</span>` +
      `<span class="count">${r.count} 块积木</span>` +
    `</div>` +
    `<div class="detail-grid">` +
      `<div class="detail-section"><h4>脑区功能</h4><ul>${funcItems}</ul></div>` +
      `<div class="detail-section"><h4>复杂任务协作链路</h4><div class="chains">${chainItems}</div></div>` +
    `</div>`;
}

// ---------------------------------------------------------------- 数据处理
function buildMeshes(byteData, dims, regionList) {
  const N = byteData.length / 4;
  const cx = (dims[0] - 1) / 2; // right
  const cy = (dims[1] - 1) / 2; // anterior
  const cz = (dims[2] - 1) / 2; // superior

  // 按脑区统计体素数量并分配数组
  const counts = new Array(regionList.length + 1).fill(0);
  for (let i = 0; i < N; i++) counts[byteData[i * 4 + 3]]++;

  const voxelArrays = new Map();
  for (const r of regionList) voxelArrays.set(r.id, new Float32Array(counts[r.id] * 3));
  const cursor = new Array(regionList.length + 1).fill(0);

  let gMinX = Infinity, gMinY = Infinity, gMinZ = Infinity;
  let gMaxX = -Infinity, gMaxY = -Infinity, gMaxZ = -Infinity;

  for (let i = 0; i < N; i++) {
    const right = byteData[i * 4];
    const anterior = byteData[i * 4 + 1];
    const superior = byteData[i * 4 + 2];
    const rid = byteData[i * 4 + 3];
    const arr = voxelArrays.get(rid);
    const p = cursor[rid];
    cursor[rid] += 3;
    // 场景坐标：x = 左右，y = 上下(superior)，z = 前后(anterior)
    const x = right - cx;
    const y = superior - cz;
    const z = anterior - cy;
    arr[p] = x;
    arr[p + 1] = y;
    arr[p + 2] = z;
    if (x < gMinX) gMinX = x; if (x > gMaxX) gMaxX = x;
    if (y < gMinY) gMinY = y; if (y > gMaxY) gMaxY = y;
    if (z < gMinZ) gMinZ = z; if (z > gMaxZ) gMaxZ = z;
  }

  const hx = (gMaxX - gMinX) / 2;
  const hy = (gMaxY - gMinY) / 2;
  const hz = (gMaxZ - gMinZ) / 2;
  brainRadius = Math.sqrt(hx * hx + hy * hy + hz * hz);

  const m = new THREE.Matrix4();
  const v = new THREE.Vector3();

  for (const r of regionList) {
    const arr = voxelArrays.get(r.id);
    const count = arr.length / 3;
    if (count === 0) { r.mesh = null; continue; }

    const mat = new THREE.MeshLambertMaterial({
      color: new THREE.Color(r.color),
      transparent: false,
    });
    const mesh = new THREE.InstancedMesh(boxGeom, mat, count);

    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    let sx = 0, sy = 0, sz = 0;

    for (let i = 0; i < count; i++) {
      const x = arr[i * 3];
      const y = arr[i * 3 + 1];
      const z = arr[i * 3 + 2];
      v.set(x, y, z);
      m.makeTranslation(x, y, z);
      mesh.setMatrixAt(i, m);
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
      sx += x; sy += y; sz += z;
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.userData.regionId = r.id;

    r.mesh = mesh;
    r.localBox = new THREE.Box3(new THREE.Vector3(minX, minY, minZ), new THREE.Vector3(maxX, maxY, maxZ));
    r.localCenter = new THREE.Vector3(sx / count, sy / count, sz / count);
    r.colorObj = new THREE.Color(r.color);

    brainGroup.add(mesh);
  }
}

// ---------------------------------------------------------------- 启动
async function init() {
  const data = await fetch('/brain.json').then((r) => r.json());
  regions = data.regions.map((r) => ({ ...r }));
  for (const r of regions) regionById.set(r.id, r);

  const bin = atob(data.voxels_b64);
  const byteData = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) byteData[i] = bin.charCodeAt(i);

  buildMeshes(byteData, data.dims, regions);
  buildList();
  updateDetail();
  updateList();
  updateButtons();

  statEl.textContent = `${regions.length} 个脑区 · ${data.voxelCount.toLocaleString()} 块积木`;

  btnReset.addEventListener('click', reset);
  btnUndo.addEventListener('click', undo);
  btnRedo.addEventListener('click', redo);

  resize();
  new ResizeObserver(() => resize()).observe(viewportEl);
  const fovV = camera.fov * Math.PI / 180;
  const fovH = 2 * Math.atan(Math.tan(fovV / 2) * camera.aspect);
  const minFov = Math.min(fovV, fovH);
  INITIAL_RADIUS = (brainRadius / Math.sin(minFov / 2)) * 0.88;
  radius = INITIAL_RADIUS;
  updateCamera();
  animate();
}

function resize() {
  const w = viewportEl.clientWidth;
  const h = viewportEl.clientHeight;
  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  for (const [id, t] of tweens) {
    const k = Math.min(1, (now - t.start) / t.dur);
    const e = easeOut(k);
    const reg = regionById.get(id);
    if (reg && reg.mesh) reg.mesh.position.lerpVectors(t.from, t.to, e);
    if (k >= 1) tweens.delete(id);
  }
  target.lerp(targetGoal, 0.08);
  updateCamera();
  composer.render();
}

window.addEventListener('resize', resize);
init();
