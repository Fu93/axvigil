#!/usr/bin/env python3
"""Scroll the landing page quickly and assert section content stays visible.

At 1440x900 and 390x844, scroll 120px every 100ms. Every [data-reveal] node
and every section heading, card, citation, and roadmap row that intersects
the viewport must reach a used opacity above 0.9 within 600ms.
"""
from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STEP_PX = 120
STEP_MS = 100
WINDOW_MS = 600
VIEWPORTS = ({"width": 1440, "height": 900}, {"width": 390, "height": 844})

PROBE = r"""() => {
  const vh = window.innerHeight;
  const sel = "[data-reveal], main section h1, main section h2, main section h3, main section .lede, main section .card, main section .sources li, main section .timeline li, main section .stat, main section .recompute, main section .faq details";
  const seen = new Set();
  const items = [];
  document.querySelectorAll(sel).forEach((el) => {
    if (seen.has(el)) return;
    seen.add(el);
    const r = el.getBoundingClientRect();
    const hit = r.width > 1 && r.height > 1 && r.bottom > 0 && r.top < vh;
    let op = 1;
    let node = el;
    while (node && node !== document.documentElement) {
      const o = parseFloat(getComputedStyle(node).opacity);
      if (!Number.isNaN(o)) op *= o;
      node = node.parentElement;
    }
    items.push({
      i: items.length,
      hit,
      op,
      top: Math.round(r.top),
      label: (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 72)
    });
  });
  return items;
}"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def serve(port: int) -> http.server.ThreadingHTTPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, fmt, *args):
            return

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run_viewport(page, url: str, viewport: dict) -> tuple[int, int, list]:
    page.set_viewport_size(viewport)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("[data-reveal]", timeout=5000)
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, 0)")
    first: dict[int, float] = {}
    passed: set[int] = set()
    failures = []
    seen = 0
    max_y = page.evaluate("Math.max(0, document.documentElement.scrollHeight - window.innerHeight)")
    y = 0
    next_step = 0.0
    deadline = None
    while True:
        now = page.evaluate("performance.now()")
        if y < max_y and now >= next_step:
            y = min(max_y, y + STEP_PX)
            page.evaluate("(top) => window.scrollTo(0, top)", y)
            next_step = now + STEP_MS
            deadline = now + WINDOW_MS + 80
        states = page.evaluate(PROBE)
        seen = max(seen, len(states))
        now = page.evaluate("performance.now()")
        for item in states:
            if item["hit"] and item["i"] not in first:
                first[item["i"]] = now
            if item["i"] in passed or item["i"] not in first:
                continue
            if item["op"] > 0.9:
                passed.add(item["i"])
            elif now - first[item["i"]] >= WINDOW_MS:
                failures.append(item)
                passed.add(item["i"])
        if y >= max_y and deadline is not None and now >= deadline:
            break
        page.wait_for_timeout(20)
    print(f"viewport {viewport['width']}x{viewport['height']}")
    print(f"  targets {seen}, intersected {len(first)}, visible {len(passed) - len(failures)}, failed {len(failures)}")
    for item in failures:
        print(f"  FAIL opacity={item['op']:.3f} top={item['top']} {item['label']}")
    return seen, len(first), failures


def check_board(page, url: str, viewport: dict) -> list:
    page.set_viewport_size(viewport)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("text=6/6", timeout=8000)
    page.wait_for_selector("text=no patch submitted", timeout=8000)
    page.wait_for_selector("text=hiddenTestsPass", timeout=8000)
    page.wait_for_selector("text=2c45b7a", timeout=8000)
    page.wait_for_selector("text=83/114", timeout=8000)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    clipped = page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll("td, th, h1, h2, p")];
          const bad = [];
          for (const el of nodes) {
            const r = el.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) continue;
            if (r.right > window.innerWidth + 1 || r.left < -1) {
              bad.push((el.innerText || "").trim().slice(0, 60));
              if (bad.length > 6) break;
            }
          }
          return bad;
        }"""
    )
    print(f"leaderboard {viewport['width']}x{viewport['height']} overflow={overflow} clipped={len(clipped)}")
    failures = []
    if overflow > 1:
        failures.append({"label": "page overflow", "op": overflow, "top": 0})
    for label in clipped:
        failures.append({"label": "clipped " + label, "op": 0, "top": 0})
    return failures


def main() -> int:
    port = free_port()
    httpd = serve(port)
    url = f"http://127.0.0.1:{port}/index.html"
    board = f"http://127.0.0.1:{port}/leaderboard.html"
    failures = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport=VIEWPORTS[0])
            print(f"scroll step {STEP_PX}px every {STEP_MS}ms, opacity window {WINDOW_MS}ms")
            for viewport in VIEWPORTS:
                _, _, bad = run_viewport(page, url, viewport)
                failures.extend(bad)
                failures.extend(check_board(page, board, viewport))
            browser.close()
    finally:
        httpd.shutdown()
    if failures:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
