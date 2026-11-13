import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { formatRemain, phase, plainGrade, shortHash, timeline, timesInOrder } from "./near-state.mjs";

const deployment = JSON.parse(readFileSync(new URL("../../docs/near/deployment.json", import.meta.url), "utf8"));

const ready = "1000000000000";

test("pending before ready_at is the open window", () => {
  assert.equal(phase({ status: "Pending", ready_at_ns: ready }, "999999999999"), "window");
});

test("pending after ready_at is waiting for finalize", () => {
  assert.equal(phase({ status: "Pending", ready_at_ns: ready }, ready), "pending");
});

test("final and revoked ignore the clock", () => {
  assert.equal(phase({ status: "Final", ready_at_ns: ready }, "1"), "final");
  assert.equal(phase({ status: "Revoked", ready_at_ns: ready }, "1"), "revoked");
  assert.equal(phase({ status: "Challenged", ready_at_ns: ready }, "1"), "challenged");
});

test("honest timeline ends on final and skips revoked", () => {
  const steps = timeline({ status: "Final", ready_at_ns: ready }, ready);
  assert.deepEqual(steps.map((item) => item.state), ["done", "done", "done", "done", "skip"]);
  assert.equal(steps[3].label, "Final");
});

test("revoked timeline marks challenge and revoked done", () => {
  const steps = timeline({ status: "Revoked", ready_at_ns: ready }, ready);
  assert.equal(steps[3].label, "Challenged");
  assert.equal(steps[3].state, "done");
  assert.equal(steps[4].state, "done");
});

test("open window is the current step", () => {
  const steps = timeline({ status: "Pending", ready_at_ns: ready }, "1");
  assert.equal(steps[2].state, "now");
  assert.equal(steps[3].state, "wait");
});

test("countdown pads hours minutes and seconds", () => {
  assert.equal(formatRemain(0), "00:00:00");
  assert.equal(formatRemain(3661000), "01:01:01");
  assert.equal(formatRemain(90000000), "1d 01:00:00");
});

test("class and difficulty are words", () => {
  assert.equal(plainGrade(0, 0), "reentrancy · basic");
  assert.equal(plainGrade(1, 2), "price manipulation · legendary");
});

test("baked chain times stay in column order", () => {
  const tx = deployment.transactions;
  const times = deployment.tx_times;
  assert.equal(timesInOrder([
    times[tx.anchor_honest],
    times[tx.anchor_honest],
    times[tx.finalize_honest],
  ]), true);
  assert.equal(timesInOrder([
    times[tx.anchor_bad],
    times[tx.anchor_bad],
    times[tx.challenge_bad],
    times[tx.resolve_bad],
  ]), true);
  assert.equal(times[tx.anchor_bad] < times[tx.challenge_bad], true);
  assert.equal(times[tx.challenge_bad] < times[tx.resolve_bad], true);
});

test("published column times do not run backwards", () => {
  assert.equal(timesInOrder([
    "2026-11-13 10:13:40.244 UTC",
    "2026-11-13 10:13:40.244 UTC",
    "2026-11-13 10:16:07.501 UTC",
  ]), true);
  assert.equal(timesInOrder([
    "2026-11-13 10:13:44.513 UTC",
    "2026-11-13 10:13:44.513 UTC",
    "2026-11-13 10:13:51.761 UTC",
    "2026-11-13 10:13:57.443 UTC",
  ]), true);
  assert.equal(timesInOrder([
    "2026-11-13 10:15:15.102 UTC",
    "2026-11-13 10:13:51.761 UTC",
  ]), false);
});

test("short hash keeps both ends", () => {
  assert.equal(shortHash("d90054a2e3f54f11ac40fa32ba9562c1aa6538f7430be757e5a0ab5efe0b81ad"), "d90054a2…0b81ad");
});
