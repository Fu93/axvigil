#!/usr/bin/env python3
"""Step the landing scroll and reject one-frame luminance spikes.

The sweep waits until the section models are resident, then moves the
scroll position in small increments. Mean luminance of the right half of
the WebGL canvas is sampled after each step. A single-frame white flash
shows up as a jump from one sample to the next.
"""
from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STEP_PX = 24
# A white blowout lifts the right-half mean by well more than this.
# Ordinary scroll motion, including the hero entering the sample, stays under it.
MAX_DELTA = 0.09

SAMPLE = r"""() => {
  const src = document.querySelector("#stage canvas");
  if (!src || src.width < 2) return -1;
  const w = 48;
  const h = 32;
  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(src, 0, 0, w, h);
  const data = ctx.getImageData(Math.floor(w * 0.46), 0, Math.ceil(w * 0.54), h).data;
  let sum = 0;
  let n = 0;
  for (let i = 0; i < data.length; i += 4) {
    sum += (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
    n += 1;
  }
  return n ? sum / n : -1;
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
                    timeout=60000,
                )
            frames(page, 8)
            max_y = page.evaluate("Math.max(0, document.documentElement.scrollHeight - window.innerHeight)")
            y = 0
            prev = None
            worst = 0.0
            worst_y = 0
            samples = 0
            while y <= max_y:
                page.evaluate("(top) => window.scrollTo(0, top)", y)
                frames(page, 2)
                luma = page.evaluate(SAMPLE)
                if luma >= 0 and prev is not None:
                    delta = luma - prev
                    samples += 1
                    if delta > worst:
                        worst = delta
                        worst_y = y
                    if delta > MAX_DELTA:
                        failures.append({"y": y, "delta": delta, "luma": luma, "prev": prev})
                if luma >= 0:
                    prev = luma
                if y >= max_y:
                    break
                y = min(max_y, y + STEP_PX)
            print(f"samples {samples} worst +{worst:.4f} at y={worst_y} limit {MAX_DELTA}")
            for item in failures[:8]:
                print(
                    f"  FAIL y={item['y']} delta={item['delta']:.4f} "
                    f"luma={item['luma']:.4f} prev={item['prev']:.4f}"
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
