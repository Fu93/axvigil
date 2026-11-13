import assert from "node:assert/strict";
import test from "node:test";
import { formatRemain, phase, shortHash, timeline } from "./near-state.mjs";

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

test("short hash keeps both ends", () => {
  assert.equal(shortHash("d90054a2e3f54f11ac40fa32ba9562c1aa6538f7430be757e5a0ab5efe0b81ad"), "d90054a2…0b81ad");
});
