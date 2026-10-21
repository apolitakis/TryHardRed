// Playtest page: patch the player's own FireRed ROM in the browser, then run it in EmulatorJS (mGBA core).
// The clean ROM is kept in this browser's IndexedDB so it is picked once; the patch is fetched fresh each visit,
// so every update applies by itself. Nothing is uploaded.
(function () {
  const PATCH_DIR = "patch/";
  const GAME_NAME = "firered-gen9"; // fixed, so EmulatorJS keeps the same save across patch updates
  const $ = id => document.getElementById(id);
  let manifest = null, cleanRom = null;

  function status(text, kind) {
    const el = $("status");
    el.textContent = text;
    el.className = kind || "";
  }

  // --- the clean ROM, remembered in IndexedDB ---
  function db() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open("firered-gen9-play", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("files");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function store(op, value) {
    try {
      const d = await db();
      return await new Promise((resolve, reject) => {
        const tx = d.transaction("files", op === "get" ? "readonly" : "readwrite");
        const os = tx.objectStore("files");
        const req = op === "get" ? os.get("clean-rom") : op === "put" ? os.put(value, "clean-rom") : os.delete("clean-rom");
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      return undefined; // private window or blocked storage: the page still works, it just asks again next time
    }
  }

  function patchFor(rom) {
    const crc = BPS.crc32(rom);
    return manifest.patches.find(p => parseInt(p.sourceCrc, 16) === crc && p.sourceSize === rom.length);
  }

  async function useRom(bytes, remember) {
    const p = patchFor(bytes);
    if (!p) {
      cleanRom = null;
      $("play").disabled = true;
      status("That file isn't a clean " + manifest.patches.map(p => p.source).join(" or ") +
        " ROM. Patched, trimmed or other-region ROMs won't work.", "bad");
      return;
    }
    cleanRom = bytes;
    if (remember) await store("put", bytes);
    $("forget").hidden = false;
    $("play").disabled = false;
    status("Found " + p.source + ". Ready to play.", "ok");
  }

  async function play() {
    $("play").disabled = true;
    status("Patching…");
    try {
      const p = patchFor(cleanRom);
      const res = await fetch(PATCH_DIR + p.file, { cache: "no-cache" });
      if (!res.ok) throw new Error("Couldn't download the patch (" + res.status + ").");
      const rom = BPS.apply(cleanRom, new Uint8Array(await res.arrayBuffer()));
      start(URL.createObjectURL(new Blob([rom], { type: "application/octet-stream" })));
    } catch (e) {
      status(e.message, "bad");
      $("play").disabled = false;
    }
  }

  function start(romUrl) {
    document.body.classList.add("playing");
    Object.assign(window, {
      EJS_player: "#game",
      EJS_core: "gba",
      EJS_gameUrl: romUrl,
      EJS_gameName: GAME_NAME,
      EJS_pathtodata: "emulatorjs/data/",
      EJS_DEBUG_XX: true, // load the unminified sources we vendor
      EJS_startOnLoaded: true,
      EJS_color: "#c8402b",
    });
    const s = document.createElement("script");
    s.src = "emulatorjs/data/loader.js";
    document.body.appendChild(s);
  }

  async function init() {
    try {
      const res = await fetch(PATCH_DIR + "patch.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      manifest = await res.json();
    } catch (e) {
      status("The patch isn't available right now. Try again later.", "bad");
      return;
    }
    const label = "Build " + manifest.version + (manifest.built ? " · " + manifest.built : "");
    $("build").textContent = label + ".";
    $("build2").textContent = label + ".";

    $("rom").addEventListener("change", async e => {
      const f = e.target.files[0];
      if (f) await useRom(new Uint8Array(await f.arrayBuffer()), true);
    });
    $("forget").addEventListener("click", async () => {
      await store("delete");
      cleanRom = null;
      $("forget").hidden = true;
      $("play").disabled = true;
      status("Forgotten. Your saves are kept.");
    });
    $("play").addEventListener("click", play);

    const saved = await store("get");
    if (saved) await useRom(new Uint8Array(saved), false);
  }

  init();
})();
