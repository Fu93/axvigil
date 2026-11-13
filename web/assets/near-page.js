import { formatRemain, phase, plainGrade, shortHash, timeline } from "./near-state.mjs";

const RPC = "https://rpc.testnet.near.org";
const EXPLORER = "https://testnet.nearblocks.io";
const FINE = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const REDUCE = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const state = {
  deployment: null,
  chainNs: 0n,
  fetchedAt: 0,
  records: [],
  reputation: null,
  signature: "",
  txTimes: {},
  preview: new URLSearchParams(location.search).get("preview"),
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

async function rpc(payload, timeout = 8000) {
  if (state.preview === "down") throw new Error("The testnet RPC did not answer.");
  const targets = [RPC];
  const host = location.hostname;
  if (host === "localhost" || host === "127.0.0.1") targets.push(location.origin + "/near-rpc");
  let last;
  for (const url of targets) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(timeout),
      });
      if (!response.ok) throw new Error("RPC " + response.status);
      const text = await response.text();
      const body = JSON.parse(text.replace(/:(\s*)(\d{16,})/g, ":$1\"$2\""));
      if (body.error) throw new Error(body.error.message || "RPC error");
      return body.result;
    } catch (err) {
      last = err;
    }
  }
  throw last || new Error("The testnet RPC did not answer.");
}

function decodeCall(result) {
  if (!result || !Array.isArray(result.result)) {
    throw new Error("empty RPC result");
  }
  const bytes = Uint8Array.from(result.result);
  const text = new TextDecoder().decode(bytes);
  return text ? JSON.parse(text) : null;
}

async function view(contract, method, args) {
  const result = await rpc({
    jsonrpc: "2.0",
    id: "axvigil",
    method: "query",
    params: {
      request_type: "call_function",
      finality: "final",
      account_id: contract,
      method_name: method,
      args_base64: btoa(JSON.stringify(args)),
    },
  });
  return decodeCall(result);
}

async function chainNow() {
  if (state.preview === "window" || state.preview === "empty" || state.preview === "down") {
    state.chainNs = BigInt(Date.now()) * 1000000n;
    state.fetchedAt = performance.now();
    return;
  }
  const result = await rpc({ jsonrpc: "2.0", id: "axvigil", method: "block", params: { finality: "final" } });
  state.chainNs = BigInt(result.header.timestamp);
  state.fetchedAt = performance.now();
}

function nowNs() {
  if (state.chainNs === 0n) return 0n;
  const elapsedMs = BigInt(Math.max(0, Math.round(performance.now() - state.fetchedAt)));
  return state.chainNs + elapsedMs * 1000000n;
}

function stepTx(hash) {
  const deployment = state.deployment;
  const txs = deployment.transactions || {};
  const agent = deployment.agent;
  const challenger = deployment.challenger;
  const contract = deployment.contract;
  if (hash === deployment.honest_evidence_hash) {
    return {
      anchor: { id: txs.anchor_honest, sender: agent },
      decide: { id: txs.finalize_honest, sender: challenger },
    };
  }
  if (hash === deployment.bad_evidence_hash) {
    return {
      anchor: { id: txs.anchor_bad, sender: agent },
      decide: { id: txs.challenge_bad, sender: challenger },
      revoked: { id: txs.resolve_bad, sender: contract },
    };
  }
  return {};
}

function formatChainTime(ns) {
  if (ns == null || ns === "" || ns === "0") return "";
  const ms = Number(BigInt(ns) / 1000000n);
  if (!Number.isFinite(ms)) return "";
  return new Date(ms).toISOString().replace(".000", "").replace("T", " ").replace("Z", " UTC");
}

function labelFor(kind) {
  if (kind === "window") return "Window";
  if (kind === "pending") return "Awaiting finalize";
  if (kind === "challenged") return "Challenged";
  if (kind === "final") return "Final";
  if (kind === "revoked") return "Revoked";
  return "Unknown";
}

function displayTime(text) {
  return String(text || "").replace(/(\d{4}-\d{2}-\d{2}) /, "$1\n");
}

function bakedTime(id) {
  const table = (state.deployment && state.deployment.tx_times) || {};
  return (state.txTimes && state.txTimes[id]) || table[id] || "";
}

function stepDetail(record, item) {
  const links = stepTx(record.evidence_hash);
  if (item.id === "verify") return { time: "Off-chain grader", secondary: "", tx: null };
  if (item.id === "window") {
    const opened = links.anchor ? bakedTime(links.anchor.id) : "";
    const closed = formatChainTime(record.ready_at_ns);
    return {
      time: opened || "Opened with the anchor",
      secondary: closed ? "Closes " + closed : "",
      tx: null,
    };
  }
  const tx = links[item.id] || null;
  if (!tx) return { time: "Not taken", secondary: "", tx: null };
  return { time: bakedTime(tx.id), secondary: "", tx };
}

