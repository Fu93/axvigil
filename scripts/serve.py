#!/usr/bin/env python3
"""AxVigil Local Dev Server: Zero-Cache, Full-CORS, Multi-Threaded, Web3-MIME-Ready."""
import http.server
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

PORT = 8080
DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class ZeroCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".woff2": "font/woff2",
        ".wasm": "application/wasm",
        ".json": "application/json",
        ".mjs": "text/javascript",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/web/index.html")
            self.end_headers()
            return
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        """Same-origin proxy for the NEAR testnet RPC. The host is fixed."""
        if urlparse(self.path).path != "/near-rpc":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 20_000:
            self.send_error(413)
            return
        raw = self.rfile.read(length)
        if b"mainnet" in raw.lower():
            self.send_error(400, "mainnet refused")
            return
        request = urllib.request.Request(
            "https://rpc.testnet.near.org",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = exc.code
        except urllib.error.URLError:
            self.send_error(502, "testnet RPC unreachable")
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    httpd = http.server.ThreadingHTTPServer(("", port), ZeroCacheHTTPRequestHandler)
    print(f"AxVigil Dev Server running on http://localhost:{port}/web/index.html")
    print(f"NEAR record page: http://localhost:{port}/web/near.html")
    print(f"Directory: {DIRECTORY}")
    print("Zero-Cache: Active (no-store, no-cache, must-revalidate)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
