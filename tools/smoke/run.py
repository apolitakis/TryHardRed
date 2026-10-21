#!/usr/bin/env python3
"""TryHardRed smoke run: plays the built ROM headless from a new game, chapter by chapter.

Each chapter starts from the save state the previous one left in build/smoke/states/, checks what it is meant
to prove (flags, items, badges) and saves its own state, so a failure shows exactly where the game broke.
Battles are fought by picking the first move with the player's side kept at full HP: the run checks that
the game flows (scripts, warps, battles, gimmicks), not that a team can win.

  python3 tools/smoke/run.py                 # every chapter
  python3 tools/smoke/run.py --from brock    # resume from the state before a chapter
  python3 tools/smoke/run.py --shots DIR     # also write screenshots
Needs libmgba-dev (apt) and a built pokefirered.gba + .elf.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game import BUILD, ROOT, Game  # noqa: E402

STATES = os.path.join(BUILD, "states")


class SmokeFailure(Exception):
    pass


def check(cond, what):
    if not cond:
        raise SmokeFailure(what)


def new_game(g):
    """Boot, title, new game, Oak's speech with default names, to the bedroom."""
    g.mash("START", until=lambda: g.callback2() == "CB2_MainMenu", timeout=3000, what="main menu")
    g.wait_free(timeout=12000)
    check(g.location() == "MAP_PALLET_TOWN_PLAYERS_HOUSE_2F", f"new game starts in {g.location()}")


def starter(g):
    """Out of the house, Oak stops you on Route 1, pick Bulbasaur, beat the rival."""
    g.travel("MAP_PALLET_TOWN_PLAYERS_HOUSE_1F", "MAP_PALLET_TOWN")
    g.go(12, 1)
    g.wait_free(timeout=20000)
    check(g.location() == "MAP_PALLET_TOWN_PROFESSOR_OAKS_LAB", f"Oak took the player to {g.location()}")
    g.go(8, 5)
    g.talk("UP")
    g.wait_free(timeout=20000)
    check(g.var("VAR_STARTER_MON") is not None, "starter chosen")
    g.go(6, 11)
    g.wait_free(timeout=30000)
    check(g.var("VAR_MAP_SCENE_PALLET_TOWN_PROFESSOR_OAKS_LAB") >= 4, "rival battle in the lab")


def pokedex(g):
    """Fetch Oak's Parcel from the Viridian Mart, get the Pokédex and the TryHardRed gimmick kit."""
    g.travel("MAP_PALLET_TOWN", "MAP_ROUTE1", "MAP_VIRIDIAN_CITY", "MAP_VIRIDIAN_CITY_MART")
    g.handle()
    check(g.var("VAR_MAP_SCENE_VIRIDIAN_CITY_MART") >= 1, "parcel from the Viridian Mart clerk")
    g.travel("MAP_VIRIDIAN_CITY", "MAP_ROUTE1", "MAP_PALLET_TOWN", "MAP_PALLET_TOWN_PROFESSOR_OAKS_LAB")
    g.go(6, 4)
    g.talk("UP")
    g.wait_free(timeout=30000)
    check(g.flag("FLAG_SYS_POKEDEX_GET"), "Pokédex")
    check(g.flag("FLAG_TRH_RECEIVED_GIMMICK_KIT"), "gimmick kit from Oak")
    check(g.flag("FLAG_TRH_EXP_SHARE_ON"), "Exp. Share switched on")
    check(g.flag("FLAG_TRH_TERA_ORB_CHARGED"), "Tera Orb charged")


def pewter(g):
    """Viridian Forest to Pewter City."""
    g.travel("MAP_PALLET_TOWN", "MAP_ROUTE1", "MAP_VIRIDIAN_CITY", "MAP_ROUTE2",
             "MAP_ROUTE2_VIRIDIAN_FOREST_SOUTH_ENTRANCE", "MAP_VIRIDIAN_FOREST",
             "MAP_ROUTE2_VIRIDIAN_FOREST_NORTH_ENTRANCE", "MAP_ROUTE2", "MAP_PEWTER_CITY")


def brock(g):
    """Brock, with Terastal allowed by the fight's gimmick rule."""
    g.travel("MAP_PEWTER_CITY_GYM")
    g.go(6, 6)
    g.talk("UP")
    g.mash("A", until=g.in_battle, timeout=3000, what="Brock's battle")
    g.battle_auto(gimmick=True)
    g.wait_free(timeout=20000)
    check(g.flag("FLAG_DEFEATED_BROCK"), "Brock defeated")
    check(g.flag("FLAG_BADGE01_GET"), "Boulder Badge")


def mt_moon(g):
    """Route 3 and Mt. Moon (beat Miguel, take the Helix Fossil) to Cerulean City."""
    g.travel_to("MAP_MT_MOON_B2F")
    g.go(14, 8)
    g.talk("UP")
    g.wait_free(timeout=20000)
    check(g.flag("FLAG_GOT_HELIX_FOSSIL"), "Helix Fossil")
    g.travel_to("MAP_CERULEAN_CITY")


def misty(g):
    """Misty, with Dynamax allowed by the fight's gimmick rule."""
    g.travel_to("MAP_CERULEAN_CITY_GYM")
    g.go(8, 7)
    g.talk("UP")
    g.mash("A", until=g.in_battle, timeout=3000, what="Misty's battle")
    g.battle_auto(gimmick=True)
    g.wait_free(timeout=20000)
    check(g.flag("FLAG_DEFEATED_MISTY"), "Misty defeated")
    check(g.flag("FLAG_BADGE02_GET"), "Cascade Badge")


CHAPTERS = [new_game, starter, pokedex, pewter, brock]
# Not in the default run yet: the walker still trips in Mt. Moon's fossil room. Run with --from mt_moon.
WORK_IN_PROGRESS = [mt_moon, misty]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(ROOT, "pokefirered.gba"))
    ap.add_argument("--from", dest="start", help="chapter to start from (uses the state the one before saved)")
    ap.add_argument("--only", help="run just this chapter")
    ap.add_argument("--shots", help="directory for screenshots")
    args = ap.parse_args()

    chapters = CHAPTERS + WORK_IN_PROGRESS if (args.only or args.start) else CHAPTERS
    names = [c.__name__ for c in chapters]
    first = names.index(args.only or args.start) if (args.only or args.start) else 0
    last = first + 1 if args.only else len(chapters)
    os.makedirs(STATES, exist_ok=True)
    g = Game(args.rom, shots=args.shots, invincible=True)
    if first > 0:
        g.load_state(os.path.join(STATES, f"{names[first - 1]}.ss"))

    failed = None
    for chapter in chapters[first:last]:
        t0, f0 = time.time(), g.frame
        print(f"== {chapter.__name__}: {chapter.__doc__.splitlines()[0]}")
        try:
            chapter(g)
        except Exception as e:  # report and stop: later chapters need this one's state
            g.shot(f"FAIL-{chapter.__name__}")
            failed = f"{chapter.__name__}: {type(e).__name__}: {e}"
            break
        g.save_state(os.path.join(STATES, f"{chapter.__name__}.ss"))
        g.shot(chapter.__name__)
        print(f"   ok in {(g.frame - f0) / 3600:.1f} game minutes ({time.time() - t0:.0f}s), "
              f"now on {g.location()} at {g.player_xy()}")
    g.close()
    if failed:
        print(f"SMOKE FAIL {failed}")
        return 1
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
