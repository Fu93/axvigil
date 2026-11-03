/* Page-length crystal. three@0.170.0 via the import map.
   Scroll stays native; the camera and crystal ease toward it.
   No per-frame grain, no opacity blinking. */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export const HERO3D = {
  bg: 0x1c1d1a,
  accent: 0xeef94b,
  camera: { fov: 31, z: 7.5, dollyToZ: 6.2, parallax: { x: 0.22, y: 0.14, lambda: 2.5 } },
  crystal: {
    height: 2.4,
    idleSpin: 0.12,
    bobAmp: 0.04,
    bobFreq: 0.6,
    tilt: { y: 0.28, x: 0.16, k: 26, damp: 7.2 },
    scrollSpin: Math.PI * 0.75
  },
  material: {
    color: 0x050505,
    metalness: 0,
    roughness: 0.04,
    clearcoat: 1,
    clearcoatRoughness: 0.02,
    ior: 1.7,
    envMapIntensity: 2.2,
    iridescence: 0
  },
  edges: { thresholdDeg: 25, hdrBoost: 2.2, opacity: 0.9, sweep: 0.18, width: 1.25 },
  bloom: { strength: 0.42, radius: 0.32, threshold: 0.96, halfRes: true },
  nodes: {
    radii: [1.75, 2.0, 2.3],
    inclDeg: [12, -20, 34],
    periodS: [18, 24, 31],
    phase: [0, 2.1, 4.2],
    size: 0.06,
    ringOpacity: 0.1,
    signEveryS: 7
  },
  intro: { edgesS: 0.9, bodyDelayS: 0.5, textDelayS: 0.7, totalS: 1.8 },
  perf: { maxDprDesktop: 1.25, maxDprMobile: 1.5, frameBudgetMs: 22 }
};

const HALVES = "assets/3d/halves_meshopt.glb";
const SHARDS = "assets/3d/shards_meshopt.glb";
const NODE = "assets/3d/node_meshopt.glb";
/* Section GLBs are max-dimension 1.90, centred, +Y up. Loaded one section ahead. */
const SECTION_FILES = [
  null,
  { id: "problem", url: "assets/3d/problem.glb", motion: "vault", cam: 5.5, dolly: 0.22 },
  { id: "how", url: "assets/3d/how.glb", motion: "cage", cam: 6.15, dolly: -0.12 },
  { id: "proof", url: "assets/3d/proof.glb", motion: "record", cam: 6.35, dolly: 0.08 },
  { id: "board", url: "assets/3d/board_podium.glb", motion: "podium", cam: 6.2, dolly: 0 },
  { id: "roadmap", url: "assets/3d/roadmap.glb", motion: "lattice", cam: 6.9, dolly: 0.16 },
  { id: "faq", url: "assets/3d/faq.glb", motion: "plumb", cam: 5.7, dolly: -0.06 }
];
const MODEL_SCALE = 2.4 / 1.9;
const SHARD_CENTROIDS = [
  [0.0235, 0.5383, 0.0131],
  [0.1876, 0.1634, 0.0381],
  [-0.0628, 0.2071, -0.178],
  [-0.155, 0.2342, 0.1167],
  [-0.0797, -0.1606, 0.1328],
  [0.0481, -0.1922, -0.1395],
  [0.0157, -0.5384, -0.0261]
];
const ACCENT = HERO3D.accent;
const lineMats = [];
let started = false;

