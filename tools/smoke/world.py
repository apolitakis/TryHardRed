"""Static route planning over the game's maps for the smoke run.

Reads each map's layout (collision bits from map.bin), warps and connections, and finds a chain of hops from a
position on one map to another map: walk to a warp, or walk off an edge into a connected map. It follows
ledges and elevation but ignores NPCs and story blocks, so the runner still replans around surprises at run time.
"""
import collections
import json
import os
import re

from game import ROOT, climb, side_blocked

DIR_STEP = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
# FireRed metatile behaviors (include/constants/metatile_behaviors_frlg.h)
JUMPS = {0x38: (1, 0), 0x39: (-1, 0), 0x3A: (0, -1), 0x3B: (0, 1)}  # ledge -> the way you can hop it
WATER = {0x10, 0x11, 0x12, 0x13, 0x15, 0x19, 0x1A, 0x1B, 0x22, 0x50, 0x51, 0x52, 0x53}
NUM_PRIMARY_FRLG = 640


def _tileset_attributes():
    """Tileset symbol -> metatile attribute words, read from the tileset headers and INCBIN paths."""
    heads = open(os.path.join(ROOT, "src", "data", "tilesets", "headers.h")).read()
    bins = open(os.path.join(ROOT, "src", "data", "tilesets", "metatiles.h")).read()
    paths = dict(re.findall(r"const u16 (gMetatileAttributes_\w+)\[\] = INCBIN_U16\(\"([^\"]+)\"\)", bins))
    out = {}
    for name, attr in re.findall(r"const struct Tileset (\w+) =\s*\{[^}]*?\.metatileAttributes = (\w+)", heads):
        if attr in paths and os.path.exists(os.path.join(ROOT, paths[attr])):
            raw = open(os.path.join(ROOT, paths[attr]), "rb").read()
            out[name] = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw) - 3, 4)]
    return out


