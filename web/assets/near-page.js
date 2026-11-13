import { formatRemain, phase, shortHash, timeline } from "./near-state.mjs";

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
  preview: new URLSearchParams(location.search).get("preview"),
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

async function rpc(payload) {
  if (state.preview === "down") throw new Error("The testnet RPC did not answer.");
  const targets = [RPC];
  if (location.protocol.startsWith("http")) targets.push(location.origin + "/near-rpc");
  let last;
  for (const url of targets) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(4000),
      });
      if (!response.ok) throw new Error("RPC " + response.status);
      const body = await response.json();
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

function txFor(hash) {
  const deployment = state.deployment;
  const txs = deployment.transactions || {};
  if (hash === deployment.honest_evidence_hash) {
    return [["Anchor", txs.anchor_honest], ["Finalize", txs.finalize_honest]];
  }
  if (hash === deployment.bad_evidence_hash) {
    return [["Anchor", txs.anchor_bad], ["Challenge", txs.challenge_bad], ["Revoke", txs.resolve_bad]];
  }
  return [];
}

function labelFor(kind) {
  if (kind === "window") return "Window";
  if (kind === "pending") return "Awaiting finalize";
  if (kind === "challenged") return "Challenged";
  if (kind === "final") return "Final";
  if (kind === "revoked") return "Revoked";
  return "Unknown";
}

function renderTimeline(record) {
  return timeline(record, nowNs()).map((item) => (
    `<li class="tl-step is-${item.state}">
      <span class="tl-mark" aria-hidden="true"></span>
      <span class="tl-label">${escapeHtml(item.label)}</span>
    </li>`
  )).join("");
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
  const links = txFor(record.evidence_hash).filter((pair) => pair[1]).map(([name, id]) => (
    `<a class="tx" href="${EXPLORER}/txns/${encodeURIComponent(id)}" target="_blank" rel="noopener">${escapeHtml(name)} <span aria-hidden="true">↗</span></a>`
  )).join("");
  return `<article class="near-card" data-hash="${escapeHtml(record.evidence_hash)}">
    <header class="card-top">
      <p class="bracket">[:${escapeHtml(labelFor(kind).toUpperCase())}]</p>
      <p class="who">${escapeHtml(record.agent)}</p>
    </header>
    ${clockHtml(record, kind)}
    <p class="hash-row">
      <code title="${escapeHtml(record.evidence_hash)}">${escapeHtml(shortHash(record.evidence_hash))}</code>
      <button type="button" class="copy" data-copy="${escapeHtml(record.evidence_hash)}">[ copy ]</button>
    </p>
    <p class="meta">bundle ${escapeHtml(shortHash(record.bundle_sha256))} · class ${escapeHtml(record.vuln_class)} · difficulty ${escapeHtml(record.difficulty)}</p>
    <ol class="timeline" aria-label="Record timeline">${renderTimeline(record)}</ol>
    <p class="txs">${links}</p>
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

async function main() {
  bindNav();
  bindCopy();
  bindMagnets();
  if (state.preview) {
    $("banner").hidden = false;
    $("banner").textContent = "[: preview ] This view is sample data for the " + state.preview + " state. It is not a chain write.";
  }
  const response = await fetch("../docs/near/deployment.json");
  if (!response.ok) throw new Error("deployment.json " + response.status);
  state.deployment = await response.json();
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
  $("key-methods").textContent = (key.method_names || []).join(", ") || "anchor_evidence";
  $("retry").addEventListener("click", () => {
    $("status").textContent = "[: reading ]";
    $("status").dataset.on = "no";
    load().catch(showError);
  });
  await load();
  window.setInterval(tick, 1000);
  if (!state.preview) window.setInterval(() => { load().catch(showError); }, 20000);
}

main().catch(showError);
