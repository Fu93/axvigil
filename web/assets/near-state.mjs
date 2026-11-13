/** Pure status rules for the NEAR record page. No DOM, no network. */

export function phase(record, nowNs) {
  const status = record && record.status;
  if (status === "Final") return "final";
  if (status === "Revoked") return "revoked";
  if (status === "Challenged") return "challenged";
  if (status === "Pending") {
    const ready = BigInt(record.ready_at_ns);
    const now = BigInt(nowNs);
    return now < ready ? "window" : "pending";
  }
  return "unknown";
}

export function formatRemain(ms) {
  const whole = Math.max(0, Math.floor(Number(ms) / 1000));
  const days = Math.floor(whole / 86400);
  const hours = Math.floor((whole % 86400) / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const seconds = whole % 60;
  const pad = (value) => String(value).padStart(2, "0");
  if (days > 0) return days + "d " + pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
  return pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
}

function step(id, label, state) {
  return { id, label, state };
}

/**
 * verify -> anchor -> challenge window -> final or challenged -> revoked
 * state is "done", "now", "wait", or "skip".
 */
export function timeline(record, nowNs) {
  const kind = phase(record, nowNs);
  const challengedPath = kind === "challenged" || kind === "revoked";
  const windowState = kind === "window" ? "now" : "done";
  let decisionLabel = "Final";
  let decisionState = "wait";
  if (challengedPath) {
    decisionLabel = "Challenged";
    decisionState = kind === "challenged" ? "now" : "done";
  } else if (kind === "final") {
    decisionState = "done";
  } else if (kind === "pending") {
    decisionState = "now";
  }
  const revokedState = kind === "revoked" ? "done" : challengedPath ? "wait" : "skip";
  return [
    step("verify", "Verify", "done"),
    step("anchor", "Anchor", "done"),
    step("window", "Window", windowState),
    step("decide", decisionLabel, decisionState),
    step("revoked", "Revoked", revokedState),
  ];
}

export function shortHash(hex) {
  const clean = String(hex || "").replace(/^0x/, "");
  if (clean.length <= 18) return clean;
  return clean.slice(0, 8) + "…" + clean.slice(-6);
}
