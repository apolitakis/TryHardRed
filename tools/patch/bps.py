#!/usr/bin/env python3
"""Make and apply BPS patches (the format Flips/beat use), with no dependencies.

    python3 tools/patch/bps.py make  CLEAN.gba BUILT.gba OUT.bps
    python3 tools/patch/bps.py apply CLEAN.gba PATCH.bps OUT.gba
    python3 tools/patch/bps.py info  PATCH.bps

The romhack is a full decomp build, so its data sits at different offsets than in the
retail ROM. `make` finds relocated runs with a hash index of the source (SourceCopy),
same-offset runs (SourceRead) and repeats such as the 0xFF padding (TargetCopy), and
writes everything else literally (TargetRead).
"""
import sys
import zlib

MAGIC = b"BPS1"
SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = range(4)
ANCHOR = 16   # bytes hashed per source anchor
STRIDE = 8    # one anchor every STRIDE source bytes
MIN_COPY = ANCHOR + STRIDE  # every match this long is found


def write_num(out, n):
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return
        out.append(x)
        n -= 1


def read_num(buf, pos):
    data, shift = 0, 1
    while True:
        x = buf[pos]
        pos += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, pos
        shift <<= 7
        data += shift


def write_signed(out, n):
    write_num(out, (abs(n) << 1) | (1 if n < 0 else 0))


def match_len(a, ai, b, bi, limit):
    """Length of the common run a[ai:] / b[bi:], at most limit."""
    n = 0
    step = 4096
    while n < limit:
        k = min(step, limit - n)
        if a[ai + n:ai + n + k] == b[bi + n:bi + n + k]:
            n += k
            continue
        if k <= 16:
            while n < limit and a[ai + n] == b[bi + n]:
                n += 1
            return n
        step = max(16, k // 8)
    return n


def make(source, target, metadata=b""):
    src, tgt = bytes(source), bytes(target)
    ns, nt = len(src), len(tgt)

    index = {}
    for p in range(0, ns - ANCHOR + 1, STRIDE):
        key = src[p:p + ANCHOR]
        if key.count(key[0]) == ANCHOR:
            continue  # filler; TargetCopy handles runs
        index.setdefault(key, p)

    out = bytearray(MAGIC)
    write_num(out, ns)
    write_num(out, nt)
    write_num(out, len(metadata))
    out += metadata

    src_rel = tgt_rel = 0
    pending = 0  # start of the literal run not yet written

    def flush(upto):
        nonlocal pending
        if upto > pending:
            write_num(out, ((upto - pending - 1) << 2) | TARGET_READ)
            out.extend(tgt[pending:upto])
        pending = upto

    i = 0
    while i < nt:
        best_len, best = 0, None
        # Same offset in the source.
        if i < ns:
            n = match_len(src, i, tgt, i, min(ns, nt) - i)
            if n >= 4:
                best_len, best = n, (SOURCE_READ, i, 0)
        # Repeat of the previous byte (padding, fills).
        if best_len < 64 and i > 0 and tgt[i] == tgt[i - 1]:
            n = match_len(tgt, i - 1, tgt, i, nt - i)
            if n >= 8 and n > best_len:
                best_len, best = n, (TARGET_COPY, i - 1, 0)
        # Relocated run in the source.
        if best_len < MIN_COPY and i + ANCHOR <= nt:
            p = index.get(tgt[i:i + ANCHOR])
            if p is not None:
                n = match_len(src, p, tgt, i, min(ns - p, nt - i))
                back = 0
                while back < i - pending and back < p and src[p - back - 1] == tgt[i - back - 1]:
                    back += 1
                if n + back >= MIN_COPY and n > best_len:
                    best_len, best = n + back, (SOURCE_COPY, p - back, back)
        if best is None:
            i += 1
            continue
        kind, at, back = best
        start = i - back
        flush(start)
        write_num(out, ((best_len - 1) << 2) | kind)
        if kind == SOURCE_COPY:
            write_signed(out, at - src_rel)
            src_rel = at + best_len
        elif kind == TARGET_COPY:
            write_signed(out, at - tgt_rel)
            tgt_rel = at + best_len
        i = start + best_len
        pending = i
    flush(nt)

    out += zlib.crc32(src).to_bytes(4, "little")
    out += zlib.crc32(tgt).to_bytes(4, "little")
    out += zlib.crc32(out).to_bytes(4, "little")
    return bytes(out)


def header(patch):
    if patch[:4] != MAGIC:
        raise ValueError("not a BPS patch")
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise ValueError("patch is corrupt (patch CRC mismatch)")
    ns, pos = read_num(patch, 4)
    nt, pos = read_num(patch, pos)
    nm, pos = read_num(patch, pos)
    return {
        "source_size": ns, "target_size": nt, "metadata": patch[pos:pos + nm],
        "source_crc": int.from_bytes(patch[-12:-8], "little"),
        "target_crc": int.from_bytes(patch[-8:-4], "little"),
        "body": pos + nm,
    }


def apply(source, patch):
    h = header(patch)
    if len(source) != h["source_size"] or zlib.crc32(source) != h["source_crc"]:
        raise ValueError("this ROM is not the one the patch was made for")
    tgt = bytearray(h["target_size"])
    pos, end = h["body"], len(patch) - 12
    o = src_rel = tgt_rel = 0
    while pos < end:
        data, pos = read_num(patch, pos)
        kind, length = data & 3, (data >> 2) + 1
        if kind == SOURCE_READ:
            tgt[o:o + length] = source[o:o + length]
        elif kind == TARGET_READ:
            tgt[o:o + length] = patch[pos:pos + length]
            pos += length
        else:
            d, pos = read_num(patch, pos)
            d = -(d >> 1) if d & 1 else d >> 1
            if kind == SOURCE_COPY:
                src_rel += d
                tgt[o:o + length] = source[src_rel:src_rel + length]
                src_rel += length
            else:
                tgt_rel += d
                for k in range(length):  # may overlap its own output
                    tgt[o + k] = tgt[tgt_rel + k]
                tgt_rel += length
        o += length
    if zlib.crc32(tgt) != h["target_crc"]:
        raise ValueError("patched ROM failed its checksum")
    return bytes(tgt)


def main(argv):
    if len(argv) == 5 and argv[1] == "make":
        src, tgt = open(argv[2], "rb").read(), open(argv[3], "rb").read()
        patch = make(src, tgt)
        if apply(src, patch) != tgt:
            sys.exit("internal error: patch does not round-trip")
        open(argv[4], "wb").write(patch)
        print(f"{argv[4]}: {len(patch):,} bytes (target {len(tgt):,}, crc32 {zlib.crc32(tgt):08x})")
    elif len(argv) == 5 and argv[1] == "apply":
        out = apply(open(argv[2], "rb").read(), open(argv[3], "rb").read())
        open(argv[4], "wb").write(out)
        print(f"{argv[4]}: {len(out):,} bytes")
    elif len(argv) == 3 and argv[1] == "info":
        h = header(open(argv[2], "rb").read())
        print({k: v for k, v in h.items() if k != "body"})
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