export function mount() {
  if (started) return;
  started = true;
  const host = document.getElementById("hero-core");
  const stage = document.getElementById("stage");
  const hero = document.getElementById("top");
  if (!host || !stage || !hero) return;

  const lumTest = /(?:\?|&)lum=1(?:&|$)/.test(location.search);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  let mobile = window.matchMedia("(max-width: 767px)").matches;
  let seen = false;
  let midPage = false;
  try {
    seen = sessionStorage.getItem("axv-intro-seen") === "1";
    midPage = Number(sessionStorage.getItem("axv-scroll") || 0) > 160;
  } catch (err) { seen = false; }
  const hashed = !!(location.hash && location.hash.length > 1);
  const playIntro = !reduced && !seen && !hashed && !midPage;
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  if (!webglOk()) {
    document.documentElement.classList.remove("hold-hero");
    document.documentElement.classList.add("intro-go");
    document.documentElement.classList.add("no-webgl");
    return;
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
      stencil: false,
      preserveDrawingBuffer: lumTest
    });
  } catch (err) {
    document.documentElement.classList.remove("hold-hero");
    document.documentElement.classList.add("intro-go");
    document.documentElement.classList.add("no-webgl");
    return;
  }
  if (!renderer.getContext()) {
    document.documentElement.classList.remove("hold-hero");
    document.documentElement.classList.add("intro-go");
    document.documentElement.classList.add("no-webgl");
    return;
  }

  renderer.setClearColor(0x1c1d1a, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.domElement.setAttribute("aria-hidden", "true");
  stage.insertBefore(renderer.domElement, stage.querySelector(".stage-vignette"));
  const grain = stage.querySelector(".stage-grain");
  const vignette = stage.querySelector(".stage-vignette");
  if (grain) stage.appendChild(grain);
  if (vignette) stage.appendChild(vignette);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1c1d1a);
  const fogNear = new THREE.Color(0x1c1d1a);
  const fogFar = new THREE.Color(0x14140f);
  scene.fog = new THREE.FogExp2(0x1c1d1a, 0.045);
  const camera = new THREE.PerspectiveCamera(HERO3D.camera.fov, 1, 0.08, 40);
  camera.position.set(0, 0.08, HERO3D.camera.z);
  camera.layers.enable(1);
  camera.layers.enable(2);

  const pmrem = new THREE.PMREMGenerator(renderer);
  const studio = buildStudio();
  const prevSpace = renderer.outputColorSpace;
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  const envMap = pmrem.fromScene(studio, 0).texture;
  renderer.outputColorSpace = prevSpace;
  scene.environment = envMap;
  studio.traverse(function (obj) {
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) obj.material.dispose();
  });
  pmrem.dispose();

  const key = new THREE.DirectionalLight(0xfff4e4, 0.42);
  key.position.set(-3.4, 4.8, 3.6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xeef3ff, 0.7);
  rim.position.set(4.8, 1.6, -5.2);
  scene.add(rim);
  /* Section meshes are near-black metal. These lights stay on layer 2 so the hero crystal is unchanged. */
  const sectionAmb = new THREE.AmbientLight(0xc5cbc4, 0.32);
  sectionAmb.layers.set(2);
  scene.add(sectionAmb);
  const sectionKey = new THREE.DirectionalLight(0xfff6ea, 1.05);
  sectionKey.position.set(-2.6, 4.4, 5.2);
  sectionKey.layers.set(2);
  scene.add(sectionKey);
  const sectionFill = new THREE.DirectionalLight(0xd5deea, 0.8);
  sectionFill.position.set(4.2, 1.4, 3.2);
  sectionFill.layers.set(2);
  scene.add(sectionFill);
  const sectionRim = new THREE.DirectionalLight(0xf4f1e6, 1.35);
  sectionRim.position.set(-5.2, 2.8, -3.6);
  sectionRim.layers.set(2);
  scene.add(sectionRim);

  const slot = new THREE.Group();
  scene.add(slot);
  const shows = SECTION_FILES.map(function (spec, index) {
    return {
      spec: spec, index: index, root: null, mats: [], state: "idle",
      weight: 0, travel: 0, yaw: 0, swing: 0, step: 0, raw: 0
    };
  });
  let scrollV = 0;
  let lastScroll = window.scrollY;

  const rig = new THREE.Group();
  const tilt = new THREE.Group();
  const yaw = new THREE.Group();
  const topGroup = new THREE.Group();
  const botGroup = new THREE.Group();
  const orbits = new THREE.Group();
  scene.add(rig);
  rig.add(tilt);
  tilt.add(yaw);
  yaw.add(topGroup);
  yaw.add(botGroup);
  yaw.add(orbits);

  const bodyMat = new THREE.MeshPhysicalMaterial({
    color: HERO3D.material.color,
    metalness: HERO3D.material.metalness,
    roughness: HERO3D.material.roughness,
    clearcoat: HERO3D.material.clearcoat,
    clearcoatRoughness: HERO3D.material.clearcoatRoughness,
    ior: HERO3D.material.ior,
    specularIntensity: 1,
    envMap: envMap,
    envMapIntensity: HERO3D.material.envMapIntensity,
    iridescence: HERO3D.material.iridescence,
    flatShading: false,
    transparent: true,
    opacity: playIntro ? 0 : 1,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1
  });

  const hiddenLines = [];
  const solidMat = lineMat(1.55, 0);
  const glintMat = trackLine(new LineMaterial({
    color: hdr(HERO3D.edges.hdrBoost),
    linewidth: HERO3D.edges.width,
    dashed: true,
    dashSize: 0.12,
    gapSize: 0.16,
    dashScale: 1,
    transparent: true,
    opacity: 0,
    toneMapped: false,
    depthWrite: false,
    alphaToCoverage: true
  }));
  const hiddenMat = lineMat(1.15, 0);
  hiddenMat.depthFunc = THREE.GreaterDepth;

  const nodeMat = new THREE.MeshStandardMaterial({
    color: 0x050505,
    emissive: ACCENT,
    emissiveIntensity: 0.42,
    roughness: 0.32,
    metalness: 0.15,
    envMapIntensity: 1.4,
    transparent: true,
    opacity: playIntro ? 0 : 1
  });
  const nodeEdgeMat = lineMat(2.5, playIntro ? 0 : 1);
  const ringMat = trackLine(new LineMaterial({
    color: 0xffffff,
    linewidth: 1,
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
    toneMapped: false,
    alphaToCoverage: true
  }));

  const innerMat = new THREE.MeshBasicMaterial({
    color: hdr(0.55),
    toneMapped: false,
    transparent: true,
    opacity: 0,
    depthWrite: false
  });
  let inner = null;

  const apexMark = new THREE.Object3D();
  apexMark.position.set(0, 1.2, 0);
  topGroup.add(apexMark);
  const girdleMark = new THREE.Object3D();
  girdleMark.position.set(0.72, 0, 0);
  yaw.add(girdleMark);

  const backlight = new THREE.Sprite(new THREE.SpriteMaterial({
    map: backlightTexture(),
    color: 0xffffff,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.AdditiveBlending,
    opacity: 1
  }));
  backlight.scale.set(5.2, 5.2, 1);
  backlight.material.opacity = 0.55;
  backlight.position.z = -1.15;
  backlight.renderOrder = -1;
  rig.add(backlight);

  const dust = makeDust(mobile ? 1100 : 2600);
  scene.add(dust);
  const floor = makeFloor();
  if (!mobile) scene.add(floor);

  const sats = HERO3D.nodes.radii.map(function (radius, i) {
    const pivot = new THREE.Group();
    pivot.rotation.x = THREE.MathUtils.degToRad(HERO3D.nodes.inclDeg[i]);
    const ringPts = [];
    for (let s = 0; s <= 256; s += 1) {
      const a = (s / 256) * Math.PI * 2;
      ringPts.push(Math.cos(a) * radius, 0, Math.sin(a) * radius);
    }
    const ringGeo = new LineGeometry();
    ringGeo.setPositions(ringPts);
    const ring = new Line2(ringGeo, ringMat);
    ring.computeLineDistances();
    ring.visible = !mobile || i === 0;
    pivot.add(ring);
    const orb = new THREE.Group();
    orb.position.set(radius, 0, 0);
    pivot.add(orb);
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(0.25, 8, 8),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
    );
    hit.position.copy(orb.position);
    hit.userData.index = i;
    pivot.add(hit);
    orbits.add(pivot);
    return {
      pivot: pivot,
      orb: orb,
      ring: ring,
      hit: hit,
      radius: radius,
      period: HERO3D.nodes.periodS[i],
      angle: HERO3D.nodes.phase[i],
      hover: false,
      index: i
    };
  });

  const signLines = [0, 1].map(function () {
    const geo = new LineGeometry();
    geo.setPositions([0, 0, 0, 0, 1.2, 0]);
    const mat = trackLine(new LineMaterial({
      color: hdr(1.6),
      linewidth: HERO3D.edges.width,
      dashed: true,
      dashSize: 0.06,
      gapSize: 0.1,
      transparent: true,
      opacity: 0,
      toneMapped: false,
      depthWrite: false,
      alphaToCoverage: true
    }));
    const line = new Line2(geo, mat);
    line.computeLineDistances();
    line.frustumCulled = false;
    line.layers.enable(1);
    scene.add(line);
    return line;
  });

  const shardPieces = [];
  const shardMat = bodyMat.clone();
  shardMat.transparent = true;
  shardMat.opacity = 0;
  shardMat.depthWrite = false;

  const hud = buildHud();
  const chrome = buildChrome(playIntro);
  if (playIntro) document.documentElement.classList.add("await-intro");
  else document.documentElement.classList.add("intro-go");

  const grade = makeComposer(renderer, scene, camera);
  const forceHQ = /(?:\?|&)forcehq(?:&|=|$)/.test(location.search);
  const dprLadder = forceHQ
    ? [topDpr(mobile, true)]
    : mobile
      ? [topDpr(mobile, false), 1, 0.75]
      : [topDpr(mobile, false), 1.5, 1, 0.75];
  let tier = 0;
  let dprCap = dprLadder[0];
  let bloomOn = !reduced;
  const frameMs = [];
  let active = true;
  let raf = 0;
  let posed = false;
  const pose = {
    x: 0, y: 0, scale: 1, split: 0, body: playIntro ? 0 : 1, edge: 0,
    hidden: 0, orbit: 1, camZ: HERO3D.camera.z, spin: 0, rotZ: 0, light: 0, proof: 0, heroP: 0,
    side: 0, lift: 0, fog: 0, podium: 0, dolly: 0, book: 0
  };
  let slotPosed = false;
  const slotPose = { x: 0, y: 0, scale: 1 };
  let heldScale = 0;
  let heldCam = 0;
  let heldSlot = 0;
  let bloomLevel = HERO3D.bloom.strength;
  let exposureLevel = 1;
  let stageFade = 1;
  let storyS = 0;
  const tiltS = { x: 0, vx: 0, y: 0, vy: 0 };
  const drag = { x: 0, v: 0, on: false, lastX: 0, lastT: 0 };
  const look = { nx: 0, ny: 0 };
  let camPx = 0;
  let camPy = 0;
  let sweep = 0;
  const rate = { fx: 0, fy: 0, sx: 0, sy: 0 };
  let idle = 0;
  let introT = playIntro ? 0 : 20;
  let meshReady = !playIntro;
  let meshReadyAt = playIntro ? 0 : performance.now();
  let heroResident = false;
  let envIn = reduced ? 0.4 : 0;
  let clock = performance.now();
  const pointer = new THREE.Vector2(0, 0);
  const ray = new THREE.Raycaster();
  const tmp = new THREE.Vector3();
  const tmp2 = new THREE.Vector3();
  const centerNdc = new THREE.Vector3();

  function finishIntro() {
    introT = 30;
    document.documentElement.classList.add("intro-go");
    chrome.hideLoader();
    chrome.hideSkip();
    try { sessionStorage.setItem("axv-intro-seen", "1"); } catch (err) { /* ignore */ }
  }
  chrome.onSkip(finishIntro);

  const manager = new THREE.LoadingManager();
  manager.onProgress = function (_url, loaded, total) {
    if (total) chrome.progress(loaded / total);
  };
  const loader = new GLTFLoader(manager);
  loader.setMeshoptDecoder(MeshoptDecoder);
  const t0 = performance.now();
  function loadOne(url) {
    return new Promise(function (resolve, reject) {
      loader.load(url, resolve, undefined, reject);
    });
  }
  Promise.all([loadOne(HALVES), loadOne(SHARDS), loadOne(NODE)]).then(function (loaded) {
    const halves = meshesByName(loaded[0].scene);
    const shardMap = meshesByName(loaded[1].scene);
    const nodes = meshesByName(loaded[2].scene);
    if (halves.half_top) addHalf(topGroup, halves.half_top);
    if (halves.half_bottom) addHalf(botGroup, halves.half_bottom);
    if (halves.core) {
      inner = halves.core;
      inner.material = innerMat;
      inner.scale.setScalar(MODEL_SCALE);
      inner.layers.enable(1);
      inner.userData.bloom = true;
      inner.visible = false;
      yaw.add(inner);
    }
    SHARD_CENTROIDS.forEach(function (centroid, index) {
      const src = shardMap["shard_0" + (index + 1)];
      if (!src) return;
      const piece = src;
      piece.material = shardMat;
      piece.scale.setScalar(MODEL_SCALE);
      piece.visible = playIntro;
      const dir = new THREE.Vector3(centroid[0] * 3, centroid[1], centroid[2] * 3).normalize();
      yaw.add(piece);
      shardPieces.push({ mesh: piece, dir: dir, delay: index * 0.04 });
    });
    const nodeSrc = nodes.validator_node;
    if (nodeSrc) {
      const edgeGeo = new THREE.EdgesGeometry(nodeSrc.geometry, 1);
      sats.forEach(function (sat) {
        const mesh = new THREE.Mesh(nodeSrc.geometry, nodeMat);
        mesh.scale.setScalar(0.18);
        const edges = fatLines(edgeGeo, nodeEdgeMat);
        edges.scale.setScalar(1.02);
        edges.layers.enable(1);
        edges.userData.bloom = true;
        mesh.add(edges);
        mesh.layers.enable(1);
        mesh.userData.bloom = true;
        sat.orb.add(mesh);
        sat.node = mesh;
      });
    }
    const bytes = performance.getEntriesByType("resource").filter(function (row) {
      return /halves_meshopt|shards_meshopt|node_meshopt/.test(row.name);
    }).reduce(function (sum, row) { return sum + (row.decodedBodySize || row.transferSize || 0); }, 0);
    host.dataset.glbBytes = String(bytes);
    host.dataset.glbMs = String(Math.round(performance.now() - t0));
    host.classList.add("is-live");
    document.documentElement.classList.add("ax-3d");
    meshReady = true;
    heroResident = true;
    meshReadyAt = performance.now();
    chrome.loaded();
    resize();
    setActive(true);
  }).catch(function () {
    chrome.loaded();
    document.documentElement.classList.add("intro-go");
    host.classList.remove("is-live");
  });

  function addHalf(group, source) {
    const mesh = source.isMesh ? source : new THREE.Mesh(source, bodyMat);
    mesh.material = bodyMat;
    mesh.scale.setScalar(MODEL_SCALE);
    mesh.layers.set(0);
    group.add(mesh);
    const edges = makeEdges(mesh.geometry);
    const solid = fatLines(edges, solidMat);
    solid.scale.setScalar(1.004);
    solid.layers.enable(1);
    mesh.add(solid);
    const glint = fatLines(edges, glintMat);
    glint.scale.setScalar(1.006);
    glint.computeLineDistances();
    glint.layers.enable(1);
    mesh.add(glint);
    const hidden = fatLines(edges, hiddenMat);
    hidden.scale.setScalar(1.004);
    hidden.layers.enable(1);
    hidden.visible = false;
    hiddenLines.push(hidden);
    mesh.add(hidden);
  }

  function resize() {
    mobile = window.matchMedia("(max-width: 767px)").matches;
    if (tier === 0) {
      dprLadder[0] = topDpr(mobile, forceHQ);
      dprCap = dprLadder[0];
    }
    const w = window.innerWidth;
    const h = Math.max(1, window.innerHeight);
    const ratio = Math.max(0.5, dprCap);
    renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    lineMats.forEach(function (mat) { mat.resolution.set(w, h); });
    grade.resize(w, h);
    sats.forEach(function (sat, i) { sat.ring.visible = !mobile || i === 0; });
    hud.root.hidden = mobile || reduced;
  }

  function projectAt(sx, sy, camZ, px, minScale, maxScale) {
    const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * Math.max(camZ, 4.8);
    const halfW = halfH * camera.aspect;
    const ndcX = (sx / Math.max(1, window.innerWidth)) * 2 - 1;
    const ndcY = -((sy / Math.max(1, window.innerHeight)) * 2 - 1);
    const pxPerUnit = window.innerHeight / (2 * halfH);
    return {
      x: ndcX * halfW,
      y: ndcY * halfH,
      scale: THREE.MathUtils.clamp(px / (HERO3D.crystal.height * pxPerUnit), minScale, maxScale)
    };
  }

  function bandScreen(id) {
    if (!mobile) return null;
    const el = id === "top"
      ? document.getElementById("hero-core")
      : document.querySelector('.model-band[data-band="' + id + '"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return null;
    return {
      sx: r.left + r.width * 0.5,
      sy: r.top + r.height * 0.48,
      px: Math.min(r.width * 0.86, r.height * 0.82)
    };
  }

  function bookendScreen() {
    const closeEl = document.getElementById("close");
    const r = closeEl ? closeEl.getBoundingClientRect() : null;
    const gutter = Math.max(40, window.innerWidth * 0.04);
    const col = Math.min(700, window.innerWidth * 0.52);
    const copyRight = gutter + col;
    const sx = THREE.MathUtils.clamp(
      copyRight + (window.innerWidth - copyRight) * 0.58,
      window.innerWidth * 0.74,
      window.innerWidth * 0.9
    );
    let sy = r ? r.top + Math.min(r.height, window.innerHeight * 0.7) * 0.42 : window.innerHeight * 0.4;
    const footer = document.getElementById("footer");
    if (footer) sy = Math.min(sy, footer.getBoundingClientRect().top - 48);
    const room = Math.max(120, (window.innerWidth - copyRight) * 0.7);
    return { sx: sx, sy: sy, px: Math.min(210, window.innerHeight * 0.26, room) };
  }

  function viewCam() {
    const mix = sectionMix();
    const closeW = anchorWeight(document.getElementById("close"));
    const book = closeW * (1 - mix.hero);
    let cam = mix.cam;
    if (!(cam > 4.5)) cam = 6.8;
    cam = THREE.MathUtils.lerp(cam, 7.15, smootherstep(clamp01(book)));
    cam = THREE.MathUtils.clamp(cam, 5.5, 8.4);
    return { mix: mix, closeW: closeW, book: book, cam: cam };
  }

  function activeShowId() {
    let best = 1;
    let bestW = -1;
    for (let i = 1; i < shows.length; i += 1) {
      if (shows[i].raw > bestW) {
        bestW = shows[i].raw;
        best = i;
      }
    }
    return shows[best] && shows[best].spec ? shows[best].spec.id : "problem";
  }

  function desired() {
    const heroP = THREE.MathUtils.clamp(-hero.getBoundingClientRect().top / Math.max(hero.offsetHeight, 1), 0, 1);
    const flight = sampleFlight(storyS);
    const view = viewCam();
    const camZ = view.cam;
    const book = view.book;
    const away = (1 - view.mix.hero) * (1 - view.closeW);
    const heroBand = bandScreen("top");
    const lane = projectAt(
      heroBand ? heroBand.sx : window.innerWidth * 0.8,
      heroBand ? heroBand.sy : window.innerHeight * 0.46,
      camZ,
      heroBand ? heroBand.px : Math.min(window.innerHeight * 0.56, window.innerWidth * 0.28 * 1.35),
      0.45,
      1.85
    );
    const endScreen = bandScreen("close") || bookendScreen();
    const end = projectAt(endScreen.sx, endScreen.sy, camZ, endScreen.px, 0.16, 0.62);
    const k = mobile ? (book > 0.42 ? 1 : 0) : smootherstep(clamp01((book - 0.12) / 0.5));
    return {
      x: lane.x + (end.x - lane.x) * k,
      y: lane.y + (end.y - lane.y) * k,
      scale: lane.scale + (end.scale - lane.scale) * k,
      split: flight.split * (1 - k),
      body: flight.body,
      edge: flight.edge * (1 - k),
      hidden: flight.hidden * (1 - k),
      orbit: flight.orbit * (1 - k),
      camZ: camZ,
      spin: flight.spin * (1 - k * 0.85) + heroP * 0.35 * (1 - k),
      rotZ: flight.side * 0.05 * (1 - k),
      light: 0,
      proof: flight.proof * (1 - k),
      heroP: heroP,
      side: flight.side * (1 - k),
      lift: flight.lift * (1 - k),
      fog: flight.fog * (1 - k),
      podium: away,
      book: book,
      dolly: view.mix.dolly * (1 - k)
    };
  }

  function slotDesired(camZ) {
    const band = bandScreen(activeShowId());
    if (band) return projectAt(band.sx, band.sy, camZ, band.px, 0.32, 1.65);
    const laneW = window.innerWidth * 0.28;
    return projectAt(
      window.innerWidth * 0.8,
      window.innerHeight * 0.46,
      camZ,
      Math.min(window.innerHeight * 0.56, laneW * 1.35),
      0.45,
      1.85
    );
  }

  function anchorWeight(el) {
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const vh = window.innerHeight || 1;
    const mid = r.top + Math.min(r.height, vh) * 0.42;
    return Math.max(0, 1 - Math.abs(mid - vh * 0.46) / (vh * 0.62));
  }

  function sectionTravel(el) {
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const vh = window.innerHeight || 1;
    const start = vh * 0.92;
    const end = vh * 0.15 - r.height;
    return clamp01((start - r.top) / Math.max(1, start - end));
  }

  function sectionMix() {
    let sum = 0;
    const weights = shows.map(function (show, i) {
      const id = i === 0 ? "top" : show.spec.id;
      const w = anchorWeight(document.getElementById(id));
      show.raw = w;
      sum += w;
      return w;
    });
    if (sum < 0.001) return { hero: 0, cam: 6.8, dolly: 0 };
    let cam = 0;
    let dolly = 0;
    weights.forEach(function (w, i) {
      const n = w / sum;
      if (i === 0) cam += 6.8 * n;
      else {
        cam += shows[i].spec.cam * n;
        dolly += (shows[i].spec.dolly || 0) * n;
      }
    });
    return { hero: weights[0] / sum, cam: cam, dolly: dolly };
  }

  function addPlinthStrip(root, mats) {
    const mat = new THREE.MeshStandardMaterial({
      color: 0x14140c,
      emissive: 0xeef94b,
      emissiveIntensity: 1.9,
      roughness: 0.35,
      metalness: 0,
      transparent: true,
      opacity: 0,
      toneMapped: false,
      depthWrite: false
    });
    const strip = new THREE.Mesh(new THREE.BoxGeometry(1.74, 0.012, 0.018), mat);
    strip.position.set(0, -0.63, 0.28);
    root.add(strip);
    mats.push(mat);
  }

  function tuneShowMats(root, bucket, motion) {
    const look = {
      vault: { env: 0.42, metal: 0.06, rough: 0.74, glow: 0x3a3e36, flatSpec: true },
      cage: { env: 0.36, metal: 0.05, rough: 0.78, glow: 0x363a34, flatSpec: true },
      record: { env: 1.3, metal: 0.36, rough: 0.7, glow: 0x343830 },
      podium: { env: 1.15, metal: 0.46, rough: 0.86, glow: 0x2c302a },
      lattice: { env: 1.25, metal: 0.4, rough: 0.76, glow: 0x32362f },
      plumb: { env: 1.4, metal: 0.36, rough: 0.66, glow: 0x363a32 }
    }[motion] || { env: 1.7, metal: 0.45, rough: 0.66, glow: 0x363a32 };
    root.traverse(function (obj) {
      if (!obj.isMesh || !obj.material) return;
      obj.layers.enable(2);
      const list = Array.isArray(obj.material) ? obj.material : [obj.material];
      list.forEach(function (mat) {
        mat.envMap = scene.environment;
        mat.envMapIntensity = look.env;
        mat.fog = false;
        if (look.flatSpec) {
          mat.metalnessMap = null;
          mat.roughnessMap = null;
        }
        if (mat.metalness !== undefined) mat.metalness = look.metal;
        if (mat.roughness !== undefined) mat.roughness = look.rough;
        if (mat.emissive) {
          mat.emissive.set(look.glow);
          mat.emissiveIntensity = 1;
          mat.emissiveMap = null;
          mat.userData.baseEmit = 1;
        }
        mat.userData.baseEnv = look.env;
        mat.transparent = true;
        mat.opacity = 0;
        mat.depthWrite = true;
        bucket.push(mat);
      });
    });
  }

  function releaseShow(show) {
    if (show.root) {
      slot.remove(show.root);
      show.root.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (!obj.material) return;
        const list = Array.isArray(obj.material) ? obj.material : [obj.material];
        list.forEach(function (mat) {
          ["map", "normalMap", "roughnessMap", "metalnessMap", "emissiveMap", "aoMap"].forEach(function (key) {
            if (mat[key]) mat[key].dispose();
          });
          mat.dispose();
        });
      });
    }
    show.root = null;
    show.mats = [];
    show.state = "idle";
    const el = show.spec && document.getElementById(show.spec.id);
    if (el && mobile) el.classList.add("still-on");
  }

  let sectionChain = Promise.resolve();
  function loadShow(show) {
    if (!show.spec || show.state !== "idle") return;
    show.state = "loading";
    const spec = show.spec;
    sectionChain = sectionChain.then(function () {
      if (show.state === "dead") return null;
      return loadOne(spec.url);
    }).then(function (gltf) {
      if (!gltf || show.state === "dead") {
        if (show.state === "dead") releaseShow(show);
        return;
      }
      const root = gltf.scene;
      root.scale.setScalar(MODEL_SCALE);
      tuneShowMats(root, show.mats, spec.motion);
      show.root = root;
      show.state = "ready";
      root.visible = false;
      if (spec.motion === "podium") addPlinthStrip(root, show.mats);
      slot.add(root);
    }).catch(function () {
      if (show.state !== "dead") show.state = "idle";
    });
  }

  function streamShows() {
    if (!heroResident) return;
    let best = 0;
    let bestW = -1;
    shows.forEach(function (show, i) {
      if (show.raw > bestW) { bestW = show.raw; best = i; }
    });
    const scrolled = window.scrollY > 40;
    shows.forEach(function (show, i) {
      if (!show.spec) return;
      const keep = scrolled && (i === best || i === best + 1);
      if (keep && show.state === "idle") loadShow(show);
    });
  }

  function updateShows(dt, tSec) {
    sectionMix();
    streamShows();
    let sum = 0;
    const sharp = shows.map(function (show) {
      const s = Math.pow(Math.max(0, show.raw), 2.4);
      sum += s;
      return s;
    });
    if (sum < 0.001) sum = 1;
    if (lumTest) {
      host.dataset.models = shows.filter(function (show) { return show.root && show.spec; }).map(function (show) { return show.spec.id; }).join(",");
    }
    const stepEl = document.querySelector("#how .step.is-on");
    let step = 0;
    document.querySelectorAll("#how .step").forEach(function (el, n) { if (el === stepEl) step = n; });
    shows.forEach(function (show, i) {
      const el = document.getElementById(i === 0 ? "top" : show.spec.id);
      show.travel = sectionTravel(el);
      show.weight = THREE.MathUtils.damp(show.weight, sharp[i] / sum, 4.2, dt);
      if (!show.root || !show.spec) return;
      const vis = show.weight * (1 - Math.min(1, (pose.book || 0) * 1.7));
      const alpha = vis <= 0.02 ? 0 : Math.min(1, (vis - 0.02) / 0.72);
      show.root.visible = alpha > 0.02;
      show.mats.forEach(function (mat) {
        mat.opacity = alpha;
        mat.depthWrite = alpha > 0.35;
        if (mat.userData.baseEnv) {
          mat.envMapIntensity = mat.userData.baseEnv;
          mat.emissiveIntensity = mat.userData.baseEmit || 1;
        }
      });
      const tr = show.travel;
      const motion = show.spec.motion;
      if (motion === "vault") {
        show.yaw = THREE.MathUtils.damp(show.yaw, (tr - 0.5) * 1.15, 2.2, dt);
        show.root.rotation.set(0.06, show.yaw + tSec * 0.05, 0);
        show.root.scale.setScalar(MODEL_SCALE);
      } else if (motion === "cage") {
        show.step = THREE.MathUtils.damp(show.step, step, 2.6, dt);
        show.root.rotation.set(0.04, show.step * (Math.PI / 2) + tSec * 0.04, 0);
        show.root.scale.setScalar(MODEL_SCALE);
      } else if (motion === "record") {
        show.root.rotation.set(0.18, tr * 1.25 + tSec * 0.03, 0);
        show.root.scale.setScalar(MODEL_SCALE);
      } else if (motion === "podium") {
        show.root.rotation.set(0, 0, 0);
        show.root.scale.setScalar(MODEL_SCALE);
      } else if (motion === "lattice") {
        show.root.rotation.set(0.22 * Math.sin(tr * Math.PI), tr * 1.5 + tSec * 0.07, 0.08);
        show.root.scale.setScalar(MODEL_SCALE);
      } else if (motion === "plumb") {
        show.swing = show.swing * Math.exp(-1.4 * dt) + scrollV * 0.0011;
        show.swing = THREE.MathUtils.clamp(show.swing, -0.11, 0.11);
        show.root.rotation.set(0, tSec * 0.08, show.swing);
        show.root.scale.setScalar(MODEL_SCALE);
      }
    });
  }

  function rawStory() {
    const road = document.getElementById("roadmap");
    const end = road ? road.offsetTop + road.offsetHeight * 0.7 : document.body.scrollHeight;
    const start = hero.offsetTop;
    return clamp01((window.scrollY - start) / Math.max(1, end - start));
  }

  function spring(value, vel, target, dt) {
    const k = HERO3D.crystal.tilt.k;
    const d = HERO3D.crystal.tilt.damp;
    const v = (vel + (target - value) * k * dt) * Math.exp(-d * dt);
    return { value: value + v * dt, vel: v };
  }

  function frame(now) {
    if (!active) return;
    raf = requestAnimationFrame(frame);
    const raw = Math.max(0.001, (now - clock) / 1000);
    const dt = Math.min(0.1, raw);
    clock = now;
    if (meshReady && playIntro && introT < 20) {
      introT = (now - meshReadyAt) / 1000;
      if (introT > 0.68) document.documentElement.classList.add("intro-go");
      if (introT > 2.3) finishIntro();
    }

    const amp = reduced ? 0.25 : 1;
    const tx = look.nx * HERO3D.crystal.tilt.y * amp;
    const ty = -look.ny * HERO3D.crystal.tilt.x * amp;
    const sy = spring(tiltS.y, tiltS.vy, reduced ? tx * 0.25 : tx, dt);
    const sx = spring(tiltS.x, tiltS.vx, reduced ? ty * 0.25 : ty, dt);
    tiltS.y = sy.value;
    tiltS.vy = sy.vel;
    tiltS.x = sx.value;
    tiltS.vx = sx.vel;
    if (!drag.on) {
      drag.v += (0 - drag.x) * 10 * dt;
      drag.v *= Math.exp(-2.6 * dt);
      drag.x += drag.v * dt;
    }

    const follow = Math.min(0.2, raw);
    const storyTarget = rawStory();
    storyS = posed ? THREE.MathUtils.damp(storyS, storyTarget, reduced ? 14 : 2.6, follow) : storyTarget;
    const goal = reduced ? snapHero() : desired();
    const lambda = reduced ? 18 : 4.2;
    if (!posed) {
      Object.assign(pose, goal);
      posed = true;
    } else {
      pose.x = THREE.MathUtils.damp(pose.x, goal.x, lambda, follow);
      pose.y = THREE.MathUtils.damp(pose.y, goal.y, lambda, follow);
      pose.scale = THREE.MathUtils.damp(pose.scale, goal.scale, lambda, follow);
      pose.split = THREE.MathUtils.damp(pose.split, goal.split, 3.2, follow);
      pose.body = THREE.MathUtils.damp(pose.body, goal.body, 3.4, follow);
      pose.edge = THREE.MathUtils.damp(pose.edge, goal.edge, 3.4, follow);
      pose.hidden = THREE.MathUtils.damp(pose.hidden, goal.hidden, 3.2, follow);
      pose.orbit = THREE.MathUtils.damp(pose.orbit, goal.orbit, 3.2, follow);
      pose.camZ = THREE.MathUtils.damp(pose.camZ, goal.camZ, 6, follow);
      pose.spin = THREE.MathUtils.damp(pose.spin, goal.spin, 3.6, follow);
      pose.rotZ = THREE.MathUtils.damp(pose.rotZ, goal.rotZ, 3.6, follow);
      pose.light = THREE.MathUtils.damp(pose.light, goal.light, 3, follow);
      pose.proof = THREE.MathUtils.damp(pose.proof, goal.proof, 3.4, follow);
      pose.side = THREE.MathUtils.damp(pose.side, goal.side || 0, 2.8, follow);
      pose.lift = THREE.MathUtils.damp(pose.lift, goal.lift || 0, 2.8, follow);
      pose.fog = THREE.MathUtils.damp(pose.fog, goal.fog || 0, 2.2, follow);
      pose.podium = THREE.MathUtils.damp(pose.podium, goal.podium || 0, 3.4, follow);
      pose.dolly = THREE.MathUtils.damp(pose.dolly, goal.dolly || 0, 2.2, follow);
      pose.book = THREE.MathUtils.damp(pose.book || 0, goal.book || 0, 3.2, follow);
      pose.heroP = goal.heroP;
      if (mobile) {
        pose.x = goal.x;
        pose.y = goal.y;
        pose.scale = goal.scale;
      }
    }
    pose.camZ = THREE.MathUtils.clamp(pose.camZ || 6.8, 5.5, 8.4);
    pose.scale = THREE.MathUtils.clamp(pose.scale || 1, 0.16, 1.55);
    if (heldScale) pose.scale = THREE.MathUtils.clamp(pose.scale, heldScale - 0.045, heldScale + 0.045);
    if (heldCam) pose.camZ = THREE.MathUtils.clamp(pose.camZ, heldCam - 0.12, heldCam + 0.12);
    heldScale = pose.scale;
    heldCam = pose.camZ;

    const edgeEase = playIntro ? expoOut(clamp01(introT / HERO3D.intro.edgesS)) : 1;
    const bodyEase = playIntro ? expoOut(clamp01((introT - HERO3D.intro.bodyDelayS) / 0.8)) : 1;
    const nodeEase = playIntro ? expoOut(clamp01((introT - 1.1) / 0.55)) : 1;
    const buildP = playIntro ? elasticOut(clamp01(introT / 1.65)) : 1;
    const introScale = playIntro ? 0.58 + 0.42 * buildP : 1;
    const introRot = playIntro ? (1 - bodyEase) * -0.6 : 0;
    if (!reduced) idle += dt * HERO3D.crystal.idleSpin;
    const bob = reduced ? 0 : Math.sin(now * 0.001 * HERO3D.crystal.bobFreq) * HERO3D.crystal.bobAmp;

    const kFast = 1 - Math.pow(0.95, dt * 60);
    const kSlow = 1 - Math.pow(0.965, dt * 60);
    const aim = reduced ? 0.25 : 1;
    rate.fx += (look.nx - rate.fx) * kFast;
    rate.fy += (look.ny - rate.fy) * kFast;
    rate.sx += (look.nx - rate.sx) * kSlow;
    rate.sy += (look.ny - rate.sy) * kSlow;
    const camYaw = -rate.fx * 0.045 * aim;
    const pitch = rate.fy * 0.03 * aim;
    const roll = reduced ? 0 : (rate.fx - rate.sx) * 0.06;
    const tSec = now * 0.001;
    const drift = reduced ? 0 : Math.sin(tSec * 1.256) * 0.012 + Math.sin(tSec * 3.455) * 0.008;
    const driftRot = reduced ? 0 : Math.sin(tSec * 1.256) * 0.006 + Math.sin(tSec * 3.455) * 0.004;
    camPx = pose.side + camYaw * 1.4 + drift;
    camPy = pose.lift + pitch * 1.1 + drift * 0.6;
    sweep = THREE.MathUtils.damp(sweep, look.nx * 0.35 * amp, 2, dt);
    if (scene.environmentRotation) scene.environmentRotation.y = sweep + camYaw + tSec * 0.05;
    scene.background.copy(fogNear).lerp(fogFar, pose.fog * 0.65);
    scene.fog.color.copy(scene.background);
    scene.fog.density = 0.04 + pose.fog * 0.03;
    dust.rotation.y = tSec * 0.012;
    dust.position.y = Math.sin(tSec * 0.15) * 0.08;

    const hall = pose.podium;
    const bookK = Math.min(1, pose.book || 0);
    const boardShow = shows[4];
    const boardSlide = boardShow && boardShow.weight > 0.04
      ? boardShow.weight * THREE.MathUtils.lerp(-0.42, 0.42, sectionTravel(document.getElementById("board")))
      : 0;
    sectionAmb.intensity = 0.38;
    sectionKey.intensity = 1.15;
    sectionFill.intensity = 0.9;
    sectionRim.intensity = 1.05;
    const lock = mobile ? 1 : smootherstep(clamp01((bookK - 0.12) / 0.5));
    const freeX = camPx + pose.dolly + boardSlide;
    const freeY = 0.12 + camPy + hall * 0.04;
    const camX = freeX * (1 - lock);
    const camY = freeY * (1 - lock) + 0.08 * lock;
    camera.position.set(camX, camY, pose.camZ);
    camera.lookAt(
      freeX * 0.28 * (1 - hall) * (1 - lock),
      (camPy * 0.22 * (1 - hall) + hall * 0.02) * (1 - lock),
      0
    );
    camera.rotation.z += roll + driftRot;
    const rule = document.getElementById("hero-rule");
    if (rule) rule.classList.toggle("is-apart", pose.heroP > 0.52 && bookK < 0.2);

    rig.position.set(pose.x, pose.y + bob * (1 - bookK), 0);
    rig.scale.setScalar(pose.scale * introScale);
    const slotG = slotDesired(Math.max(4.8, pose.camZ));
    if (mobile || !slotPosed) {
      slotPose.x = slotG.x;
      slotPose.y = slotG.y;
      slotPose.scale = slotG.scale;
      slotPosed = true;
    } else {
      slotPose.x = THREE.MathUtils.damp(slotPose.x, slotG.x, lambda, follow);
      slotPose.y = THREE.MathUtils.damp(slotPose.y, slotG.y, lambda, follow);
      slotPose.scale = THREE.MathUtils.damp(slotPose.scale, slotG.scale, lambda, follow);
    }
    slotPose.scale = THREE.MathUtils.clamp(slotPose.scale, 0.2, 1.55);
    if (heldSlot) slotPose.scale = THREE.MathUtils.clamp(slotPose.scale, heldSlot - 0.045, heldSlot + 0.045);
    heldSlot = slotPose.scale;
    slot.position.set(slotPose.x, slotPose.y, 0);
    slot.scale.setScalar(slotPose.scale);
    scrollV = THREE.MathUtils.damp(scrollV, (window.scrollY - lastScroll) / Math.max(dt, 0.016), 3, dt);
    lastScroll = window.scrollY;
    updateShows(dt, tSec);
    tilt.rotation.x = tiltS.x;
    tilt.rotation.y = tiltS.y;
    tilt.rotation.z = pose.rotZ;
    yaw.rotation.y = idle + pose.spin + drag.x + introRot;

    topGroup.position.y = pose.split * 0.35;
    botGroup.position.y = -pose.split * 0.35;
    const hallFade = 1 - smootherstep(clamp01(pose.podium / 0.7));
    const bodyOpacity = pose.body * (playIntro ? bodyEase : 1) * Math.max(hallFade, bookK);
    bodyMat.opacity = bodyOpacity;
    bodyMat.depthWrite = bodyOpacity > 0.9;
    bodyMat.roughness = THREE.MathUtils.lerp(HERO3D.material.roughness, 0.62, bookK);
    bodyMat.clearcoatRoughness = THREE.MathUtils.lerp(HERO3D.material.clearcoatRoughness, 0.45, bookK);
    bodyMat.envMapIntensity = THREE.MathUtils.lerp(HERO3D.material.envMapIntensity, 0.4, bookK);
    bodyMat.emissive.setHex(0x2a2824);
    bodyMat.emissiveIntensity = bookK * 0.18;
    solidMat.opacity = pose.edge * edgeEase * hallFade * 0.85;
    glintMat.opacity = pose.edge * edgeEase * 0.32 * hallFade;
    glintMat.dashOffset = -((reduced ? 0 : now * 0.001) * HERO3D.edges.sweep);
    hiddenMat.opacity = pose.hidden * edgeEase * hallFade;
    hiddenLines.forEach(function (line) { line.visible = hiddenMat.opacity > 0.04; });

    if (inner) {
      const heroHere = shows[0].raw > 0.55 && bookK < 0.12;
      inner.visible = heroHere && pose.split > 0.12;
      innerMat.opacity = heroHere ? Math.min(1, pose.split * 1.25) : 0;
      const coreScale = MODEL_SCALE * (0.72 + pose.split * 0.28);
      inner.scale.setScalar(coreScale);
      inner.rotation.y = idle * 0.6;
    }

    orbits.scale.setScalar(0.6 + 0.4 * nodeEase);
    nodeMat.opacity = nodeEase * hallFade * (mobile ? 0 : 1);
    nodeEdgeMat.opacity = nodeEase * hallFade * (mobile ? 0 : 1);
    ringMat.opacity = mobile ? 0 : HERO3D.nodes.ringOpacity * nodeEase * (0.35 + pose.orbit * 0.65) * hallFade * (1 - bookK);
    const glowAmt = !mobile && shows[0].raw > 0.7 && bookK < 0.06 ? 0.4 * hallFade : 0;
    backlight.material.opacity = glowAmt;
    backlight.visible = glowAmt > 0.03;
    rig.visible = hallFade > 0.04;
    orbits.visible = !mobile && hallFade > 0.04 && bookK < 0.2;
    if (floor) floor.visible = !mobile && bookK < 0.28;

    let hoverIndex = -1;
    if (fine && !mobile && !drag.on) {
      ray.setFromCamera(pointer, camera);
      const hits = ray.intersectObjects(sats.map(function (sat) { return sat.hit; }));
      if (hits.length) hoverIndex = hits[0].object.userData.index;
    }
    sats.forEach(function (sat) {
      sat.hover = sat.index === hoverIndex;
      const speed = (Math.PI * 2) / sat.period;
      const hoverMul = sat.hover ? 0.5 : 1;
      sat.angle += reduced ? 0 : dt * speed * hoverMul * (1 - pose.proof);
      const lineup = [0.35, 1.55, 2.75][sat.index];
      sat.angle += shortAngle(sat.angle, lineup) * pose.proof * Math.min(1, dt * 3.2);
      sat.pivot.rotation.y = sat.angle;
      const nodeScale = 0.18 * (sat.hover ? 1.45 : 1);
      if (sat.node) sat.node.scale.setScalar(nodeScale);
    });

    const pulse = signEnvelope(now * 0.001);
    const envTarget = reduced ? 0.42 : Math.max(pulse, pose.proof * 0.96);
    envIn = THREE.MathUtils.damp(envIn, envTarget, 4.5, dt);
    const pair = Math.floor(now / 1000 / HERO3D.nodes.signEveryS) % 3;
    const pairIdx = [[0, 1], [1, 2], [2, 0]][pair];
    const gate = window.innerWidth * (mobile ? 0.22 : 0.4);
    signLines.forEach(function (line, i) {
      const sat = sats[pairIdx[i]];
      sat.orb.getWorldPosition(tmp);
      apexMark.getWorldPosition(tmp2);
      line.geometry.setPositions([tmp.x, tmp.y, tmp.z, tmp2.x, tmp2.y, tmp2.z]);
      line.computeLineDistances();
      const a = tmp.clone().project(camera);
      const b = tmp2.clone().project(camera);
      const ax = (a.x * 0.5 + 0.5) * window.innerWidth;
      const bx = (b.x * 0.5 + 0.5) * window.innerWidth;
      const calm = ax > gate && bx > gate && a.z < 1 && b.z < 1 ? 1 : 0;
      line.material.opacity = mobile ? 0 : envIn * nodeEase * 0.4 * calm * hallFade * (1 - Math.min(1, bookK * 3));
    });

    if (shardPieces.length) {
      const fade = playIntro ? 1 - clamp01((introT - 1.45) / 0.4) : 0;
      shardMat.opacity = fade;
      shardPieces.forEach(function (piece) {
        const local = playIntro ? elasticOut(clamp01((introT - piece.delay) / 1.35)) : 1;
        piece.mesh.position.copy(piece.dir).multiplyScalar((1 - local) * 1.15);
        piece.mesh.visible = fade > 0.03;
      });
    }

    placePins(nodeEase, hoverIndex);
    placeGlow();

    const tail = document.getElementById("close") || document.getElementById("faq");
    const pastStory = tail && tail.getBoundingClientRect().bottom < 48;
    const footerEl = document.getElementById("footer");
    const footerTop = footerEl ? footerEl.getBoundingClientRect().top : 99999;
    const closeBottom = tail ? tail.getBoundingClientRect().bottom : 0;
    const parked = closeBottom < window.innerHeight * 0.12 && footerTop < window.innerHeight * 0.42;
    stageFade = THREE.MathUtils.damp(stageFade, pastStory || parked ? 0 : 1, 3.5, dt);
    stage.style.opacity = stageFade.toFixed(3);
    if (pastStory) {
      setActive(false);
      return;
    }

    if (bloomOn) {
      renderer.toneMapping = THREE.NoToneMapping;
      const crossing = pose.podium > 0.2 && pose.podium < 0.8;
      const bloomTarget = HERO3D.bloom.strength * (crossing ? 0.72 : 1);
      const exposureTarget = crossing ? 0.94 : 1;
      bloomLevel = THREE.MathUtils.damp(bloomLevel, bloomTarget, 2.2, dt);
      exposureLevel = THREE.MathUtils.damp(exposureLevel, exposureTarget, 2.2, dt);
      bloomLevel = THREE.MathUtils.clamp(bloomLevel, 0.12, HERO3D.bloom.strength);
      exposureLevel = THREE.MathUtils.clamp(exposureLevel, 0.9, 1);
      grade.strength(bloomLevel);
      renderer.toneMappingExposure = exposureLevel;
      try {
        grade.time(Math.floor(now / 41.67));
        grade.render();
      } catch (err) {
        bloomOn = false;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.setRenderTarget(null);
        renderer.render(scene, camera);
      }
    } else {
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.setRenderTarget(null);
      renderer.render(scene, camera);
    }

    if (!reduced && !forceHQ && tier < dprLadder.length - 1) {
      frameMs.push(dt * 1000);
      if (frameMs.length >= 40) {
        const sorted = frameMs.slice().sort(function (a, b) { return a - b; });
        const body = sorted.slice(1, sorted.length - 1);
        const avg = body.reduce(function (a, b) { return a + b; }, 0) / Math.max(1, body.length);
        frameMs.length = 0;
        if (avg > HERO3D.perf.frameBudgetMs) {
          tier += 1;
          dprCap = dprLadder[Math.min(tier, dprLadder.length - 1)];
          if (tier >= dprLadder.length - 1) bloomOn = false;
          resize();
        }
      }
    }
  }

  function snapHero() {
    const camZ = 7.2;
    const band = bandScreen("top");
    const at = band
      ? projectAt(band.sx, band.sy, camZ, band.px, 0.4, 1.6)
      : projectAt(window.innerWidth * 0.63, window.innerHeight * 0.48, camZ, window.innerHeight * 0.86, 0.45, 1.85);
    return {
      x: at.x,
      y: at.y,
      scale: at.scale,
      split: 0,
      body: 1,
      edge: 0,
      hidden: 0,
      orbit: mobile ? 0 : 1,
      camZ: camZ,
      spin: 0.2,
      rotZ: 0,
      light: 0,
      proof: 0,
      heroP: 0,
      side: 0,
      lift: 0,
      fog: 0,
      podium: 0,
      dolly: 0,
      book: 0
    };
  }

  function placeGlow() {
    const glow = document.getElementById("hero-glow");
    if (!glow) return;
    rig.getWorldPosition(tmp);
    tmp.project(camera);
    const cx = (tmp.x * 0.5 + 0.5) * window.innerWidth;
    const cy = (-tmp.y * 0.5 + 0.5) * window.innerHeight;
    const restX = window.innerWidth * (mobile ? 0.5 : 0.72);
    const restY = window.innerHeight * 0.42;
    const gx = restX + (cx - restX) * 0.3;
    const gy = restY + (cy - restY) * 0.3;
    glow.style.left = gx.toFixed(1) + "px";
    glow.style.top = gy.toFixed(1) + "px";
  }

  function placePins(nodeEase, hoverIndex) {
    if (hud.root.hidden) return;
    const hr = hero.getBoundingClientRect();
    const vh = window.innerHeight || 1;
    const inHero = hr.top < vh * 0.42 && hr.bottom > vh * 0.72;
    const show = inHero
      ? (nodeEase > 0.72 ? Math.min(1, (nodeEase - 0.72) / 0.28) : 0) * (1 - Math.min(1, pose.podium * 1.4)) * (1 - Math.min(1, (pose.book || 0) * 4))
      : 0;
    hud.root.style.visibility = show > 0.04 ? "visible" : "hidden";
    if (show <= 0.04) {
      hud.apex.style.opacity = "0";
      hud.girdle.style.opacity = "0";
      hud.node.hidden = true;
      hud.lineA.setAttribute("stroke-opacity", "0");
      hud.lineB.setAttribute("stroke-opacity", "0");
      return;
    }
    projectPin(hud.apex, apexMark, -78, -36, show * faceAmount(apexMark, new THREE.Vector3(0, 1, 0)));
    projectPin(hud.girdle, girdleMark, 22, 18, show * faceAmount(girdleMark, new THREE.Vector3(1, 0, 0)));
    hud.leaders.setAttribute("viewBox", "0 0 " + window.innerWidth + " " + window.innerHeight);
    setLeader(hud.lineA, hud.apex);
    setLeader(hud.lineB, hud.girdle);
    if (hoverIndex >= 0) {
      const sat = sats[hoverIndex];
      sat.orb.getWorldPosition(tmp);
      tmp.project(camera);
      const x = (tmp.x * 0.5 + 0.5) * window.innerWidth;
      const y = (-tmp.y * 0.5 + 0.5) * window.innerHeight;
      hud.node.hidden = false;
      hud.node.style.opacity = "1";
      hud.node.style.transform = "translate(" + (x + 14).toFixed(1) + "px," + (y - 28).toFixed(1) + "px)";
      hud.node.textContent = "[ VALIDATOR 0" + (hoverIndex + 1) + " · SIGNED ]";
    } else {
      hud.node.hidden = true;
    }
    typePins(show);
  }

  function faceAmount(mark, localNormal) {
    mark.getWorldPosition(tmp);
    tmp2.copy(localNormal).transformDirection(mark.matrixWorld);
    const view = camera.position.clone().sub(tmp).normalize();
    return tmp2.dot(view) > -0.15 ? 1 : 0;
  }

  function projectPin(pin, mark, ox, oy, alpha) {
    mark.getWorldPosition(tmp);
    tmp.project(camera);
    const behind = tmp.z > 1;
    const ax = (tmp.x * 0.5 + 0.5) * window.innerWidth;
    const ay = (-tmp.y * 0.5 + 0.5) * window.innerHeight;
    pin.dataset.ax = ax.toFixed(1);
    pin.dataset.ay = ay.toFixed(1);
    const w = Math.max(pin.offsetWidth, 132);
    const h = Math.max(pin.offsetHeight, 22);
    const margin = 12;
    let x = ax + ox;
    let y = ay + oy;
    if (x + w > window.innerWidth - margin) x = ax - w - 14;
    if (x < margin) x = margin;
    if (x + w > window.innerWidth - margin) x = window.innerWidth - margin - w;
    if (y < 78) y = 78;
    if (y + h > window.innerHeight - margin) y = window.innerHeight - margin - h;
    document.querySelectorAll(".idx").forEach(function (el) {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      const hit = x < r.right + 10 && x + w > r.left - 10 && y < r.bottom + 8 && y + h > r.top - 8;
      if (!hit) return;
      const below = r.bottom + 10;
      if (below + h < window.innerHeight - margin) y = below;
      else y = Math.max(78, r.top - h - 10);
    });
    pin.style.transform = "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px)";
    pin.style.opacity = behind ? "0" : String(alpha);
  }

  function setLeader(line, pin) {
    const x1 = Number(pin.dataset.ax || 0);
    const y1 = Number(pin.dataset.ay || 0);
    const box = pin.getBoundingClientRect();
    line.setAttribute("x1", x1.toFixed(1));
    line.setAttribute("y1", y1.toFixed(1));
    line.setAttribute("x2", (box.left + 8).toFixed(1));
    line.setAttribute("y2", (box.top + box.height * 0.5).toFixed(1));
    line.setAttribute("stroke-opacity", pin.style.opacity || "0");
  }

  let typed = false;
  function typePins(show) {
    if (typed || show < 0.99 || reduced) {
      if (reduced || !playIntro) {
        hud.apex.textContent = hud.apex.dataset.full;
        hud.girdle.textContent = hud.girdle.dataset.full;
      }
      return;
    }
    typed = true;
    [hud.apex, hud.girdle].forEach(function (pin, index) {
      const full = pin.dataset.full;
      const start = performance.now() + index * 80;
      function tick(now) {
        const n = Math.max(0, Math.floor((now - start) / 18));
        pin.textContent = full.slice(0, n);
        if (n < full.length) requestAnimationFrame(tick);
        else pin.textContent = full;
      }
      requestAnimationFrame(tick);
    });
  }

  function nearCrystal(x, y) {
    let shown = pose.podium < 0.4 && rig.visible;
    shows.forEach(function (show) {
      if (show.root && show.root.visible && show.weight > 0.45) shown = true;
    });
    if (!shown) return false;
    const anchor = pose.podium < 0.4 ? rig : slot;
    anchor.getWorldPosition(tmp);
    const edge = tmp.clone();
    edge.y += HERO3D.crystal.height * 0.35 * Math.abs(anchor.scale.y || 1);
    tmp.project(camera);
    edge.project(camera);
    if (tmp.z > 1) return false;
    const cx = (tmp.x * 0.5 + 0.5) * window.innerWidth;
    const cy = (-tmp.y * 0.5 + 0.5) * window.innerHeight;
    const ey = (-edge.y * 0.5 + 0.5) * window.innerHeight;
    const reach = Math.max(24, Math.abs(cy - ey) * 0.42);
    return Math.hypot(x - cx, y - cy) < reach;
  }

  function setActive(on) {
    if (on === active && raf) return;
    active = on;
    if (on) {
      clock = performance.now();
      raf = requestAnimationFrame(frame);
    } else {
      cancelAnimationFrame(raf);
      raf = 0;
    }
  }

  function onPointerMove(event) {
    const w = window.innerWidth || 1;
    const h = window.innerHeight || 1;
    look.nx = ((event.clientX / w) * 2 - 1);
    look.ny = ((event.clientY / h) * 2 - 1);
    pointer.x = look.nx;
    pointer.y = -look.ny;
    if (drag.on) {
      const dx = event.clientX - drag.lastX;
      const t = performance.now();
      const step = Math.max(0.008, (t - drag.lastT) / 1000);
      drag.x += dx * 0.0055;
      drag.v = (dx * 0.0055) / step;
      drag.lastX = event.clientX;
      drag.lastT = t;
    }
    const overUi = event.target.closest && event.target.closest("a, button, input, textarea, summary, .nav-bar, .ax-skip, .hero-actions, .close");
    const zone = !reduced && fine && !mobile && !overUi && nearCrystal(event.clientX, event.clientY);
    document.body.dataset.axCursor = zone ? "drag" : "";
  }

  function onPointerDown(event) {
    if (reduced || !fine || mobile || event.button !== 0) return;
    if (event.target.closest && event.target.closest("a, button, input, textarea, summary, .nav-bar, .ax-skip")) return;
    if (!nearCrystal(event.clientX, event.clientY)) return;
    drag.on = true;
    drag.lastX = event.clientX;
    drag.lastT = performance.now();
  }

  function onPointerUp() { drag.on = false; }

  function storyOn() {
    if (document.hidden) return false;
    const tailEl = document.getElementById("close") || document.getElementById("faq");
    if (tailEl && tailEl.getBoundingClientRect().bottom < 48) return false;
    return true;
  }
  const seenIO = new IntersectionObserver(function () {
    setActive(storyOn());
  }, { threshold: 0 });
  seenIO.observe(document.body);
  document.addEventListener("visibilitychange", function () {
    frameMs.length = 0;
    setActive(storyOn());
  });
  window.addEventListener("scroll", function () { setActive(storyOn()); }, { passive: true });
  window.addEventListener("pointermove", onPointerMove, { passive: true });
  window.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("resize", resize);
  resize();
  raf = requestAnimationFrame(frame);

  window.addEventListener("pagehide", function () {
    try { sessionStorage.setItem("axv-scroll", String(window.scrollY)); } catch (err) { /* ignore */ }
    setActive(false);
    grade.dispose();
    renderer.dispose();
    envMap.dispose();
  }, { once: true });
}

