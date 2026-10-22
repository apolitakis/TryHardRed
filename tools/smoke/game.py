"""Drive the TryHardRed ROM headless through smokecore (see smokecore.c).

Reads symbol addresses from the build's ELF, struct offsets by compiling a tiny C file with the game's headers,
and flag/var/map ids from the game's constants, so scenarios can say flag("FLAG_SYS_POKEDEX_GET") or
walk_to(5, 8) instead of raw addresses.
"""
import collections
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, "build", "smoke")

KEYS = {"A": 1, "B": 2, "SELECT": 4, "START": 8, "RIGHT": 16, "LEFT": 32, "UP": 64, "DOWN": 128, "R": 256, "L": 512}
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
MAP_OFFSET = 7  # the live map grid has a 7-tile border on each side
def climb(elev, tile):
    """The player's elevation after stepping onto a tile of elevation `tile`, or None if the step is a cliff
    (IsElevationMismatchAt): 0 and 15 are bridges/any-level, and only real levels stick to the player."""
    if elev and tile not in (0, 15) and tile != elev:
        return None
    return elev if tile in (0, 15) else tile


# FireRed one-way walls (MB_FRLG_IMPASSABLE_*): behavior -> the sides of the tile you can't cross
SIDES = {0x30: "e", 0x31: "w", 0x32: "n", 0x33: "s", 0x34: "ne", 0x35: "nw", 0x36: "se", 0x37: "sw"}
SIDE = {(0, 1): ("s", "n"), (0, -1): ("n", "s"), (-1, 0): ("w", "e"), (1, 0): ("e", "w")}  # step -> (out, in)


def side_blocked(here, there, dx, dy):
    """IsMetatileDirectionallyImpassable: leaving through a blocked side of this tile or entering one of the next."""
    out, into = SIDE[(dx, dy)]
    return out in SIDES.get(here, "") or into in SIDES.get(there, "")


JUMPS = {0x38: (1, 0), 0x39: (-1, 0), 0x3A: (0, -1), 0x3B: (0, 1)}  # FireRed ledge behaviors -> hop direction

OFFSETS_C = r"""
#include "global.h"
#include "global.fieldmap.h"
#include <stddef.h>
#define OFF(name, value) const int kOff_##name = value;
OFF(sb1_pos, offsetof(struct SaveBlock1, pos))
OFF(sb1_location, offsetof(struct SaveBlock1, location))
OFF(sb1_flags, offsetof(struct SaveBlock1, flags))
OFF(sb1_vars, offsetof(struct SaveBlock1, vars))
OFF(sb1_money, offsetof(struct SaveBlock1, money))
OFF(obj_size, sizeof(struct ObjectEvent))
OFF(obj_coords, offsetof(struct ObjectEvent, currentCoords))
OFF(obj_local_id, offsetof(struct ObjectEvent, localId))
OFF(sb2_encryption_key, offsetof(struct SaveBlock2, encryptionKey))
OFF(bmon_size, sizeof(struct BattlePokemon))
OFF(bmon_hp, offsetof(struct BattlePokemon, hp))
OFF(bmon_max_hp, offsetof(struct BattlePokemon, maxHP))
OFF(bmon_pp, offsetof(struct BattlePokemon, pp))
OFF(bmon_moves, offsetof(struct BattlePokemon, moves))
"""


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT, **kw).stdout


def build_core():
    os.makedirs(BUILD, exist_ok=True)
    exe = os.path.join(BUILD, "smokecore")
    src = os.path.join(ROOT, "tools", "smoke", "smokecore.c")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        _run(["cc", "-O2", "-DUSE_PNG", "-o", exe, src, "-lmgba", "-lpng"])
    return exe


