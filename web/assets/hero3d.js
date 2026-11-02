/* Lazy hero core. three@0.170.0. No flicker: one slow spin, one glow, scroll brings the nodes in. */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const ACCENT = 0xeef94b;
const GLB = "assets/3d/axvigil_core_web.glb";
let started = false;

export function mount() {
  if (started) return;
  started = true;
  const host = document.getElementById("hero-core");
  const hero = document.querySelector(".hero");
  const how = document.getElementById("how");
  if (!host || !hero || !how) return;
  if (!webgl()) return;

  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  host.appendChild(canvas);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
    preserveDrawingBuffer: true
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);
  camera.position.set(0.15, 0.1, 6.4);

  scene.add(new THREE.AmbientLight(0xf4f1e4, 0.55));
  const key = new THREE.DirectionalLight(0xfff6d8, 1.35);
  key.position.set(3.2, 4.2, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xeef94b, 0.35);
  rim.position.set(-3, -1.5, -2);
  scene.add(rim);

  const rig = new THREE.Group();
  scene.add(rig);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(),
    color: ACCENT,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    opacity: 0.42
  }));
  glow.scale.set(3.6, 3.6, 1);
  glow.position.z = -0.35;
  rig.add(glow);

  const nodes = new THREE.Group();
  const satellites = [];
  for (let i = 0; i < 3; i += 1) {
    const tilt = (i - 1) * 0.42;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.35, 0.006, 6, 72),
      new THREE.MeshBasicMaterial({ color: ACCENT, transparent: true, opacity: 0 })
    );
    ring.rotation.x = Math.PI / 2.15 + tilt;
    nodes.add(ring);
    const orb = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.075, 0),
      new THREE.MeshStandardMaterial({
        color: 0x14160c,
        emissive: ACCENT,
        emissiveIntensity: 0.7,
        roughness: 0.35,
        metalness: 0.55
      })
    );
    nodes.add(orb);
    satellites.push({ orb, ring, base: (i / 3) * Math.PI * 2, radius: 1.35, tilt });
  }
  nodes.scale.setScalar(0.001);
  rig.add(nodes);

  let core = null;
  let active = false;
  let raf = 0;
  let spin = 0;
  const look = { x: 0, y: 0, tx: 0, ty: 0 };
  const born = performance.now();

  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const t0 = performance.now();
  loader.load(GLB, (gltf) => {
    core = gltf.scene;
    core.traverse((obj) => {
      if (!obj.isMesh) return;
      const list = Array.isArray(obj.material) ? obj.material : [obj.material];
      list.forEach((mat) => {
        if (!mat || !mat.emissive) return;
        mat.emissive.set(ACCENT);
        mat.emissiveIntensity = 1.15;
        mat.needsUpdate = true;
      });
    });
    const box = new THREE.Box3().setFromObject(core);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    core.position.sub(center);
    const span = Math.max(size.x, size.y, size.z) || 1;
    core.scale.setScalar(1.72 / span);
    rig.add(core);
    glow.position.z = -0.2;
    const entry = performance.getEntriesByType("resource").filter((row) => row.name.indexOf("axvigil_core_web.glb") !== -1).pop();
    const bytes = entry ? (entry.decodedBodySize || entry.transferSize || 0) : 0;
    const ms = Math.round(performance.now() - t0);
    host.dataset.glbBytes = String(bytes);
    host.dataset.glbMs = String(ms);
    host.classList.add("is-live");
    resize();
    setActive(true);
  }, undefined, () => {
    host.classList.remove("is-live");
  });

  function scrollProgress() {
    const start = hero.offsetTop;
    const end = start + hero.offsetHeight * 0.7;
    return Math.min(1, Math.max(0, (window.scrollY - start) / Math.max(1, end - start)));
  }

  function resize() {
    const w = host.clientWidth;
    const h = host.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function frame(now) {
    if (!active) return;
    raf = requestAnimationFrame(frame);
    const t = (now - born) / 1000;
    const p = scrollProgress();
    look.x += (look.tx - look.x) * 0.06;
    look.y += (look.ty - look.y) * 0.06;
    spin += 0.0032;
    rig.position.y = Math.sin(t * 0.55) * 0.07;
    rig.rotation.x = look.y * 0.28;
    rig.rotation.z = look.x * -0.06;
    if (core) core.rotation.y = spin + p * Math.PI * 1.35 + look.x * 0.35;
    const shown = p * p * (3 - 2 * p);
    nodes.scale.setScalar(Math.max(0.001, shown));
    satellites.forEach((sat) => {
      const a = sat.base + t * 0.35 + p * Math.PI;
      sat.orb.position.set(Math.cos(a) * sat.radius, Math.sin(a) * 0.22 + sat.tilt * 0.15, Math.sin(a) * sat.radius * 0.72);
      sat.ring.material.opacity = shown * 0.55;
    });
    glow.material.opacity = 0.28 + shown * 0.12;
    renderer.render(scene, camera);
  }

  function setActive(on) {
    if (on === active) return;
    active = on;
    if (on) raf = requestAnimationFrame(frame);
    else cancelAnimationFrame(raf);
  }

  const seen = new IntersectionObserver((entries) => {
    setActive(entries[0].isIntersecting && !document.hidden);
  }, { threshold: 0 });
  seen.observe(hero);
  document.addEventListener("visibilitychange", () => {
    const box = hero.getBoundingClientRect();
    const on = !document.hidden && box.bottom > 0 && box.top < window.innerHeight;
    setActive(on);
  });
  hero.addEventListener("pointermove", (event) => {
    const rect = hero.getBoundingClientRect();
    look.tx = (event.clientX - rect.left) / rect.width - 0.5;
    look.ty = (event.clientY - rect.top) / rect.height - 0.5;
  });
  hero.addEventListener("pointerleave", () => {
    look.tx = 0;
    look.ty = 0;
  });
  window.addEventListener("resize", resize);
  resize();
}

function webgl() {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch (err) {
    return false;
  }
}

function glowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 8, 64, 64, 64);
  g.addColorStop(0, "rgba(238,249,75,0.55)");
  g.addColorStop(0.45, "rgba(238,249,75,0.12)");
  g.addColorStop(1, "rgba(238,249,75,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