function buildHud() {
  const root = document.createElement("div");
  root.id = "crystal-hud";
  root.innerHTML = "<svg class=\"leaders\" aria-hidden=\"true\"><line data-lead=\"a\"></line><line data-lead=\"b\"></line></svg>"
    + "<p class=\"pin\" data-pin=\"apex\" data-full=\"[ APEX · GRADE HOLDS ]\"></p>"
    + "<p class=\"pin\" data-pin=\"girdle\" data-full=\"[ GIRDLE · 2 OF 3 SIGN ]\"></p>"
    + "<p class=\"pin\" data-pin=\"node\" hidden>[ VALIDATOR 01 · SIGNED ]</p>";
  document.body.appendChild(root);
  return {
    root: root,
    apex: root.querySelector("[data-pin=\"apex\"]"),
    girdle: root.querySelector("[data-pin=\"girdle\"]"),
    node: root.querySelector("[data-pin=\"node\"]"),
    leaders: root.querySelector("svg"),
    lineA: root.querySelector("[data-lead=\"a\"]"),
    lineB: root.querySelector("[data-lead=\"b\"]")
  };
}

function buildChrome(playIntro) {
  const markup = "<div class=\"frame\"><div class=\"ax-mark\" aria-hidden=\"true\"><i class=\"ring ring-a\"></i><i class=\"ring ring-b\"></i><span class=\"orbit o1\"><i></i></span><span class=\"orbit o2\"><i></i></span><span class=\"orbit o3\"><i></i></span></div><p class=\"pct\">[ 000% SYNCING ]</p><div class=\"bar\"><i></i></div></div>";
  let loader = document.getElementById("ax-loader");
  if (!loader) {
    loader = document.createElement("div");
    loader.id = "ax-loader";
    loader.innerHTML = markup;
    document.body.appendChild(loader);
  } else if (!loader.querySelector(".pct")) {
    loader.innerHTML = markup;
  }
  let status = document.getElementById("ax-status");
  if (!status) {
    status = document.createElement("p");
    status.id = "ax-status";
    status.className = "ax-status";
    status.textContent = "[ SEEDING SANDBOX ]";
    document.body.appendChild(status);
  }
  let skip = document.querySelector(".ax-skip");
  if (!skip) {
    skip = document.createElement("button");
    skip.type = "button";
    skip.className = "ax-skip";
    skip.textContent = "[ SKIP ]";
    document.body.appendChild(skip);
  }
  if (playIntro) document.documentElement.classList.add("show-loader");
  else document.documentElement.classList.remove("show-loader");
  loader.hidden = !playIntro;
  status.hidden = !playIntro;
  skip.hidden = !playIntro;
  skip.tabIndex = playIntro ? 0 : -1;
  document.documentElement.classList.remove("hold-hero");
  let skipFn = function () {};
  let settled = false;
  skip.addEventListener("click", function () { skipFn(); });
  const failSafe = window.setTimeout(function () {
    if (settled) return;
    write(100, "online");
    loaded();
  }, 8000);
  function write(n, phase) {
    const pct = loader.querySelector(".pct");
    const bar = loader.querySelector(".bar i");
    const clamped = Math.max(0, Math.min(100, Math.round(n)));
    let line = "[ SEEDING SANDBOX ]";
    if (phase === "scroll") line = "[ SCROLL TO VERIFY ]";
    else if (phase === "online" || clamped >= 100) line = "[ VALIDATORS ONLINE ]";
    else if (clamped >= 18) line = "[ VARIANTS " + String(clamped).padStart(3, "0") + "% ]";
    if (pct) pct.textContent = "[ " + String(clamped).padStart(3, "0") + "% SYNCING ]";
    if (bar) bar.style.width = clamped + "%";
    status.textContent = line;
  }
  function hideSkip() {
    skip.hidden = true;
    skip.classList.add("is-out");
    skip.tabIndex = -1;
  }
  function hideShell() {
    loader.hidden = true;
    status.hidden = true;
    hideSkip();
    document.documentElement.classList.remove("show-loader");
  }
  function loaded() {
    if (settled) return;
    settled = true;
    window.clearTimeout(failSafe);
    write(100, "online");
    window.setTimeout(function () { write(100, "scroll"); }, 900);
    window.setTimeout(function () {
      hideSkip();
      loader.classList.add("is-out");
      status.classList.add("is-out");
    }, 1600);
    window.setTimeout(hideShell, 2100);
  }
  return {
    onSkip: function (fn) { skipFn = fn; },
    progress: function (ratio) { write(ratio * 100); },
    loaded: loaded,
    hideLoader: function () {
      settled = true;
      window.clearTimeout(failSafe);
      hideShell();
    },
    hideSkip: hideSkip
  };
}