function renderTimeline(record) {
  return timeline(record, nowNs()).map((item) => {
    const detail = stepDetail(record, item);
    const fail = item.id === "revoked" && item.state === "done";
    const klass = fail ? "is-fail" : "is-" + item.state;
    const tx = detail.tx
      ? `<a class="tl-tx" href="${EXPLORER}/txns/${encodeURIComponent(detail.tx.id)}" target="_blank" rel="noopener">tx <span aria-hidden="true">↗</span></a>`
      : "";
    return `<li class="tl-step ${klass}">
      <span class="tl-mark" aria-hidden="true"></span>
      <span class="tl-label">${escapeHtml(item.label)}</span>
      <span class="tl-time"${detail.tx ? ` data-tx="${escapeHtml(detail.tx.id)}"` : ""}>${escapeHtml(displayTime(detail.time))}</span>
      ${detail.secondary ? `<span class="tl-time secondary">${escapeHtml(displayTime(detail.secondary))}</span>` : ""}
      ${tx}
    </li>`;
  }).join("");
}

function clockHtml(record, kind) {
  if (kind === "window") {
    const remain = formatRemain(Number(BigInt(record.ready_at_ns) - nowNs()) / 1e6);
    return `<p class="clock" data-clock="${escapeHtml(record.ready_at_ns)}" aria-live="polite">[: ${remain} ]</p>`;
  }
  if (kind === "pending") return `<p class="clock quiet">[: window closed ]</p>`;
  return "";
}

function renderRecord(record) {
  const kind = phase(record, nowNs());
  const cardClass = kind === "revoked" ? " is-revoked" : "";
  return `<article class="near-card${cardClass}" data-hash="${escapeHtml(record.evidence_hash)}">
    <header class="card-top">
      <p class="bracket">[:${escapeHtml(labelFor(kind).toUpperCase())}]</p>
      <p class="who">${escapeHtml(record.agent)}</p>
    </header>
    ${clockHtml(record, kind)}
    <p class="hash-row">
      <code title="${escapeHtml(record.evidence_hash)}">${escapeHtml(shortHash(record.evidence_hash))}</code>
      <button type="button" class="copy" data-copy="${escapeHtml(record.evidence_hash)}">[ copy hash ]</button>
    </p>
    <p class="meta">${escapeHtml(plainGrade(record.vuln_class, record.difficulty))}</p>
    <ol class="timeline" aria-label="Verify, anchor, window, final or challenged, revoked">${renderTimeline(record)}</ol>
  </article>`;
}

function dataSignature() {
  const rep = state.reputation || {};
  return JSON.stringify({
    f: rep.finalized, r: rep.revoked, p: rep.pending, v: rep.is_valid,
    rec: state.records.map((record) => [record.evidence_hash, record.status, record.ready_at_ns]),
  });
}

function render() {
  const next = dataSignature();
  const rep = state.reputation;
  $("rep-final").textContent = String(rep.finalized);
  $("rep-revoked").textContent = String(rep.revoked);
  $("rep-pending").textContent = String(rep.pending);
  $("rep-valid").textContent = rep.is_valid ? "true" : "false";
  $("rep-valid").dataset.on = rep.is_valid ? "yes" : "no";
  $("record-count").textContent = String(state.records.length).padStart(3, "0");
  $("empty-records").hidden = state.records.length > 0;
  const cards = [...document.querySelectorAll("#record-list .near-card")];
  const sameCards = cards.length === state.records.length && cards.every((card, index) => {
    const record = state.records[index];
    const kind = labelFor(phase(record, nowNs())).toUpperCase();
    return card.dataset.hash === record.evidence_hash && card.querySelector(".bracket").textContent.includes(kind);
  });
  if (next !== state.signature && !sameCards) {
    const empty = $("empty-records");
    $("record-list").innerHTML = state.records.map(renderRecord).join("");
    $("record-list").appendChild(empty);
    state.signature = next;
    drawTimelines();
  }
  const open = state.records.find((record) => phase(record, nowNs()) === "window");
  const challenge = $("challenge-copy");
  if (open) {
    const args = JSON.stringify({
      evidence_hash: open.evidence_hash,
      challenge_hash: "64_HEX_COUNTER_EVIDENCE",
    });
    challenge.textContent = [
      "near contract call-function as-transaction " + state.deployment.contract + " challenge",
      "json-args '" + args + "'",
      "prepaid-gas '100 Tgas' attached-deposit '0 NEAR'",
      "sign-as YOUR_ACCOUNT.testnet network-config testnet sign-with-keychain send",
    ].join(" \\\n  ");
    $("challenge-note").textContent = "This record is still inside the window. Replace the challenge hash, then send from an account that is not the agent.";
  } else if (state.records.length === 0) {
    challenge.textContent = "No seals to challenge.";
    $("challenge-note").textContent = "This agent has no records. A pending seal would print the challenge command here.";
  } else {
    challenge.textContent = "No record is inside a challenge window.";
    $("challenge-note").textContent = "The published records are already Final and Revoked. A new pending anchor prints the challenge command here. The page does not open a wallet.";
  }
}

