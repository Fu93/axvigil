#!/usr/bin/env python3
"""AxVigil Local Dev Server: Zero-Cache, Full-CORS, Multi-Threaded, Web3-MIME-Ready."""
import http.server
import os
import sys

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

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    httpd = http.server.ThreadingHTTPServer(("", port), ZeroCacheHTTPRequestHandler)
    print(f"AxVigil Dev Server running on http://localhost:{port}/web/index.html")
    print(f"Directory: {DIRECTORY}")
    print("Zero-Cache: Active (no-store, no-cache, must-revalidate)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