function webglOk() {
  try {
    const canvas = document.createElement("canvas");
    return !!(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch (err) {
    return false;
  }
}

function hdr(boost) {
  const c = new THREE.Color(ACCENT);
  return new THREE.Color(c.r * boost, c.g * boost, c.b * boost);
}

function trackLine(mat) {
  mat.resolution.set(window.innerWidth || 1, window.innerHeight || 1);
  lineMats.push(mat);
  return mat;
}

function lineMat(boost, opacity) {
  return trackLine(new LineMaterial({
    color: hdr(boost),
    linewidth: HERO3D.edges.width,
    transparent: true,
    opacity: opacity,
    toneMapped: false,
    depthWrite: false,
    alphaToCoverage: true
  }));
}

function fatLines(edges, material) {
  const geo = new LineSegmentsGeometry();
  geo.fromEdgesGeometry(edges);
  const line = new LineSegments2(geo, material);
  line.computeLineDistances();
  return line;
}

function topDpr(isMobile, force) {
  const native = window.devicePixelRatio || 1;
  const cap = isMobile ? HERO3D.perf.maxDprMobile : HERO3D.perf.maxDprDesktop;
  if (force) return Math.max(native, cap, isMobile ? 1.5 : 1.75);
  if (isMobile) return Math.min(native, cap);
  return Math.min(Math.max(native, 1.5), Math.max(cap, 1.5));
}

function sampleFlight(p) {
  const stops = [
    { at: 0, split: 0, body: 1, hidden: 0, orbit: 1, edge: 0, camZ: 6.8, side: 0, lift: 0, spin: 0.12, fog: 0.12, proof: 0, light: 0 },
    { at: 0.15, split: 0, body: 1, hidden: 0, orbit: 0.8, edge: 0, camZ: 6.9, side: -0.04, lift: 0.03, spin: 0.45, fog: 0.22, proof: 0, light: 0 },
    { at: 0.31, split: 0.55, body: 1, hidden: 0, orbit: 0.9, edge: 0, camZ: 6.5, side: 0.08, lift: 0.02, spin: 1.1, fog: 0.24, proof: 0.05, light: 0 },
    { at: 0.5, split: 0.04, body: 0.42, hidden: 0.9, orbit: 1, edge: 0.85, camZ: 6.6, side: -0.02, lift: 0.04, spin: 1.8, fog: 0.18, proof: 1, light: 0 },
    { at: 0.69, split: 0, body: 1, hidden: 0, orbit: 0.2, edge: 0, camZ: 5.7, side: 0, lift: 0.02, spin: 2.2, fog: 0.2, proof: 0, light: 0 },
    { at: 0.84, split: 0, body: 1, hidden: 0, orbit: 0.28, edge: 0, camZ: 7.8, side: 0.04, lift: 0.08, spin: 2.5, fog: 0.22, proof: 0, light: 0 },
    { at: 1, split: 0, body: 1, hidden: 0, orbit: 0.18, edge: 0, camZ: 8.6, side: 0.02, lift: 0.1, spin: 2.8, fog: 0.18, proof: 0, light: 0 }
  ];
  const x = clamp01(p);
  let i = 0;
  while (i < stops.length - 2 && x > stops[i + 1].at) i += 1;
  const a = stops[i];
  const b = stops[i + 1];
  const t = smootherstep((x - a.at) / Math.max(0.0001, b.at - a.at));
  const out = {};
  Object.keys(a).forEach(function (key) {
    if (key === "at") return;
    out[key] = a[key] + (b[key] - a[key]) * t;
  });
  return out;
}

function smootherstep(t) {
  const x = clamp01(t);
  return x * x * x * (x * (x * 6 - 15) + 10);
}

function elasticOut(t) {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  return Math.pow(2, -8 * t) * Math.sin((t * 8 - 0.75) * Math.PI) * 0.5 + 1;
}

function expoOut(p) {
  if (p <= 0) return 0;
  if (p >= 1) return 1;
  return 1 - Math.pow(2, -10 * p);
}

function clamp01(v) { return Math.max(0, Math.min(1, v)); }

function shortAngle(a, b) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return d;
}

function signEnvelope(t) {
  const local = (t + 5.6) % HERO3D.nodes.signEveryS;
  if (local < 0.6) return easeInOutSine(local / 0.6);
  if (local < 1.8) return 1;
  if (local < 2.6) return 1 - easeInOutSine((local - 1.8) / 0.8);
  return 0;
}

function easeInOutSine(p) {
  return -(Math.cos(Math.PI * clamp01(p)) - 1) / 2;
}

function meshesByName(root) {
  const map = {};
  root.traverse(function (obj) {
    if (obj.isMesh && obj.name) map[obj.name] = obj;
  });
  return map;
}

function makeEdges(geometry) {
  let edges = new THREE.EdgesGeometry(geometry, HERO3D.edges.thresholdDeg);
  let n = edges.getAttribute("position") ? edges.getAttribute("position").count : 0;
  if (n < 48) {
    edges.dispose();
    edges = new THREE.EdgesGeometry(geometry, 8);
    n = edges.getAttribute("position").count;
  }
  const maxVerts = 900;
  if (n > maxVerts) edges = keepLongest(edges, maxVerts / 2);
  return edges;
}

function keepLongest(edges, maxSegments) {
  const pos = edges.getAttribute("position").array;
  const segs = [];
  for (let i = 0; i < pos.length; i += 6) {
    const dx = pos[i + 3] - pos[i];
    const dy = pos[i + 4] - pos[i + 1];
    const dz = pos[i + 5] - pos[i + 2];
    segs.push(dx * dx + dy * dy + dz * dz, i);
  }
  const order = [];
  for (let i = 0; i < segs.length; i += 2) order.push(i);
  order.sort(function (a, b) { return segs[b] - segs[a]; });
  const keep = Math.min(maxSegments, order.length);
  const out = new Float32Array(keep * 6);
  for (let k = 0; k < keep; k += 1) {
    const at = segs[order[k] + 1];
    out.set(pos.subarray(at, at + 6), k * 6);
  }
  edges.dispose();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(out, 3));
  return geo;
}