function tick() {
  document.querySelectorAll("[data-clock]").forEach((node) => {
    const ready = BigInt(node.getAttribute("data-clock"));
    const left = ready - nowNs();
    const text = "[: " + formatRemain(Number(left) / 1e6) + " ]";
    if (node.textContent !== text) node.textContent = text;
    if (left <= 0n) {
      node.removeAttribute("data-clock");
      load().catch(showError);
    }
  });
}

function applyPreview(reputation, records) {
  if (state.preview === "empty") {
    return [{
      account: state.deployment.agent,
      registered: true, banned: false, pending: 0, finalized: 0, revoked: 0,
      is_valid: false, records: [],
    }, []];
  }
  if (state.preview === "window") {
    const ready = (nowNs() + 95000000000n).toString();
    const record = {
      agent: state.deployment.agent,
      evidence_hash: "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00",
      bundle_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      vuln_class: 0,
      difficulty: 0,
      status: "Pending",
      ready_at_ns: ready,
      respond_by_ns: "0",
      passed_claim: true,
    };
    return [{
      account: state.deployment.agent,
      registered: true, banned: false, pending: 1, finalized: 0, revoked: 0,
      is_valid: false, records: [record.evidence_hash],
    }, [record]];
  }
  return [reputation, records];
}

async function load() {
  const deployment = state.deployment;
  let reputation = { finalized: 0, revoked: 0, pending: 0, is_valid: false, records: [] };
  let records = [];
  if (state.preview !== "empty" && state.preview !== "window") {
    const [, fetched] = await Promise.all([
      chainNow(),
      view(deployment.contract, "get_reputation", { account: deployment.agent }),
    ]);
    reputation = fetched;
    const hashes = reputation.records || [];
    records = (await Promise.all(hashes.map((hash) => (
      view(deployment.contract, "get_record", { evidence_hash: hash })
    )))).filter(Boolean);
  } else {
    await chainNow();
  }
  [reputation, records] = applyPreview(reputation, records);
  state.reputation = reputation;
  state.records = records;
  $("error").hidden = true;
  $("status").textContent = state.preview ? "[: preview ]" : "[: live ]";
  $("status").dataset.on = "yes";
  render();
}

function showError(err) {
  if (state.reputation && state.records.length) return;
  $("status").textContent = "[: rpc down ]";
  $("status").dataset.on = "no";
  $("error").hidden = false;
  $("error").textContent = (err && err.message ? err.message : "The testnet RPC did not answer.")
    + " Showing the last page shell. Retry when the network answers.";
  if (!state.reputation) {
    state.reputation = { finalized: 0, revoked: 0, pending: 0, is_valid: false, records: [] };
    state.records = [];
    $("empty-records").textContent = "No seals could be read. The contract is still listed above.";
    render();
  }
}

function bindNav() {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      nav.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

async function copyText(button, text) {
  const previous = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "[ copied ]";
  } catch (err) {
    button.textContent = "[ select ]";
  }
  window.setTimeout(() => { button.textContent = previous; }, 1200);
}

function bindCopy() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-copy]");
    if (button) copyText(button, button.getAttribute("data-copy"));
  });
  $("copy-command").addEventListener("click", () => {
    copyText($("copy-command"), $("challenge-copy").textContent);
  });
}

function drawTimelines() {
  document.querySelectorAll(".timeline").forEach((node) => {
    if (node.dataset.watched) return;
    node.dataset.watched = "1";
    if (REDUCE || !("IntersectionObserver" in window)) {
      node.classList.add("is-drawn");
      return;
    }
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-drawn");
        obs.disconnect();
      });
    }, { threshold: 0.3 });
    obs.observe(node);
  });
}

const TIME_CACHE = "axvigil-near-tx-times";