def read_offsets():
    os.makedirs(BUILD, exist_ok=True)
    src = os.path.join(BUILD, "offsets.c")
    obj = os.path.join(BUILD, "offsets.o")
    with open(src, "w") as f:
        f.write(OFFSETS_C)
    _run(["arm-none-eabi-gcc", "-mthumb", "-mthumb-interwork", "-O1", "-mabi=apcs-gnu", "-march=armv4t",
          "-iquote", "include", "-iquote", "build/firered/include", "-DMODERN=1", "-DTESTING=0", "-DFIRERED",
          "-std=gnu17", "-c", src, "-o", obj])
    syms = {}
    for line in _run(["arm-none-eabi-nm", obj]).splitlines():
        addr, _, name = line.split()
        if name.startswith("kOff_"):
            syms[name[5:]] = int(addr, 16)
    data = _run(["arm-none-eabi-objdump", "-s", "-j", ".rodata", obj])
    raw = b""
    for line in data.splitlines():
        m = re.match(r"^ ([0-9a-f]{4}) ((?:[0-9a-f]{8} ?){1,4})", line)
        if m:
            raw += bytes.fromhex(m.group(2).replace(" ", ""))
    return {k: int.from_bytes(raw[v:v + 4], "little", signed=True) for k, v in syms.items()}


def read_symbols(elf):
    syms = {}
    for line in _run(["arm-none-eabi-nm", elf]).splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms.setdefault(parts[2], int(parts[0], 16))
    return syms


def read_constants(paths):
    """Evaluates simple #defines (numbers, other constants, + and parentheses) from the given headers."""
    raw = {}
    for path in paths:
        live = [True]  # #if IS_FRLG / #else / #endif, the FireRed build's view; other conditions count as true
        for line in open(os.path.join(ROOT, path), encoding="utf-8", errors="replace"):
            d = re.match(r"\s*#\s*(if|ifdef|ifndef|else|elif|endif)\b(.*)", line)
            if d:
                kind, cond = d.group(1), d.group(2).split("//")[0].strip()
                if kind in ("if", "ifdef", "ifndef"):
                    val = {"IS_FRLG": True, "!IS_FRLG": False}.get(cond, True) if kind == "if" else True
                    live.append(live[-1] and val)
                elif kind in ("else", "elif") and len(live) > 1:
                    live[-1] = live[-2] and not live[-1]
                elif kind == "endif" and len(live) > 1:
                    live.pop()
                continue
            if not live[-1]:
                continue
            m = re.match(r"\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+([^/\n]+)", line)
            if m:
                raw[m.group(1)] = m.group(2).strip()
            m = re.match(r"\s*(MAP_[A-Z0-9_]+)\s*=\s*\((\d+)\s*\|\s*\((\d+)\s*<<\s*8\)\)", line)
            if m:
                raw[m.group(1)] = str(int(m.group(2)) | (int(m.group(3)) << 8))
    values = {}

    def value(name, depth=0):
        if name in values:
            return values[name]
        expr = raw.get(name)
        if expr is None or depth > 20:
            return None
        expr = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", lambda m: str(value(m.group(1), depth + 1)), expr)
        try:
            values[name] = int(eval(expr, {"__builtins__": {}}))
        except Exception:
            values[name] = None
        return values[name]

    return {name: value(name) for name in raw}


def read_maps():
    """Map id -> (group, num), map id -> layout, and layout -> (width, height, blockdata path)."""
    maps = {}
    for d in os.listdir(os.path.join(ROOT, "data", "maps")):
        path = os.path.join(ROOT, "data", "maps", d, "map.json")
        if os.path.exists(path):
            j = json.load(open(path))
            maps[j["id"]] = j
    return maps


