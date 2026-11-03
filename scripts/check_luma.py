#!/usr/bin/env python3
"""Wheel through the How transition and the footer at 30 fps.

Samples the full WebGL canvas after every wheel event. A frame whose mean
luminance rises more than MAX_RISE (0-255) above the previous frame fails.
The How cage burst was about +4 and the footer crystal blob about +16.
"""
from __future__ import annotations

import http.server
import math
import socket
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
WHEEL_PX = 18
# A flash jumps and then falls back. The footer blob was about +16 and the
# cage burst about +4, both reversing on the next frame. A model fading in
# rises and stays, so it is not a spike.
MAX_SPIKE = 3.5

SAMPLE = r"""() => {
  const src = document.querySelector("#stage canvas");
  if (!src || src.width < 2) return -1;
  const w = 80;
  const h = 45;
  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(src, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h).data;
  let sum = 0;
  const n = data.length / 4;
  for (let i = 0; i < data.length; i += 4) {
    sum += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
  }
  return sum / n;
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


def frames(page, count: int) -> None:
    page.evaluate(
        """(n) => new Promise((resolve) => {
          let left = n;
          function tick() {
            left -= 1;
            if (left <= 0) resolve();
            else requestAnimationFrame(tick);
          }
          requestAnimationFrame(tick);
        })""",
        count,
    )


def wheel_span(page, start: float, end: float, label: str) -> tuple[float, list]:
    """Scroll with real wheel events and a moving pointer. Returns worst rise and failures."""
    page.evaluate("(y) => window.scrollTo(0, y)", start)
    frames(page, 6)
    width = page.evaluate("window.innerWidth")
    height = page.evaluate("window.innerHeight")
    prev = None
    prev2 = None
    worst = 0.0
    worst_y = start
    failures = []
    samples = 0
    guard = 0
    while True:
        y = page.evaluate("window.scrollY")
        if y >= end - 1 or guard > 500:
            break
        guard += 1
        ang = guard * 0.35
        page.mouse.move(
            width * 0.55 + math.sin(ang) * 36,
            height * 0.48 + math.cos(ang) * 22,
        )
        page.mouse.wheel(0, WHEEL_PX)
        frames(page, 1)
        luma = page.evaluate(SAMPLE)
        y_now = page.evaluate("window.scrollY")
        if luma >= 0 and prev is not None and prev2 is not None:
            rise = prev - prev2
            fall = prev - luma
            samples += 1
            if rise > worst:
                worst = rise
                worst_y = y_now
            if rise > MAX_SPIKE and fall > rise * 0.5:
                failures.append({"y": y_now, "rise": rise, "luma": prev, "prev": prev2})
        if luma >= 0:
            prev2 = prev
            prev = luma
    print(f"{label} samples {samples} worst spike +{worst:.2f} at y={worst_y:.0f} limit {MAX_SPIKE}")
    return worst, failures


def main() -> int:
    port = free_port()
    httpd = serve(port)
    url = f"http://127.0.0.1:{port}/index.html?lum=1"
    failures = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader-webgl"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.add_init_script("try{sessionStorage.setItem('axv-intro-seen','1')}catch(e){}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#stage canvas", timeout=20000)
            page.evaluate("document.documentElement.style.scrollBehavior='auto'")
            for sel, key in (("#how", "how"), ("#faq", "faq")):
                page.evaluate(
                    """(sel) => document.querySelector(sel).scrollIntoView({block:'center', behavior:'instant'})""",
                    sel,
                )
                page.wait_for_function(
                    """(key) => (document.getElementById('hero-core').dataset.models || '').includes(key)""",
                    arg=key,
                    timeout=70000,
                )
            spans = page.evaluate(
                """() => {
                  const how = document.getElementById('how');
                  const close = document.getElementById('close');
                  const footer = document.getElementById('footer');
                  const vh = window.innerHeight;
                  return {
                    how0: Math.max(0, how.offsetTop - vh * 0.2),
                    how1: how.offsetTop + how.offsetHeight * 0.9,
                    foot0: Math.max(0, close.offsetTop - vh * 0.35),
                    foot1: footer.offsetTop + footer.offsetHeight - vh
                  };
                }"""
            )
            _, how_bad = wheel_span(page, spans["how0"], spans["how1"], "how")
            _, foot_bad = wheel_span(page, spans["foot0"], spans["foot1"], "footer")
            failures.extend(how_bad)
            failures.extend(foot_bad)
            page.evaluate(
                """() => document.getElementById('how').scrollIntoView({block:'center', behavior:'instant'})"""
            )
            frames(page, 8)
            page.screenshot(path="/tmp/qa/how_fix.png")
            for item in failures[:8]:
                print(
                    f"  FAIL y={item['y']:.0f} rise={item['rise']:.2f} "
                    f"luma={item['luma']:.2f} prev={item['prev']:.2f}"
                )
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
