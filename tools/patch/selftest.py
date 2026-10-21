#!/usr/bin/env python3
"""Round-trip check for the BPS tools, with no ROM needed: build a fake "retail" ROM, a fake "build" that moves,
edits and pads its data, then make a patch and apply it with both bps.py and the browser's site/play/bps.js (Node)."""
import os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bps  # noqa: E402

rng = random.Random(7)
blocks = [bytes(rng.randrange(256) for _ in range(4096)) for _ in range(256)]
source = b"".join(blocks)  # 1 MiB
moved = blocks[:]
rng.shuffle(moved)
target = bytearray(b"".join(moved[:200]) + bytes(rng.randrange(256) for _ in range(50000)) + b"".join(moved[200:]))
for _ in range(500):
    target[rng.randrange(len(target))] = rng.randrange(256)
target = bytes(target) + b"\xff" * (2 * len(source) - len(target))

patch = bps.make(source, target)
assert bps.apply(source, patch) == target, "bps.py round trip failed"
assert len(patch) < len(target) // 4, f"patch too big: {len(patch)}"
try:
    bps.apply(source[:-1] + b"\0", patch)
    sys.exit("a wrong source ROM was accepted")
except ValueError:
    pass

with tempfile.TemporaryDirectory() as d:
    for name, data in (("src", source), ("tgt", target), ("p.bps", patch)):
        open(os.path.join(d, name), "wb").write(data)
    js = os.path.join(HERE, "..", "..", "site", "play", "bps.js")
    check = (
        "const fs=require('fs'),B=require(process.argv[1]),d=process.argv[2];"
        "const out=B.apply(new Uint8Array(fs.readFileSync(d+'/src')),new Uint8Array(fs.readFileSync(d+'/p.bps')));"
        "if(Buffer.compare(Buffer.from(out),fs.readFileSync(d+'/tgt'))!==0){console.error('mismatch');process.exit(1)}"
    )
    subprocess.run(["node", "-e", check, os.path.abspath(js), d], check=True)
print(f"ok: {len(target):,}-byte target from a {len(patch):,}-byte patch; bps.py and bps.js agree")