class Game:
    def __init__(self, rom, shots=None, log=print, invincible=False):
        self.rom = rom
        self.shots = shots
        self.log = log
        self.sym = read_symbols(os.path.splitext(rom)[0] + ".elf")
        self.off = read_offsets()
        self.const = read_constants(["include/constants/opponents_frlg.h", "include/constants/opponents.h",
                                     "include/constants/flags.h", "include/constants/flags_frlg.h",
                                     "include/constants/vars.h", "include/constants/vars_frlg.h",
                                     "include/constants/map_groups.h", "include/constants/items.h"])
        self.maps = read_maps()
        self.map_by_num = {self.const[m]: m for m in self.maps if self.const.get(m) is not None}
        self.proc = subprocess.Popen([build_core(), rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.frame = 0
        self.shot_count = 0
        self.repel = False  # keep a Repel running so wild battles don't stall long walks (trainers still fight)
        self.invincible = invincible  # keep the player's battlers at full HP: the smoke run checks flow, not skill

    # --- the core ---
    def cmd(self, line):
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        out = self.proc.stdout.readline().strip()
        if out.startswith("err"):
            raise RuntimeError(f"smokecore: {line}: {out}")
        return out

    def frames(self, n):
        self.cmd(f"frames {n}")
        self.frame += n

    def keys(self, *names):
        mask = 0
        for k in names:
            mask |= KEYS[k]
        self.cmd(f"keys {mask}")

    def press(self, key, hold=4, after=10):
        self.keys(key)
        self.frames(hold)
        self.keys()
        self.frames(after)

    def r8(self, addr):
        return int(self.cmd(f"read8 {addr}"))

    def r16(self, addr):
        return int(self.cmd(f"read16 {addr}"))

    def r32(self, addr):
        return int(self.cmd(f"read32 {addr}"))

    def dump(self, addr, length):
        return bytes.fromhex(self.cmd(f"dump {addr} {length}"))

    def shot(self, name):
        if not self.shots:
            return None
        os.makedirs(self.shots, exist_ok=True)
        self.shot_count += 1
        path = os.path.join(self.shots, f"{self.shot_count:03d}-{name}.png")
        self.cmd(f"shot {path}")
        return path

    def save_state(self, path):
        self.cmd(f"save {path}")

    def load_state(self, path):
        self.cmd(f"load {path}")

    def close(self):
        self.proc.stdin.write("quit\n")
        self.proc.stdin.close()
        self.proc.wait()

    # --- game state ---
    def callback2(self):
        addr = self.r32(self.sym["gMain"] + 4) & ~1
        return self.func_name(addr)

    def func_name(self, addr):
        if not hasattr(self, "_funcs"):
            self._funcs = {}
            for name, a in self.sym.items():
                self._funcs.setdefault(a & ~1, name)
        return self._funcs.get(addr, hex(addr))

    def sb1(self):
        return self.r32(self.sym["gSaveBlock1Ptr"])

    def flag(self, name):
        fid = self.const[name] if isinstance(name, str) else name
        return bool(self.r8(self.sb1() + self.off["sb1_flags"] + fid // 8) & (1 << (fid % 8)))

    def var(self, name):
        vid = self.const[name] if isinstance(name, str) else name
        return self.r16(self.sb1() + self.off["sb1_vars"] + (vid - self.const["VARS_START"]) * 2)

    def set_var(self, name, value):
        vid = self.const[name] if isinstance(name, str) else name
        self.cmd(f"write16 {self.sb1() + self.off['sb1_vars'] + (vid - self.const['VARS_START']) * 2} {value}")

    def location(self):
        base = self.sb1() + self.off["sb1_location"]
        group, num = self.r8(base), self.r8(base + 1)
        return self.map_by_num.get(group << 8 | num, f"group{group}/num{num}")

    def player_xy(self):
        idx = self.r8(self.sym["gPlayerAvatar"] + 5)
        base = self.sym["gObjectEvents"] + idx * self.off["obj_size"] + self.off["obj_coords"]
        x, y = self.r16(base), self.r16(base + 2)
        return (x if x < 0x8000 else x - 0x10000) - MAP_OFFSET, (y if y < 0x8000 else y - 0x10000) - MAP_OFFSET

    def in_overworld(self):
        return self.callback2() == "CB2_Overworld"

    def script_running(self):
        return self.r8(self.sym["sGlobalScriptContextStatus"]) != 2 or self.r8(self.sym["sLockFieldControls"]) != 0

    def free_to_move(self):
        return self.in_overworld() and not self.script_running()

    def in_battle(self):
        return self.callback2() == "BattleMainCB2"

    def battle_outcome(self):
        return self.r8(self.sym["gBattleOutcome"])

    # --- higher level ---
    def wait_until(self, cond, timeout=3000, step=10, what="condition"):
        for _ in range(0, timeout, step):
            if cond():
                return True
            self.frames(step)
        raise TimeoutError(f"timed out after {timeout} frames waiting for {what} "
                           f"(callback2={self.callback2()}, map={self.location()})")

    def mash(self, key="A", until=None, timeout=3000, what="condition", every=16):
        """Press key every few frames until `until()` holds."""
        for _ in range(0, timeout, every + 4):
            if until and until():
                return True
            self.press(key, hold=4, after=every)
        if until and until():
            return True
        raise TimeoutError(f"timed out mashing {key} waiting for {what} "
                           f"(callback2={self.callback2()}, map={self.location()})")

    def grid(self):
        """The live map grid around the player: (width, height, cells) with map coordinates."""
        w = self.r32(self.sym["gBackupMapLayout"])
        h = self.r32(self.sym["gBackupMapLayout"] + 4)
        ptr = self.r32(self.sym["gBackupMapLayout"] + 8)
        raw = self.dump(ptr, w * h * 2)
        cells = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
        return w, h, cells

    def object_tiles(self):
        tiles = set()
        player = self.r8(self.sym["gPlayerAvatar"] + 5)
        for i in range(16):
            base = self.sym["gObjectEvents"] + i * self.off["obj_size"]
            if i == player or not (self.r8(base) & 1):
                continue
            x, y = self.r16(base + self.off["obj_coords"]), self.r16(base + self.off["obj_coords"] + 2)
            tiles.add((x - MAP_OFFSET, y - MAP_OFFSET))
        return tiles

    def step(self, direction):
        """One tile in a direction; returns True if the player moved. A first press may only turn the player."""
        before = self.player_xy()
        self.keys(direction)
        for _ in range(16):
            self.frames(2)
            if self.player_xy() != before or not self.free_to_move():
                break
        self.keys()
        for _ in range(16):
            if self.r8(self.sym["gPlayerAvatar"] + 3) == 0:  # tileTransitionState: centred on a tile
                break
            self.frames(2)
        return self.player_xy() != before

    def walk_to(self, tx, ty=None, max_steps=300, stop_when=None):
        """Walks to a tile with BFS over the live map grid, replanning around tiles that turn out blocked."""
        goals = tx if isinstance(tx, (set, frozenset)) else {(tx, ty)}
        blocked, talked = set(), set()
        if self.repel:
            self.set_var("VAR_REPEL_STEP_COUNT", 250)
        for _ in range(max_steps):
            if stop_when and stop_when():
                return True
            if not self.free_to_move():
                return False  # a script took over (trainer, event, warp)
            pos = self.player_xy()
            if pos in goals:
                return True
            objects = self.object_tiles()
            path = self._bfs(pos, goals, blocked | objects)
            if not path:  # maybe only people or item balls are in the way: walk up and talk to them
                path = self._bfs(pos, goals, blocked)
            if not path and blocked:  # a tile we gave up on may have been a passing NPC
                blocked.clear()
                path = self._bfs(pos, goals, objects) or self._bfs(pos, goals, set())
            if not path:
                raise RuntimeError(f"no path from {pos} to {sorted(goals)[:4]} on {self.location()}")
            d = path[0]
            dx, dy = DIRS[d]
            ahead = (pos[0] + dx, pos[1] + dy)
            if ahead in objects and ahead not in talked:
                talked.add(ahead)
                self.face(d)
                self.press("A")
                self.handle()
                continue
            if not self.step(d):
                self.frames(20)  # a trainer who spotted us takes a moment to start the script
                if not self.free_to_move():
                    return False
                blocked.add(ahead)
        raise RuntimeError(f"walk_to {sorted(goals)[:4]} gave up at {self.player_xy()} on {self.location()}")

    def _bfs(self, start, goal, blocked):
        """Shortest path of directions to `goal`, or to the nearest of a set of goals."""
        goals = goal if isinstance(goal, (set, frozenset)) else {goal}
        w, h, cells = self.grid()

        def passable(x, y):
            gx, gy = x + MAP_OFFSET, y + MAP_OFFSET
            if not (0 <= gx < w and 0 <= gy < h):
                return False
            if (x, y) in goals:
                return True
            return (cells[gy * w + gx] & 0x0C00) == 0 and (x, y) not in blocked

        def elevation(x, y):
            gx, gy = x + MAP_OFFSET, y + MAP_OFFSET
            return cells[gy * w + gx] >> 12 if 0 <= gx < w and 0 <= gy < h else 0

        def enter(cur, pos, d, hop=False):
            if not hop and here in world.maps and side_blocked(world.behavior(here, *cur[:2]),
                                                               world.behavior(here, *pos), *DIRS[d]):
                return
            e = climb(cur[2], elevation(*pos))
            if e is not None and (x := (pos[0], pos[1], e)) not in prev and passable(*pos):
                prev[x] = (cur, d)
                queue.append(x)

        world = self.world()
        here = self.location()
        mw, mh = self.map_size()
        first = (start[0], start[1], climb(0, elevation(*start)) or 0)
        prev = {first: None}
        queue = collections.deque([first])
        found = None
        while queue:
            cur = queue.popleft()
            if cur[:2] in goals:
                found = cur
                break
            for d, (dx, dy) in DIRS.items():
                nxt = (cur[0] + dx, cur[1] + dy)
                if here in world.maps and 0 <= nxt[0] < mw and 0 <= nxt[1] < mh:
                    jump = JUMPS.get(world.behavior(here, *nxt))
                    if jump is not None:  # a ledge: hop it two tiles the one way it allows
                        if jump == (dx, dy):
                            enter(cur, (nxt[0] + dx, nxt[1] + dy), d, hop=True)
                        continue
                enter(cur, nxt, d)
        if found is None:
            return None
        path = []
        cur = found
        while prev[cur]:
            cur, d = prev[cur]
            path.append(d)
        return path[::-1]

    def world(self):
        if not hasattr(self, "_world"):
            from world import World
            self._world = World(self.maps)
        return self._world

    def face(self, direction):
        self.press(direction, hold=2, after=8)

    def talk(self, direction=None):
        if direction:
            self.face(direction)
        self.press("A")

    # --- map travel ---
    def map_json(self):
        return self.maps.get(self.location())

    def wait_free(self, timeout=6000, key="A"):
        """Advances text with key until the player can move again. Naming screens get the default name."""
        def done():
            cb = self.callback2()
            if cb == "CB2_NamingScreen":
                self.press("START", after=20)
            elif cb == "BattleMainCB2":
                self.battle_auto()
            return self.free_to_move()
        return self.mash(key, until=done, timeout=timeout, what="player control")

    def go_to_map(self, dest, timeout=6000, attempts=6):
        """Walks to a warp on this map that leads to `dest` and takes it, clicking through any scene on the way.
        Some warp tiles only work from one side or not at all (wide door mats), so each is tried in turn."""
        here = self.location()
        changed = lambda: self.location() != here
        tried = set()
        for _ in range(attempts * 4):
            if changed():
                break
            if not self.free_to_move():
                self.handle()
                continue
            warps = [w for w in self.map_json()["warp_events"]
                     if w["dest_map"] == dest and (w["x"], w["y"]) not in tried]
            if not warps:
                raise RuntimeError(f"no working warp from {here} to {dest}")
            px, py = self.player_xy()
            warps.sort(key=lambda w: abs(w["x"] - px) + abs(w["y"] - py))
            w = warps[0]
            try:
                if not self.walk_to(w["x"], w["y"], stop_when=changed):
                    continue
            except RuntimeError:
                tried.add((w["x"], w["y"]))
                continue
            for d in ("DOWN", "UP", "LEFT", "RIGHT"):
                if changed() or not self.free_to_move():
                    break
                self.keys(d)
                self.frames(24)
                self.keys()
                self.frames(40)
            if not changed() and self.free_to_move():
                tried.add((w["x"], w["y"]))
        self.wait_until(lambda: changed() and self.free_to_move(), timeout=timeout, what=f"arrival in {dest}")
        return self.location()

    # --- interruptions and travel across map connections ---
    def battle_auto(self, timeout=60000, gimmick=False):
        """Fights a battle with A through every menu, rotating through the known moves turn by turn so a
        status move that keeps failing can't stall it. With gimmick, presses START once at the first move
        menu to Mega Evolve, Terastallize, Dynamax or Z-Move. Returns gBattleOutcome."""
        asked = False
        turn = 0
        in_menu = False
        for _ in range(0, timeout, 16):
            if not self.in_battle():
                break
            if self.invincible:
                self.heal_player_battlers()
            choosing = self.player_choosing_move()
            if choosing and not in_menu:
                if self.invincible and turn >= 12:  # a walled matchup (Vine Whip into Koffing): finish it off
                    self.weaken_foes()
                self.pick_move_slot(turn)
                turn += 1
                if gimmick and not asked:
                    self.press("START", hold=4, after=12)
                    self.shot("gimmick-trigger")
                    asked = True
            in_menu = choosing
            self.press("A", hold=4, after=12)
        else:
            self.shot("stuck-battle")
            raise TimeoutError(f"battle on {self.location()} didn't end in {timeout} frames")
        outcome = self.battle_outcome()
        self.log(f"    battle on {self.location()}: outcome {outcome}")
        return outcome

    def pick_move_slot(self, turn):
        """Moves the cursor in the 2x2 move menu to the turn's slot among the moves the battler knows."""
        mon = self.sym["gBattleMons"]
        known = [i for i in range(4) if self.r16(mon + self.off["bmon_moves"] + 2 * i)]
        if not known:
            return
        target = known[turn % len(known)]
        cur = self.r8(self.sym["gMoveSelectionCursor"])
        if cur % 2 != target % 2:
            self.press("RIGHT" if target % 2 else "LEFT", hold=2, after=6)
        if cur // 2 != target // 2:
            self.press("DOWN" if target // 2 else "UP", hold=2, after=6)

    def player_choosing_move(self):
        return self.func_name(self.r32(self.sym["gBattlerControllerFuncs"]) & ~1) == "HandleInputChooseMove"

    def heal_player_battlers(self):
        size, base = self.off["bmon_size"], self.sym["gBattleMons"]
        for battler in (0, 2):  # player side
            mon = base + battler * size
            hp, max_hp = self.r16(mon + self.off["bmon_hp"]), self.r16(mon + self.off["bmon_max_hp"])
            if 0 < hp < max_hp:
                self.cmd(f"write16 {mon + self.off['bmon_hp']} {max_hp}")
            for i in range(4):
                if hp and self.r8(mon + self.off["bmon_pp"] + i) < 5:
                    self.cmd(f"write8 {mon + self.off['bmon_pp'] + i} 20")

    def weaken_foes(self):
        size, base = self.off["bmon_size"], self.sym["gBattleMons"]
        for battler in (1, 3):
            hp = base + battler * size + self.off["bmon_hp"]
            if self.r16(hp) > 1:
                self.cmd(f"write16 {hp} 1")

    def handle(self):
        """Deals with whatever took control away: a battle, a scene or text."""
        if self.in_battle():
            self.battle_auto()
        if not self.free_to_move():
            self.wait_free(timeout=20000)

    def go(self, x, y, attempts=40):
        """walk_to that survives wild battles, trainers and scenes on the way."""
        here = self.location()
        for _ in range(attempts):
            if self.location() != here:
                return False
            if self.walk_to(x, y):
                return True
            self.handle()
        raise RuntimeError(f"go {(x, y)} on {here} kept getting interrupted")

    def map_size(self):
        w, h = self.r32(self.sym["gBackupMapLayout"]), self.r32(self.sym["gBackupMapLayout"] + 4)
        return w - (2 * MAP_OFFSET + 1), h - 2 * MAP_OFFSET  # MAP_OFFSET_W, MAP_OFFSET_H

    def cross_to(self, dest, attempts=40):
        """Walks off the edge of this map into the connected map `dest`."""
        here = self.location()
        conns = [c for c in (self.map_json().get("connections") or []) if c["map"] == dest]
        if not conns:
            raise RuntimeError(f"{here} doesn't connect to {dest}")
        direction = conns[0]["direction"]
        changed = lambda: self.location() != here
        for _ in range(attempts):
            if changed():
                break
            if not self.free_to_move():
                self.handle()
                continue
            w, h = self.map_size()
            gw, gh, cells = self.grid()
            if direction in ("up", "down"):
                y = -1 if direction == "up" else h
                edge = [(x, y) for x in range(w)]
            else:
                x = -1 if direction == "left" else w
                edge = [(x, y) for y in range(h)]
            edge = [(x, y) for x, y in edge
                    if not cells[(y + MAP_OFFSET) * gw + x + MAP_OFFSET] & 0x0C00]
            if not edge:
                raise RuntimeError(f"no open edge on {here} toward {dest}")
            self.walk_to(set(edge), stop_when=changed)
        self.wait_until(lambda: changed(), timeout=600, what=f"arrival in {dest}")
        if not self.free_to_move():
            self.handle()
        return self.location()

    def travel(self, *hops):
        """Each hop is a map id reached by a warp or a connection from the current map."""
        for dest in hops:
            j = self.map_json()
            if any(c["map"] == dest for c in (j.get("connections") or [])):
                self.cross_to(dest)
            else:
                self.go_to_map(dest)
            self.log(f"  -> {self.location()} at {self.player_xy()}")

    def take_warp(self, x, y, attempts=20):
        """Walks onto the warp at (x, y) on this map and through it."""
        here = self.location()
        changed = lambda: self.location() != here
        for _ in range(attempts):
            if changed():
                break
            if not self.free_to_move():
                self.handle()
                continue
            if not self.walk_to(x, y, stop_when=changed):
                continue
            # Doors and stairs fire on arrival; exit mats and cave mouths need a push in the right direction.
            for d in ("DOWN", "UP", "LEFT", "RIGHT"):
                if changed() or not self.free_to_move():
                    break
                if self.player_xy() != (x, y) and not self.walk_to(x, y, stop_when=changed):
                    break
                self.keys(d)
                self.frames(24)
                self.keys()
                self.frames(40)
        self.wait_until(lambda: changed() and self.free_to_move(), timeout=600, what=f"warp at {(x, y)}")

    def travel_to(self, goal, pos=None, max_hops=40):
        """Plans a route over the game's maps (see world.py) and follows it, replanning after every hop. With pos,
        arrives in the part of the goal map that can walk to pos."""
        for _ in range(max_hops):
            here = self.location()
            if here == goal and (pos is None or self.world()._reaches(here, self.player_xy(), tuple(pos))):
                return
            route = self.world().route(here, self.player_xy(), goal, pos)
            if not route:
                raise RuntimeError(f"no route from {here} {self.player_xy()} to {goal}")
            kind, target, dest = route[0]
            if kind == "conn":
                self.cross_to(dest)
            else:
                try:
                    self.take_warp(*target)
                except TimeoutError:
                    self.go_to_map(dest)  # some warp tiles never fire (wide mats); try the map's others
            self.log(f"  -> {self.location()} at {self.player_xy()}")
        raise RuntimeError(f"travel_to {goal} took more than {max_hops} hops")
