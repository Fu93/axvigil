/* Page-length crystal. three@0.170.0 via the import map.
   Scroll stays native; the camera and crystal ease toward it.
   No per-frame grain, no opacity blinking. */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

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
    color: 0x0a0b09,
    metalness: 0,
    roughness: 0.12,
    clearcoat: 1,
    clearcoatRoughness: 0.04,
    ior: 1.5,
    envMapIntensity: 1.15,
    iridescence: 0.15
  },
  edges: { thresholdDeg: 25, hdrBoost: 2.2, opacity: 0.9, sweep: 0.18 },
  bloom: { strength: 0.65, radius: 0.35, threshold: 0.92, halfRes: true },
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
  perf: { maxDprDesktop: 1.75, maxDprMobile: 1.5, frameBudgetMs: 22 }
};

const GLB = "assets/3d/axvigil_core_web.glb";
const ACCENT = HERO3D.accent;
let started = false;

export function mount() {
  if (started) return;
  started = true;
  const host = document.getElementById("hero-core");
  const stage = document.getElementById("stage");
  const hero = document.getElementById("top");
  if (!host || !stage || !hero) return;

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
    document.documentElement.classList.add("intro-go");
    return;
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
      stencil: false
    });
  } catch (err) {
    document.documentElement.classList.add("intro-go");
    return;
  }
  if (!renderer.getContext()) {
    document.documentElement.classList.add("intro-go");
    return;
  }

  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.domElement.setAttribute("aria-hidden", "true");
  stage.insertBefore(renderer.domElement, stage.querySelector(".stage-vignette"));
  const grain = stage.querySelector(".stage-grain");
  const vignette = stage.querySelector(".stage-vignette");
  if (grain) stage.appendChild(grain);
  if (vignette) stage.appendChild(vignette);

  const scene = new THREE.Scene();
  const fogNear = new THREE.Color(0x1c1d1a);
  const fogFar = new THREE.Color(0x3a3426);
  scene.fog = new THREE.FogExp2(0x1c1d1a, 0.012);
  const camera = new THREE.PerspectiveCamera(HERO3D.camera.fov, 1, 0.08, 40);
  camera.position.set(0, 0.08, HERO3D.camera.z);
  camera.layers.enable(1);

  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const envRim = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(ACCENT).multiplyScalar(3.2) })
  );
  envRim.position.set(9.5, 7.2, -8.4);
  envRim.scale.set(0.45, 6.2, 0.18);
  room.add(envRim);
  const envMap = pmrem.fromScene(room, 0.04).texture;
  scene.environment = envMap;
  pmrem.dispose();

  const strip = new THREE.DirectionalLight(ACCENT, 4.2);
  strip.position.set(2.8, 1.6, -3.4);
  scene.add(strip);
  const key = new THREE.DirectionalLight(0xfff6ea, 1.35);
  key.position.set(-4.2, 5.4, 4.6);
  scene.add(key);
  scene.add(new THREE.AmbientLight(0xd9d4c6, 0.22));
  const fill = new THREE.DirectionalLight(0xc5d0da, 0.9);
  fill.position.set(5.2, -1.4, 3.4);
  scene.add(fill);
  key.intensity = 2.35;

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
    color: 0x161710,
    metalness: HERO3D.material.metalness,
    roughness: HERO3D.material.roughness,
    clearcoat: HERO3D.material.clearcoat,
    clearcoatRoughness: HERO3D.material.clearcoatRoughness,
    ior: HERO3D.material.ior,
    specularIntensity: 1,
    envMap: envMap,
    envMapIntensity: 1.5,
    iridescence: HERO3D.material.iridescence,
    iridescenceIOR: 1.3,
    flatShading: false,
    transparent: true,
    opacity: playIntro ? 0 : 1,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1
  });

  const hiddenLines = [];
  const solidMat = lineMat(1.55, 0.62);
  const glintMat = new THREE.LineDashedMaterial({
    color: hdr(HERO3D.edges.hdrBoost),
    dashSize: 0.28,
    gapSize: 1.05,
    transparent: true,
    opacity: 0.95,
    toneMapped: false,
    depthWrite: false
  });
  const hiddenMat = lineMat(1.15, 0);
  hiddenMat.depthFunc = THREE.GreaterDepth;

  const nodeMat = new THREE.MeshBasicMaterial({
    color: hdr(2.15),
    toneMapped: false,
    transparent: true,
    opacity: playIntro ? 0 : 1
  });
  const ringMat = new THREE.LineBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.1,
    depthWrite: false,
    toneMapped: false
  });

  const inner = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.22, 0),
    new THREE.MeshBasicMaterial({
      color: hdr(2.3),
      toneMapped: false,
      transparent: true,
      opacity: 0,
      depthWrite: false
    })
  );
    inner.layers.enable(1);
  inner.userData.bloom = true;
  inner.visible = false;
  yaw.add(inner);

  const apexMark = new THREE.Object3D();
  apexMark.position.set(0, 1.2, 0);
  topGroup.add(apexMark);
  const girdleMark = new THREE.Object3D();
  girdleMark.position.set(0.72, 0, 0);
  yaw.add(girdleMark);

  const disc = new THREE.Sprite(new THREE.SpriteMaterial({
    map: discTexture(),
    color: 0x050505,
    transparent: true,
    depthWrite: false,
    opacity: 0
  }));
  disc.scale.set(4.4, 4.4, 1);
  disc.position.z = -0.85;
  disc.renderOrder = -2;
  rig.add(disc);

  const sats = HERO3D.nodes.radii.map(function (radius, i) {
    const pivot = new THREE.Group();
    pivot.rotation.x = THREE.MathUtils.degToRad(HERO3D.nodes.inclDeg[i]);
    const ringGeo = new THREE.BufferGeometry();
    const ringPts = [];
    for (let s = 0; s <= 96; s += 1) {
      const a = (s / 96) * Math.PI * 2;
      ringPts.push(Math.cos(a) * radius, 0, Math.sin(a) * radius);
    }
    ringGeo.setAttribute("position", new THREE.Float32BufferAttribute(ringPts, 3));
    const ring = new THREE.Line(ringGeo, ringMat);
    ring.visible = !mobile || i === 0;
    pivot.add(ring);
    const orb = new THREE.Mesh(new THREE.OctahedronGeometry(HERO3D.nodes.size, 0), nodeMat);
    orb.position.set(radius, 0, 0);
    orb.layers.enable(1);
    orb.userData.bloom = true;
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
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
    const mat = new THREE.LineBasicMaterial({
      color: hdr(2.2),
      transparent: true,
      opacity: 0,
      toneMapped: false,
      depthWrite: false
    });
    const line = new THREE.Line(geo, mat);
    line.frustumCulled = false;
    line.layers.enable(1);
    line.userData.bloom = true;
    scene.add(line);
    return line;
  });

  const shardCount = mobile || reduced ? 0 : 22;
  const shards = shardCount ? new THREE.InstancedMesh(
    new THREE.OctahedronGeometry(0.05, 0),
    new THREE.MeshBasicMaterial({ color: hdr(1.6), transparent: true, opacity: 0, toneMapped: false, depthWrite: false }),
    shardCount
  ) : null;
  const shardSeed = [];
  if (shards) {
    const dummy = new THREE.Object3D();
    for (let i = 0; i < shardCount; i += 1) {
      const dir = new THREE.Vector3(Math.cos(i * 2.4), Math.sin(i * 1.7) * 0.65, Math.sin(i * 2.4)).normalize();
      shardSeed.push(dir);
      dummy.position.copy(dir).multiplyScalar(0.2);
      dummy.scale.setScalar(0.2);
      dummy.updateMatrix();
      shards.setMatrixAt(i, dummy.matrix);
    }
    shards.instanceMatrix.needsUpdate = true;
    shards.frustumCulled = false;
    yaw.add(shards);
  }

  const hud = buildHud();
  const chrome = buildChrome(playIntro);
  if (playIntro) document.documentElement.classList.add("await-intro");
  else document.documentElement.classList.add("intro-go");

  const bloom = makeBloom(renderer);
  const dprLadder = mobile
    ? [Math.min(window.devicePixelRatio || 1, 1.5), 1, 0.75]
    : [Math.min(window.devicePixelRatio || 1, 2), 1.5, 1, 0.75];
  let tier = 0;
  let dprCap = dprLadder[0];
  let bloomOn = !reduced;
  const frameMs = [];
  let active = true;
  let raf = 0;
  let posed = false;
  const pose = {
    x: 0, y: 0, scale: 1, split: 0, body: playIntro ? 0 : 1, edge: playIntro ? 0 : 0.9,
    hidden: 0, orbit: 1, camZ: HERO3D.camera.z, spin: 0, rotZ: 0, light: 0, proof: 0, heroP: 0,
    side: 0, lift: 0, fog: 0
  };
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

  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const t0 = performance.now();
  loader.load(GLB, function (gltf) {
    const baked = bakeCrystal(gltf.scene);
    const parts = splitGeometry(baked);
    baked.dispose();
    addHalf(topGroup, parts.top);
    addHalf(botGroup, parts.bot);
    const entry = performance.getEntriesByType("resource").filter(function (row) {
      return row.name.indexOf("axvigil_core_web.glb") !== -1;
    }).pop();
    host.dataset.glbBytes = String(entry ? (entry.decodedBodySize || entry.transferSize || 0) : 0);
    host.dataset.glbMs = String(Math.round(performance.now() - t0));
    host.classList.add("is-live");
    meshReady = true;
    meshReadyAt = performance.now();
    chrome.loaded();
    resize();
    setActive(true);
  }, function (ev) {
    if (ev && ev.lengthComputable) chrome.progress(ev.loaded / ev.total);
  }, function () {
    chrome.loaded();
    document.documentElement.classList.add("intro-go");
    host.classList.remove("is-live");
  });

  function addHalf(group, geometry) {
    const mesh = new THREE.Mesh(geometry, bodyMat);
    mesh.layers.set(0);
    group.add(mesh);
    const edges = makeEdges(geometry);
    const solid = new THREE.LineSegments(edges, solidMat);
    solid.scale.setScalar(1.004);
    solid.layers.enable(1);
    solid.userData.bloom = true;
    group.add(solid);
    const glint = new THREE.LineSegments(edges, glintMat);
    glint.scale.setScalar(1.006);
    glint.computeLineDistances();
    glint.layers.enable(1);
    glint.userData.bloom = true;
    group.add(glint);
    const hidden = new THREE.LineSegments(edges, hiddenMat);
    hidden.scale.setScalar(1.004);
    hidden.layers.enable(1);
    hidden.userData.bloom = true;
    hidden.visible = false;
    hiddenLines.push(hidden);
    group.add(hidden);
  }

  function resize() {
    mobile = window.matchMedia("(max-width: 767px)").matches;
    if (tier === 0) {
      dprLadder[0] = mobile
        ? Math.min(window.devicePixelRatio || 1, 1.5)
        : Math.min(window.devicePixelRatio || 1, 2);
      dprCap = dprLadder[0];
    }
    const w = window.innerWidth;
    const h = Math.max(1, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    bloom.resize(Math.floor(w * renderer.getPixelRatio()), Math.floor(h * renderer.getPixelRatio()));
    sats.forEach(function (sat, i) { sat.ring.visible = !mobile || i === 0; });
    hud.root.hidden = mobile || reduced;
  }

  function sectionWeight(el) {
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const vh = window.innerHeight;
    const anchorY = r.top + Math.min(r.height, vh) * 0.4;
    const dist = Math.abs(anchorY - vh * 0.44);
    return Math.max(0, 1 - dist / (vh * 0.9));
  }

  function corner(isMobile) {
    return {
      x: window.innerWidth - (isMobile ? 78 : 110),
      y: isMobile ? 250 : 168
    };
  }

  function desired() {
    const how = document.getElementById("how");
    const proof = document.getElementById("proof");
    const road = document.getElementById("roadmap");
    const problem = document.getElementById("problem");
    const wh = sectionWeight(hero);
    const ww = how ? sectionWeight(how) : 0;
    const wp = proof ? sectionWeight(proof) : 0;
    const wr = road ? sectionWeight(road) : 0;
    const wLight = Math.max(problem ? sectionWeight(problem) : 0, wp);
    const sum = wh + ww + wp + wr || 1;
    const heroRect = host.getBoundingClientRect();
    const heroP = THREE.MathUtils.clamp(-hero.getBoundingClientRect().top / Math.max(hero.offsetHeight, 1), 0, 1);
    const heroH = heroRect.height < 8 ? window.innerHeight * 0.5 : heroRect.height;
    const heroW = heroRect.height < 8 ? window.innerWidth * 0.28 : heroRect.width;
    const heroLeft = heroRect.height < 8 ? window.innerWidth * 0.62 : heroRect.left;
    const heroTop = heroRect.height < 8 ? window.innerHeight * 0.22 : heroRect.top;
    const slots = {
      hero: {
        x: heroLeft + heroW * 0.5,
        y: heroTop + heroH * 0.46,
        px: mobile ? heroH * 0.86 : heroH * 0.9
      },
      how: corner(mobile),
      proof: corner(mobile),
      road: corner(mobile)
    };
    slots.how.px = mobile ? 150 : 168;
    slots.proof.px = mobile ? 130 : 156;
    slots.road.px = mobile ? 110 : 132;
    const lane = smootherstep(clamp01((storyS - 0.05) / 0.16));
    const park = corner(mobile);
    const sx = slots.hero.x * (1 - lane) + park.x * lane;
    const sy = slots.hero.y * (1 - lane) + park.y * lane;
    const px = slots.hero.px * (1 - lane) + (mobile ? 140 : 168) * lane;
    const flight = sampleFlight(storyS);
    const camZ = flight.camZ;
    const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * camZ;
    const halfW = halfH * camera.aspect;
    const ndcX = (sx / Math.max(1, window.innerWidth)) * 2 - 1;
    const ndcY = -((sy / Math.max(1, window.innerHeight)) * 2 - 1);
    const pxPerUnit = window.innerHeight / (2 * halfH);
    return {
      x: ndcX * halfW,
      y: ndcY * halfH,
      scale: THREE.MathUtils.clamp(px / (HERO3D.crystal.height * pxPerUnit), 0.18, 1.35),
      split: flight.split,
      body: flight.body,
      edge: flight.edge,
      hidden: flight.hidden,
      orbit: flight.orbit,
      camZ: camZ,
      spin: flight.spin + heroP * 0.35,
      rotZ: flight.side * 0.08,
      light: Math.max(flight.light, wLight * 0.35),
      proof: flight.proof,
      heroP: heroP,
      side: flight.side,
      lift: flight.lift,
      fog: flight.fog
    };
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
      pose.heroP = goal.heroP;
    }

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
    if (scene.environmentRotation) scene.environmentRotation.y = sweep + camYaw;
    strip.position.x = 2.8 + sweep * 1.6;
    strip.position.y = 1.6 + sweep * 0.25;
    scene.fog.color.copy(fogNear).lerp(fogFar, pose.fog);
    scene.fog.density = 0.008 + pose.fog * 0.028;

    camera.position.set(camPx, 0.08 + camPy, pose.camZ);
    camera.lookAt(camPx * 0.28, camPy * 0.22, 0);
    camera.rotation.z += roll + driftRot;
    const rule = document.getElementById("hero-rule");
    if (rule) rule.classList.toggle("is-apart", pose.heroP > 0.52);

    rig.position.set(pose.x, pose.y + bob, 0);
    rig.scale.setScalar(pose.scale * introScale);
    tilt.rotation.x = tiltS.x;
    tilt.rotation.y = tiltS.y;
    tilt.rotation.z = pose.rotZ;
    yaw.rotation.y = idle + pose.spin + drag.x + introRot;

    topGroup.position.y = pose.split * 0.35;
    botGroup.position.y = -pose.split * 0.35;
    const bodyOpacity = pose.body * (playIntro ? bodyEase : 1);
    bodyMat.opacity = bodyOpacity;
    const wantTransparent = bodyOpacity < 0.98;
    if (bodyMat.transparent !== wantTransparent) {
      bodyMat.transparent = wantTransparent;
      bodyMat.depthWrite = !wantTransparent;
      bodyMat.needsUpdate = true;
    }
    bodyMat.envMapIntensity = 1.15 - pose.light * 0.25;
    const edgeBoost = 1 + envIn * 0.2;
    solidMat.opacity = pose.edge * edgeEase * 0.72 * edgeBoost;
    glintMat.opacity = pose.edge * edgeEase * 0.95;
    glintMat.dashOffset = -((reduced ? 0 : now * 0.001) * HERO3D.edges.sweep);
    hiddenMat.opacity = pose.hidden * edgeEase;
    hiddenLines.forEach(function (line) { line.visible = hiddenMat.opacity > 0.04; });
    const lit = hdr(HERO3D.edges.hdrBoost);
    const ink = new THREE.Color(0.12, 0.13, 0.08);
    solidMat.color.copy(lit).lerp(ink, pose.light * 0.78);
    glintMat.color.copy(lit).lerp(ink, pose.light * 0.55);

    inner.visible = pose.split > 0.04;
    inner.material.opacity = Math.min(1, pose.split * 1.25);
    inner.scale.setScalar(0.35 + pose.split * 0.85);
    inner.rotation.y = idle * 0.6;

    disc.material.opacity = 0.08 + pose.light * 0.62;
    orbits.scale.setScalar(0.6 + 0.4 * nodeEase);
    nodeMat.opacity = nodeEase;
    ringMat.opacity = HERO3D.nodes.ringOpacity * nodeEase * (0.35 + pose.orbit * 0.65);

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
      sat.orb.scale.setScalar(sat.hover ? 1.45 : 1);
    });

    const pulse = signEnvelope(now * 0.001);
    const envTarget = reduced ? 0.42 : Math.max(pulse, pose.proof * 0.96);
    envIn = THREE.MathUtils.damp(envIn, envTarget, 4.5, dt);
    const pair = Math.floor(now / 1000 / HERO3D.nodes.signEveryS) % 3;
    const pairIdx = [[0, 1], [1, 2], [2, 0]][pair];
    signLines.forEach(function (line, i) {
      const sat = sats[pairIdx[i]];
      sat.orb.getWorldPosition(tmp);
      apexMark.getWorldPosition(tmp2);
      const attr = line.geometry.attributes.position;
      attr.setXYZ(0, tmp.x, tmp.y, tmp.z);
      attr.setXYZ(1, tmp2.x, tmp2.y, tmp2.z);
      attr.needsUpdate = true;
      line.material.opacity = envIn * nodeEase;
    });

    if (shards) {
      const dummy = new THREE.Object3D();
      const spread = 0.25 + buildP * 1.15;
      const shardFade = playIntro ? Math.max(0, 1 - clamp01((introT - 1.15) / 0.7)) : 0;
      shards.material.opacity = shardFade;
      shardSeed.forEach(function (dir, i) {
        dummy.position.copy(dir).multiplyScalar(spread * (0.65 + (i % 5) * 0.08));
        dummy.scale.setScalar(0.35 + buildP * 0.8);
        dummy.rotation.set(i, buildP * 2, i * 0.3);
        dummy.updateMatrix();
        shards.setMatrixAt(i, dummy.matrix);
      });
      shards.instanceMatrix.needsUpdate = true;
      shards.visible = shardFade > 0.02;
    }

    placePins(nodeEase, hoverIndex);
    placeGlow();

    const road = document.getElementById("roadmap");
    const pastStory = road && road.getBoundingClientRect().bottom < 48;
    stage.style.opacity = pastStory ? "0" : "1";
    if (pastStory) {
      setActive(false);
      return;
    }

    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.setRenderTarget(null);
    renderer.render(scene, camera);
    if (bloomOn) bloom.composite(scene, camera, bodyMat, disc);

    if (!reduced && tier < dprLadder.length - 1) {
      frameMs.push(dt * 1000);
      if (frameMs.length >= 40) {
        const sorted = frameMs.slice().sort(function (a, b) { return a - b; });
        const body = sorted.slice(1, sorted.length - 1);
        const avg = body.reduce(function (a, b) { return a + b; }, 0) / Math.max(1, body.length);
        frameMs.length = 0;
        if (avg > 22) {
          tier += 1;
          dprCap = dprLadder[Math.min(tier, dprLadder.length - 1)];
          if (tier >= dprLadder.length - 1) bloomOn = false;
          resize();
        }
      }
    }
  }

  function snapHero() {
    const heroRect = host.getBoundingClientRect();
    const camZ = HERO3D.camera.z;
    const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * camZ;
    const halfW = halfH * camera.aspect;
    const sx = heroRect.left + heroRect.width * 0.5;
    const sy = heroRect.top + heroRect.height * 0.46;
    const ndcX = (sx / Math.max(1, window.innerWidth)) * 2 - 1;
    const ndcY = -((sy / Math.max(1, window.innerHeight)) * 2 - 1);
    const pxPerUnit = window.innerHeight / (2 * halfH);
    return {
      x: ndcX * halfW,
      y: ndcY * halfH,
      scale: THREE.MathUtils.clamp((heroRect.height * 0.9) / (HERO3D.crystal.height * pxPerUnit), 0.18, 1.35),
      split: 0,
      body: 1,
      edge: 0.9,
      hidden: 0.04,
      orbit: 1,
      camZ: camZ,
      spin: 0.2,
      rotZ: 0,
      light: 0,
      proof: 0,
      heroP: 0,
      side: 0,
      lift: 0,
      fog: 0
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
    const show = nodeEase > 0.72 ? Math.min(1, (nodeEase - 0.72) / 0.28) : 0;
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
    const x = (tmp.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-tmp.y * 0.5 + 0.5) * window.innerHeight;
    pin.dataset.ax = x.toFixed(1);
    pin.dataset.ay = y.toFixed(1);
    pin.style.transform = "translate(" + (x + ox).toFixed(1) + "px," + (y + oy).toFixed(1) + "px)";
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
    rig.getWorldPosition(centerNdc);
    centerNdc.project(camera);
    const cx = (centerNdc.x * 0.5 + 0.5) * window.innerWidth;
    const cy = (-centerNdc.y * 0.5 + 0.5) * window.innerHeight;
    const reach = mobile ? 90 : 160 * pose.scale + 70;
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
    const zone = !reduced && fine && !mobile && nearCrystal(event.clientX, event.clientY);
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
    const roadEl = document.getElementById("roadmap");
    if (roadEl && roadEl.getBoundingClientRect().bottom < 48) return false;
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
    bloom.dispose();
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
  const loader = document.createElement("div");
  loader.id = "ax-loader";
  loader.hidden = !playIntro;
  loader.innerHTML = "<div class=\"ax-mark\" aria-hidden=\"true\"><i class=\"ring ring-a\"></i><i class=\"ring ring-b\"></i><span class=\"orbit o1\"><i></i></span><span class=\"orbit o2\"><i></i></span><span class=\"orbit o3\"><i></i></span></div><p class=\"pct\">[ 000% SYNCING ]</p><div class=\"bar\"><i></i></div>";
  const status = document.createElement("p");
  status.id = "ax-status";
  status.className = "ax-status";
  status.textContent = "[ SEEDING SANDBOX ]";
  status.hidden = !playIntro;
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "ax-skip";
  skip.textContent = "[ SKIP ]";
  skip.hidden = !playIntro;
  skip.tabIndex = playIntro ? 0 : -1;
  document.body.appendChild(loader);
  document.body.appendChild(status);
  document.body.appendChild(skip);
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
  function loaded() {
    if (settled) return;
    settled = true;
    window.clearTimeout(failSafe);
    write(100, "online");
    window.setTimeout(function () { write(100, "scroll"); }, 900);
    window.setTimeout(function () {
      loader.classList.add("is-out");
      status.classList.add("is-out");
    }, 1600);
    window.setTimeout(function () {
      loader.hidden = true;
      status.hidden = true;
    }, 2100);
  }
  return {
    onSkip: function (fn) { skipFn = fn; },
    progress: function (ratio) { write(ratio * 100); },
    loaded: loaded,
    hideLoader: function () {
      settled = true;
      window.clearTimeout(failSafe);
      loader.hidden = true;
      status.hidden = true;
    },
    hideSkip: function () {
      skip.hidden = true;
      skip.tabIndex = -1;
    }
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

function lineMat(boost, opacity) {
  return new THREE.LineBasicMaterial({
    color: hdr(boost),
    transparent: true,
    opacity: opacity,
    toneMapped: false,
    depthWrite: false
  });
}

function sampleFlight(p) {
  const stops = [
    { at: 0, split: 0, body: 1, hidden: 0.02, orbit: 1, edge: 0.9, camZ: 7.6, side: 0.02, lift: 0.02, spin: 0.1, fog: 0, proof: 0, light: 0 },
    { at: 0.18, split: 0.12, body: 1, hidden: 0.08, orbit: 0.5, edge: 0.95, camZ: 6.35, side: -0.16, lift: 0.1, spin: 0.85, fog: 0.72, proof: 0, light: 0.45 },
    { at: 0.4, split: 1, body: 1, hidden: 0.1, orbit: 0.62, edge: 1, camZ: 5.85, side: 0.1, lift: 0.02, spin: 1.55, fog: 0.38, proof: 0.15, light: 0.15 },
    { at: 0.62, split: 0.02, body: 0.18, hidden: 0.34, orbit: 0.95, edge: 1, camZ: 6.55, side: -0.1, lift: 0.06, spin: 2.15, fog: 0.12, proof: 1, light: 0.8 },
    { at: 0.8, split: 0, body: 1, hidden: 0.03, orbit: 0.32, edge: 0.86, camZ: 8.6, side: 0.12, lift: 0.1, spin: 2.55, fog: 0.4, proof: 0.1, light: 0.08 },
    { at: 1, split: 0, body: 1, hidden: 0, orbit: 0.16, edge: 0.7, camZ: 10.4, side: 0.06, lift: 0.14, spin: 2.9, fog: 0.18, proof: 0, light: 0 }
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

function bakeCrystal(root) {
  const geos = [];
  root.updateWorldMatrix(true, true);
  root.traverse(function (obj) {
    if (!obj.isMesh || !obj.geometry) return;
    const geo = obj.geometry.clone();
    geo.applyMatrix4(obj.matrixWorld);
    geos.push(geo);
  });
  const geo = geos[0] || new THREE.BufferGeometry();
  for (let i = 1; i < geos.length; i += 1) {
    geos[i].dispose();
  }
  geo.computeBoundingBox();
  const box = geo.boundingBox;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  geo.translate(-center.x, -center.y, -center.z);
  const s = HERO3D.crystal.height / (size.y || 1);
  geo.scale(s, s, s);
  geo.computeVertexNormals();
  return geo;
}

function splitGeometry(geometry) {
  const pos = geometry.getAttribute("position");
  const index = geometry.getIndex();
  const top = [];
  const bot = [];
  const count = index ? index.count : pos.count;
  function read(i) {
    return [pos.getX(i), pos.getY(i), pos.getZ(i)];
  }
  function push(buf, a, b, c) {
    buf.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]);
  }
  function cut(p, q) {
    const t = p[1] / (p[1] - q[1]);
    return [p[0] + (q[0] - p[0]) * t, 0, p[2] + (q[2] - p[2]) * t];
  }
  for (let i = 0; i < count; i += 3) {
    const a = read(index ? index.getX(i) : i);
    const b = read(index ? index.getX(i + 1) : i + 1);
    const c = read(index ? index.getX(i + 2) : i + 2);
    const above = [];
    const below = [];
    [a, b, c].forEach(function (p) { (p[1] >= 0 ? above : below).push(p); });
    if (above.length === 3) { push(top, a, b, c); continue; }
    if (below.length === 3) { push(bot, a, b, c); continue; }
    if (above.length === 1) {
      const p = above[0];
      const q = below[0];
      const r = below[1];
      const pq = cut(p, q);
      const pr = cut(p, r);
      push(top, p, pq, pr);
      push(bot, pq, q, r);
      push(bot, pq, r, pr);
    } else {
      const p = below[0];
      const q = above[0];
      const r = above[1];
      const pq = cut(p, q);
      const pr = cut(p, r);
      push(bot, p, pq, pr);
      push(top, pq, q, r);
      push(top, pq, r, pr);
    }
  }
  return { top: geoFrom(top), bot: geoFrom(bot) };
}

function geoFrom(arr) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
  geo.computeVertexNormals();
  geo.computeBoundingSphere();
  return geo;
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

function makeBloom(renderer) {
  const rtOpts = { type: THREE.HalfFloatType, depthBuffer: true, stencilBuffer: false };
  const src = new THREE.WebGLRenderTarget(2, 2, rtOpts);
  const ping = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, depthBuffer: false });
  const pong = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, depthBuffer: false });
  [src, ping, pong].forEach(function (rt) {
    rt.texture.colorSpace = THREE.LinearSRGBColorSpace;
  });
  const blurMat = new THREE.ShaderMaterial({
    uniforms: {
      tDiffuse: { value: null },
      direction: { value: new THREE.Vector2(1, 0) },
      resolution: { value: new THREE.Vector2(1, 1) },
      threshold: { value: 0 }
    },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader: [
      "uniform sampler2D tDiffuse;",
      "uniform vec2 direction;",
      "uniform vec2 resolution;",
      "uniform float threshold;",
      "varying vec2 vUv;",
      "void main(){",
      "  if (threshold > 0.0) {",
      "    vec4 s = texture2D(tDiffuse, vUv);",
      "    float lum = max(s.r, max(s.g, s.b));",
      "    gl_FragColor = lum >= threshold ? s : vec4(0.0);",
      "    return;",
      "  }",
      "  vec2 px = direction / resolution;",
      "  vec4 c = texture2D(tDiffuse, vUv) * 0.227;",
      "  c += texture2D(tDiffuse, vUv + px * 1.35) * 0.194;",
      "  c += texture2D(tDiffuse, vUv - px * 1.35) * 0.194;",
      "  c += texture2D(tDiffuse, vUv + px * 3.2) * 0.122;",
      "  c += texture2D(tDiffuse, vUv - px * 3.2) * 0.122;",
      "  c += texture2D(tDiffuse, vUv + px * 5.4) * 0.071;",
      "  c += texture2D(tDiffuse, vUv - px * 5.4) * 0.071;",
      "  gl_FragColor = c;",
      "}"
    ].join("\n"),
    depthTest: false,
    depthWrite: false
  });
  const compMat = new THREE.ShaderMaterial({
    uniforms: {
      tBloom: { value: null },
      strength: { value: HERO3D.bloom.strength }
    },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader: [
      "uniform sampler2D tBloom;",
      "uniform float strength;",
      "varying vec2 vUv;",
      "void main(){ gl_FragColor = vec4(texture2D(tBloom, vUv).rgb * strength, 0.0); }"
    ].join("\n"),
    transparent: true,
    depthTest: false,
    depthWrite: false,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneFactor,
    blendSrcAlpha: THREE.ZeroFactor,
    blendDstAlpha: THREE.OneFactor
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), blurMat);
  const compQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), compMat);
  const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const pass = new THREE.Scene();
  pass.add(quad);
  const compScene = new THREE.Scene();
  compScene.add(compQuad);
  const saved = [];

  function blit(materialTarget, input, output) {
    blurMat.uniforms.tDiffuse.value = input.texture;
    renderer.setRenderTarget(output);
    renderer.render(pass, ortho);
  }

  return {
    resize: function (w, h) {
      const hw = Math.max(1, Math.floor(w / 2));
      const hh = Math.max(1, Math.floor(h / 2));
      src.setSize(hw, hh);
      ping.setSize(hw, hh);
      pong.setSize(hw, hh);
      blurMat.uniforms.resolution.value.set(hw, hh);
    },
    composite: function (scene, camera, bodyMat, disc) {
      const prevTarget = renderer.getRenderTarget();
      const prevTone = renderer.toneMapping;
      const prevAlpha = renderer.getClearAlpha();
      const prevAuto = renderer.autoClear;
      const discWas = disc.visible;
      try {
        renderer.toneMapping = THREE.NoToneMapping;
        renderer.setRenderTarget(src);
        renderer.setClearColor(0x000000, 0);
        renderer.clear(true, true, true);
        disc.visible = false;
        bodyMat.colorWrite = false;
        scene.traverse(function (obj) {
          if (obj.userData && obj.userData.bloom) {
            saved.push(obj, obj.visible);
            obj.visible = false;
          }
        });
        renderer.render(scene, camera);
        for (let i = 0; i < saved.length; i += 2) saved[i].visible = saved[i + 1];
        saved.length = 0;
        bodyMat.colorWrite = true;
        camera.layers.disable(0);
        renderer.render(scene, camera);
        blurMat.uniforms.threshold.value = HERO3D.bloom.threshold;
        blit(blurMat, src, ping);
        blurMat.uniforms.threshold.value = 0;
        blurMat.uniforms.direction.value.set(1, 0);
        blit(blurMat, ping, pong);
        blurMat.uniforms.direction.value.set(0, 1);
        blit(blurMat, pong, ping);
        renderer.autoClear = false;
        renderer.setRenderTarget(null);
        renderer.render(compScene, ortho);
      } finally {
        camera.layers.enable(0);
        disc.visible = discWas;
        bodyMat.colorWrite = true;
        for (let i = 0; i < saved.length; i += 2) saved[i].visible = saved[i + 1];
        saved.length = 0;
        renderer.toneMapping = prevTone;
        renderer.autoClear = prevAuto;
        renderer.setClearAlpha(prevAlpha);
        renderer.setRenderTarget(prevTarget);
      }
    },
    dispose: function () {
      src.dispose();
      ping.dispose();
      pong.dispose();
      blurMat.dispose();
      compMat.dispose();
    }
  };
}

function discTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 8, 64, 64, 64);
  g.addColorStop(0, "rgba(0,0,0,0.72)");
  g.addColorStop(0.55, "rgba(0,0,0,0.28)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