function buildStudio() {
  const studio = new THREE.Scene();
  studio.background = new THREE.Color(0x000000);
  function bulb(radius, x, y, z, color, intensity) {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 20, 14),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity) })
    );
    mesh.position.set(x, y, z);
    studio.add(mesh);
  }
  bulb(0.38, -2.2, 1.3, 2.2, 0xffffff, 2.4);
  bulb(0.28, 2.4, 0.4, -2.0, 0xffffff, 1.8);
  bulb(0.22, 0.1, 2.5, 0.5, 0xffffff, 1.15);
  bulb(0.16, 1.6, -0.4, 2.0, 0xeef94b, 1.6);
  return studio;
}

function makeDust(count) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    pos[i * 3] = (Math.random() - 0.5) * 14;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 8;
    pos[i * 3 + 2] = -0.4 - Math.random() * 10;
  }
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.018,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.45,
    depthWrite: false,
    color: 0xd9d6c8,
    fog: true
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  return points;
}

function makeFloor() {
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {},
    vertexShader: "varying vec3 vPos; void main(){ vPos = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: [
      "varying vec3 vPos;",
      "void main(){",
      "  vec2 g = abs(fract(vPos.xz * 1.5) - 0.5);",
      "  float fw = max(fwidth(vPos.x), fwidth(vPos.z)) * 1.5;",
      "  float line = 1.0 - smoothstep(0.0, fw * 1.5, min(g.x, g.y));",
      "  float fade = exp(-length(vPos.xz) * 0.16);",
      "  gl_FragColor = vec4(0.93, 0.976, 0.294, line * fade * 0.22);",
      "}"
    ].join("\n")
  });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(48, 48), mat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1.9;
  floor.frustumCulled = false;
  return floor;
}

function backlightTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(128, 128, 4, 128, 128, 128);
  g.addColorStop(0, "rgba(255,255,255,0.22)");
  g.addColorStop(0.18, "rgba(238,249,75,0.08)");
  g.addColorStop(0.46, "rgba(238,249,75,0.03)");
  g.addColorStop(1, "rgba(238,249,75,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeComposer(renderer, scene, camera) {
  const composer = new EffectComposer(renderer);
  composer.renderTarget1.samples = 0;
  composer.renderTarget2.samples = 0;
  const renderPass = new RenderPass(scene, camera);
  const clampPass = new ShaderPass({
    uniforms: {
      tDiffuse: { value: null },
      uCap: { value: 0.72 }
    },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader: [
      "uniform sampler2D tDiffuse;",
      "uniform float uCap;",
      "varying vec2 vUv;",
      "void main(){",
      "  vec3 col = texture2D(tDiffuse, vUv).rgb;",
      "  float l = dot(col, vec3(0.2126, 0.7152, 0.0722));",
      "  col *= min(1.0, uCap / max(l, 1e-4));",
      "  gl_FragColor = vec4(col, 1.0);",
      "}"
    ].join("\n")
  });
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(2, 2), HERO3D.bloom.strength, HERO3D.bloom.radius, HERO3D.bloom.threshold);
  const gradePass = new ShaderPass({
    uniforms: {
      tDiffuse: { value: null },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader: [
      "uniform sampler2D tDiffuse;",
      "uniform float uTime;",
      "varying vec2 vUv;",
      "vec3 aces(vec3 x){",
      "  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);",
      "}",
      "float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }",
      "void main(){",
      "  vec2 dir = vUv - 0.5;",
      "  float r = length(dir);",
      "  vec2 off = dir * pow(r, 3.0) * 0.004;",
      "  float cr = texture2D(tDiffuse, vUv + off).r;",
      "  float cg = texture2D(tDiffuse, vUv).g;",
      "  float cb = texture2D(tDiffuse, vUv - off).b;",
      "  vec3 col = aces(vec3(cr, cg, cb));",
      "  col = clamp(col * 1.03 - 0.012, 0.0, 1.0);",
      "  float vig = smoothstep(1.12, 0.32, r);",
      "  col *= mix(0.86, 1.0, vig);",
      "  float n = hash(vUv * vec2(1440.0, 900.0) + uTime);",
      "  col += (n - 0.5) * 0.012;",
      "  gl_FragColor = vec4(col, 1.0);",
      "}"
    ].join("\n")
  });
  const output = new OutputPass();
  composer.addPass(renderPass);
  composer.addPass(clampPass);
  composer.addPass(bloomPass);
  composer.addPass(gradePass);
  composer.addPass(output);
  return {
    resize: function (w, h) {
      composer.setPixelRatio(renderer.getPixelRatio());
      composer.setSize(w, h);
    },
    time: function (frame) {
      gradePass.uniforms.uTime.value = frame;
    },
    strength: function (value) {
      bloomPass.strength = value;
    },
    render: function () {
      composer.render();
    },
    dispose: function () {
      composer.dispose();
    }
  };
}
