// Applies a BPS patch in the browser. Same format and checks as tools/patch/bps.py.
(function (root) {
  const TABLE = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    TABLE[n] = c >>> 0;
  }

  function crc32(bytes, end = bytes.length) {
    let c = 0xffffffff;
    for (let i = 0; i < end; i++) c = TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function u32(bytes, at) {
    return (bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16) | (bytes[at + 3] << 24)) >>> 0;
  }

  // Numbers can pass 2^32 while decoding, so this uses plain arithmetic, not bit ops.
  function readNum(bytes, pos) {
    let data = 0, shift = 1;
    for (;;) {
      const x = bytes[pos.i++];
      data += (x & 0x7f) * shift;
      if (x & 0x80) return data;
      shift *= 128;
      data += shift;
    }
  }

  function header(patch) {
    if (String.fromCharCode(...patch.subarray(0, 4)) !== "BPS1") throw new Error("Not a BPS patch.");
    if (crc32(patch, patch.length - 4) !== u32(patch, patch.length - 4)) throw new Error("The patch file is damaged.");
    const pos = { i: 4 };
    const sourceSize = readNum(patch, pos);
    const targetSize = readNum(patch, pos);
    const metaSize = readNum(patch, pos);
    const metadata = new TextDecoder().decode(patch.subarray(pos.i, pos.i + metaSize));
    pos.i += metaSize;
    return {
      sourceSize, targetSize, metadata, body: pos.i,
      sourceCrc: u32(patch, patch.length - 12),
      targetCrc: u32(patch, patch.length - 8),
    };
  }

  function apply(source, patch) {
    const h = header(patch);
    if (source.length !== h.sourceSize || crc32(source) !== h.sourceCrc) {
      throw new Error("This ROM isn't the one the patch was made for.");
    }
    const out = new Uint8Array(h.targetSize);
    const pos = { i: h.body };
    const end = patch.length - 12;
    let o = 0, srcRel = 0, tgtRel = 0;
    while (pos.i < end) {
      const data = readNum(patch, pos);
      const kind = data % 4, len = Math.floor(data / 4) + 1;
      if (kind === 0) {
        out.set(source.subarray(o, o + len), o);
      } else if (kind === 1) {
        out.set(patch.subarray(pos.i, pos.i + len), o);
        pos.i += len;
      } else {
        const d = readNum(patch, pos);
        const off = d % 2 ? -Math.floor(d / 2) : Math.floor(d / 2);
        if (kind === 2) {
          srcRel += off;
          out.set(source.subarray(srcRel, srcRel + len), o);
          srcRel += len;
        } else {
          tgtRel += off;
          for (let k = 0; k < len; k++) out[o + k] = out[tgtRel + k]; // may overlap its own output
          tgtRel += len;
        }
      }
      o += len;
    }
    if (crc32(out) !== h.targetCrc) throw new Error("The patched ROM failed its checksum.");
    return out;
  }

  root.BPS = { crc32, header, apply };
  if (typeof module !== "undefined") module.exports = root.BPS;
})(typeof window !== "undefined" ? window : globalThis);
