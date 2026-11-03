#!/usr/bin/env python3
"""Placeholder colonnade for web/assets/3d/board_podium.glb.

Drop-in contract (the textured file must match this, or the page will not retarget it):
  origin   plinth center, y = 0 at the underside
  up       +Y, authored height 2.4
  row      four columns along +X, centered, outer centers at x = ±1.35
  facing   +Z toward the camera, depth about 1.7
  scale    1 in the loader. No fit-to-bounds.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "web" / "assets" / "3d" / "board_podium.glb"
HEIGHT = 2.4
COLUMNS = (-1.35, -0.45, 0.45, 1.35)


def box(cx: float, cy: float, cz: float, sx: float, sy: float, sz: float):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    faces = [
        ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
        ((0, 1, 0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)]),
        ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
        ((0, 0, -1), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)]),
        ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
        ((1, 0, 0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)]),
    ]
    pos, nrm, idx = [], [], []
    for normal, corners in faces:
        base = len(pos) // 3
        for x, y, z in corners:
            pos.extend((cx + x, cy + y, cz + z))
            nrm.extend(normal)
        idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
    return pos, nrm, idx


def cylinder(cx: float, y0: float, cz: float, radius: float, height: float, sides: int = 16):
    pos, nrm, idx = [], [], []
    y1 = y0 + height
    ring0 = 0
    for i in range(sides):
        a = math.tau * i / sides
        nx, nz = math.cos(a), math.sin(a)
        pos.extend((cx + nx * radius, y0, cz + nz * radius))
        nrm.extend((nx, 0, nz))
        pos.extend((cx + nx * radius, y1, cz + nz * radius))
        nrm.extend((nx, 0, nz))
    for i in range(sides):
        a = i * 2
        b = ((i + 1) % sides) * 2
        idx.extend((ring0 + a, ring0 + b, ring0 + a + 1, ring0 + a + 1, ring0 + b, ring0 + b + 1))
    cap0 = len(pos) // 3
    pos.extend((cx, y0, cz))
    nrm.extend((0, -1, 0))
    pos.extend((cx, y1, cz))
    nrm.extend((0, 1, 0))
    for i in range(sides):
        a = math.tau * i / sides
        nx, nz = math.cos(a), math.sin(a)
        pos.extend((cx + nx * radius, y0, cz + nz * radius))
        nrm.extend((0, -1, 0))
        pos.extend((cx + nx * radius, y1, cz + nz * radius))
        nrm.extend((0, 1, 0))
    for i in range(sides):
        n = (i + 1) % sides
        idx.extend((cap0, cap0 + 2 + n * 2, cap0 + 2 + i * 2))
        idx.extend((cap0 + 1, cap0 + 3 + i * 2, cap0 + 3 + n * 2))
    return pos, nrm, idx


def add(dst_p, dst_n, dst_i, part):
    p, n, ix = part
    base = len(dst_p) // 3
    dst_p.extend(p)
    dst_n.extend(n)
    dst_i.extend(i + base for i in ix)


def build():
    pos, nrm, idx = [], [], []
    add(pos, nrm, idx, box(0, 0.06, 0, 5.2, 0.12, 1.7))
    add(pos, nrm, idx, box(0, 0.19, 0, 4.7, 0.14, 1.35))
    shaft_h = HEIGHT - 0.26 - 0.08 - 0.08 - 0.10
    for x in COLUMNS:
        add(pos, nrm, idx, box(x, 0.30, 0, 0.56, 0.08, 0.56))
        add(pos, nrm, idx, cylinder(x, 0.34, 0, 0.22, shaft_h))
        add(pos, nrm, idx, cylinder(x, 0.34 + shaft_h, 0, 0.30, 0.08, 16))
        cap_y = 0.34 + shaft_h + 0.08 + 0.05
        add(pos, nrm, idx, box(x, cap_y, 0, 0.62, 0.10, 0.62))
    return pos, nrm, idx


def pack(pos, nrm, idx):
    pos_b = struct.pack("<" + "f" * len(pos), *pos)
    nrm_b = struct.pack("<" + "f" * len(nrm), *nrm)
    idx_b = struct.pack("<" + "H" * len(idx), *idx)
    blob = pos_b + nrm_b + idx_b
    pad = (4 - len(blob) % 4) % 4
    blob += b"\x00" * pad
    npos, nnrm, nidx = len(pos_b), len(nrm_b), len(idx_b)
    gltf = {
        "asset": {"version": "2.0", "generator": "axvigil-board-podium"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "board_podium", "mesh": 0}],
        "meshes": [{
            "name": "colonnade",
            "primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1},
                "indices": 2,
                "material": 0,
            }],
        }],
        "materials": [{
            "name": "obsidian",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.07, 0.07, 0.065, 1],
                "metallicFactor": 0,
                "roughnessFactor": 0.52,
            },
        }],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": npos, "target": 34962},
            {"buffer": 0, "byteOffset": npos, "byteLength": nnrm, "target": 34962},
            {"buffer": 0, "byteOffset": npos + nnrm, "byteLength": nidx, "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(pos) // 3, "type": "VEC3",
                "min": [min(pos[0::3]), min(pos[1::3]), min(pos[2::3])],
                "max": [max(pos[0::3]), max(pos[1::3]), max(pos[2::3])],
            },
            {"bufferView": 1, "componentType": 5126, "count": len(nrm) // 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": len(idx), "type": "SCALAR"},
        ],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<I", len(js)) + b"JSON" + js
    out += struct.pack("<I", len(blob)) + b"BIN\x00" + blob
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(out)
    ys = pos[1::3]
    xs = pos[0::3]
    print(f"wrote {OUT} ({len(out)} bytes) y {min(ys):.3f}..{max(ys):.3f} x {min(xs):.3f}..{max(xs):.3f}")


if __name__ == "__main__":
    pack(*build())