class World:
    def __init__(self, maps):
        self.maps = maps  # map id -> map.json
        layouts = json.load(open(os.path.join(ROOT, "data", "layouts", "layouts.json")))["layouts"]
        self.layouts = {l["id"]: l for l in layouts if "id" in l}
        self._grids = {}
        self._attrs = None

    def grid(self, map_id):
        if map_id not in self._grids:
            lay = self.layouts[self.maps[map_id]["layout"]]
            raw = open(os.path.join(ROOT, lay["blockdata_filepath"]), "rb").read()
            cells = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
            self._grids[map_id] = (lay["width"], lay["height"], cells)
        return self._grids[map_id]

    def behavior(self, map_id, x, y):
        if self._attrs is None:
            self._attrs = _tileset_attributes()
        w, h, cells = self.grid(map_id)
        if not (0 <= x < w and 0 <= y < h):
            return 0
        lay = self.layouts[self.maps[map_id]["layout"]]
        metatile = cells[y * w + x] & 0x3FF
        if metatile < NUM_PRIMARY_FRLG:
            table, i = self._attrs.get(lay["primary_tileset"], []), metatile
        else:
            table, i = self._attrs.get(lay["secondary_tileset"], []), metatile - NUM_PRIMARY_FRLG
        return table[i] & 0x1FF if i < len(table) else 0

    def obstacles(self, map_id):
        """Cut trees, Strength boulders and Rock Smash rocks: field-move gates the planner can't pass yet."""
        key = ("obstacles", map_id)
        if key not in self._grids:
            self._grids[key] = {(o["x"], o["y"]) for o in self.maps[map_id]["object_events"]
                                if any(k in (o.get("script") or "") for k in ("CutTree", "Boulder", "RockSmash"))}
        return self._grids[key]

    def open_tile(self, map_id, x, y):
        w, h, cells = self.grid(map_id)
        return (0 <= x < w and 0 <= y < h and not cells[y * w + x] & 0x0C00
                and (x, y) not in self.obstacles(map_id) and self.behavior(map_id, x, y) not in WATER)

    def elevation(self, map_id, x, y):
        w, h, cells = self.grid(map_id)
        return cells[y * w + x] >> 12 if 0 <= x < w and 0 <= y < h else 0

    def step(self, map_id, x, y, e, dx, dy):
        """Where a step from (x, y) at elevation e lands, as (x, y, elevation): the next tile, two tiles on for a
        ledge hopped the right way, or None (wall, water, cliff)."""
        nx, ny = x + dx, y + dy
        w, h, _ = self.grid(map_id)
        if not (0 <= nx < w and 0 <= ny < h):
            return None
        if self.behavior(map_id, nx, ny) in JUMPS:
            if JUMPS[self.behavior(map_id, nx, ny)] != (dx, dy):
                return None
            nx, ny = nx + dx, ny + dy
        elif side_blocked(self.behavior(map_id, x, y), self.behavior(map_id, nx, ny), dx, dy):
            return None
        e2 = climb(e, self.elevation(map_id, nx, ny))
        return (nx, ny, e2) if e2 is not None and self.open_tile(map_id, nx, ny) else None

    def region(self, map_id, start):
        """Tiles reachable on foot from start (hopping ledges downhill, never off a cliff), plus the blocked tiles
        next to them (warps often sit on those)."""
        first = (start[0], start[1], climb(0, self.elevation(map_id, *start)) or 0)
        seen, edge = {first}, set()
        queue = collections.deque([first])
        while queue:
            x, y, e = queue.popleft()
            for dx, dy in DIR_STEP.values():
                n = self.step(map_id, x, y, e, dx, dy)
                if n is None:
                    edge.add((x + dx, y + dy))
                elif n not in seen:
                    seen.add(n)
                    queue.append(n)
        return {(x, y) for x, y, _ in seen}, edge

    def _reaches(self, map_id, pos, goal):
        reach, edge = self.region(map_id, pos)
        return goal in reach or goal in edge

    def hops_from(self, map_id, pos):
        """Every hop available from pos: (kind, target, dest map, arrival pos)."""
        j = self.maps[map_id]
        reach, edge = self.region(map_id, pos)
        out = []
        for w in j["warp_events"]:
            if (w["x"], w["y"]) in reach or (w["x"], w["y"]) in edge:
                dest = self.maps.get(w["dest_map"])
                if not dest:
                    continue
                try:
                    dw = dest["warp_events"][int(w["dest_warp_id"])]
                except (ValueError, IndexError):
                    continue
                out.append(("warp", (w["x"], w["y"]), w["dest_map"], (dw["x"], dw["y"])))
        w_, h_, _ = self.grid(map_id)
        for c in j.get("connections") or []:
            if c["map"] not in self.maps:
                continue
            dw, dh, _ = self.grid(c["map"])
            d, off = c["direction"], int(c["offset"])
            if d in ("up", "down"):
                y = 0 if d == "up" else h_ - 1
                xs = [x for x in range(w_) if (x, y) in reach and 0 <= x - off < dw]
                if xs:
                    x = xs[len(xs) // 2]
                    out.append(("conn", d, c["map"], (x - off, dh - 1 if d == "up" else 0)))
            else:
                x = 0 if d == "left" else w_ - 1
                ys = [y for y in range(h_) if (x, y) in reach and 0 <= y - off < dh]
                if ys:
                    y = ys[len(ys) // 2]
                    out.append(("conn", d, c["map"], (dw - 1 if d == "left" else 0, y - off)))
        return out

    def route(self, map_id, pos, goal_map, goal_pos=None):
        """Fewest hops from (map, pos) to goal_map (to the part of it that reaches goal_pos, if given: caves split
        one map into pieces joined by other floors), as a list of (kind, target, dest map)."""
        start = (map_id, tuple(pos))
        prev = {start: None}
        queue = collections.deque([start])
        while queue:
            cur = queue.popleft()
            if cur[0] == goal_map and (goal_pos is None or self._reaches(cur[0], cur[1], tuple(goal_pos))):
                path = []
                while prev[cur]:
                    cur, hop = prev[cur]
                    path.append(hop)
                return path[::-1]
            for kind, target, dest, arrival in self.hops_from(*cur):
                nxt = (dest, arrival)
                if nxt not in prev:
                    prev[nxt] = (cur, (kind, target, dest))
                    queue.append(nxt)
        return None