function readTimeCache() {
  try {
    const raw = sessionStorage.getItem(TIME_CACHE);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (err) {
    return {};
  }
}

function writeTimeCache() {
  try {
    sessionStorage.setItem(TIME_CACHE, JSON.stringify(state.txTimes));
  } catch (err) {
    /* private mode can refuse storage; the baked map still paints the cards */
  }
}

async function rpcBackoff(payload) {
  let wait = 700;
  let last;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      return await rpc(payload, 12000);
    } catch (err) {
      last = err;
      await new Promise((resolve) => setTimeout(resolve, wait));
      wait = Math.min(wait * 2, 8000);
    }
  }
  throw last || new Error("RPC");
}

async function fillTimes() {
  const jobs = [];
  for (const record of state.records) {
    for (const step of Object.values(stepTx(record.evidence_hash))) {
      if (step && step.id && !state.txTimes[step.id]) jobs.push(step);
    }
  }
  for (const step of jobs) {
    try {
      const status = await rpcBackoff({
        jsonrpc: "2.0",
        id: "axvigil",
        method: "EXPERIMENTAL_tx_status",
        params: { tx_hash: step.id, sender_account_id: step.sender },
      });
      const blockId = status.transaction_outcome && status.transaction_outcome.block_hash;
      if (!blockId) continue;
      const block = await rpcBackoff({
        jsonrpc: "2.0",
        id: "axvigil",
        method: "block",
        params: { block_id: blockId },
      });
      const time = formatChainTime(block.header.timestamp);
      if (!time) continue;
      state.txTimes[step.id] = time;
      writeTimeCache();
      document.querySelectorAll(`[data-tx="${CSS.escape(step.id)}"]`).forEach((node) => {
        if (!node.textContent.trim()) node.textContent = time;
      });
    } catch (err) {
      /* keep the baked or cached time; never write a loading label */
    }
  }
}

function bindCursor() {
  const cursor = $("near-cursor");
  if (!FINE || REDUCE || !cursor) return;
  document.documentElement.classList.add("fine");
  window.addEventListener("pointermove", (event) => {
    cursor.style.left = event.clientX + "px";
    cursor.style.top = event.clientY + "px";
  }, { passive: true });
}

function bindReveals() {
  const nodes = document.querySelectorAll(".reveal");
  if (REDUCE || !("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("in"));
    return;
  }
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.2 });
  nodes.forEach((node, index) => {
    node.style.transitionDelay = Math.min(index, 5) * 70 + "ms";
    obs.observe(node);
  });
}

function bindMagnets() {
  if (!FINE || REDUCE) return;
  document.querySelectorAll("a.btn, .nav-links a, button.btn").forEach((el) => {
    el.addEventListener("pointermove", (event) => {
      const rect = el.getBoundingClientRect();
      const x = Math.max(-6, Math.min(6, event.clientX - (rect.left + rect.width / 2)));
      const y = Math.max(-4, Math.min(4, event.clientY - (rect.top + rect.height / 2)));
      el.style.transform = "translate(" + (x * 0.25).toFixed(2) + "px," + (y * 0.35).toFixed(2) + "px)";
    });
    el.addEventListener("pointerleave", () => { el.style.transform = ""; });
  });
}

async function loadDeployment() {
  for (const url of ["near-deployment.json", "../docs/near/deployment.json"]) {
    const response = await fetch(url);
    if (response.ok) return response.json();
  }
  throw new Error("deployment.json missing");
}

async function main() {
  bindNav();
  bindCopy();
  bindMagnets();
  bindCursor();
  bindReveals();
  if (state.preview) {
    $("banner").hidden = false;
    $("banner").textContent = "[: preview ] This view is sample data for the " + state.preview + " state. It is not a chain write.";
  }
  state.deployment = await loadDeployment();
  state.txTimes = { ...readTimeCache(), ...(state.deployment.tx_times || {}) };
  writeTimeCache();
  if (!String(state.deployment.contract || "").endsWith(".testnet")) {
    throw new Error("refusing a non-testnet contract");
  }
  $("contract-link").textContent = state.deployment.contract;
  $("contract-link").href = EXPLORER + "/address/" + state.deployment.contract;
  $("agent-link").textContent = state.deployment.agent;
  $("agent-link").href = EXPLORER + "/address/" + state.deployment.agent;
  const key = state.deployment.scoped_key || {};
  $("key-public").textContent = key.public_key || "";
  $("key-allowance").textContent = key.allowance || "";
  const methodName = (key.method_names || ["anchor_evidence"]).join(", ");
  $("key-methods").textContent = methodName.replaceAll("_", "_\n");
  $("retry").addEventListener("click", () => {
    $("status").textContent = "[: reading ]";
    $("status").dataset.on = "no";
    load().catch(showError);
  });
  await load();
  fillTimes().catch(() => {});
  window.setInterval(tick, 1000);
  if (!state.preview) window.setInterval(() => { load().catch(showError); }, 20000);
}

main().catch(showError);
