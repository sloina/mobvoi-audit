#!/usr/bin/env python3
# audit_listen.py -- interactive listening audit of wake-word positives.
#
# Plays every positive utterance from a wekws-style data.list that does not
# yet have a verdict in the output CSV, and records a single-key verdict:
#
#     SPACE = ok    h = hard    n = very_hard    B (shift+b) = ultra_hard
#     z = bad       r = replay (normal speed)    b = go BACK one item
#     q = quit (progress saved)
#
# Design (crash-safe, resumable):
#   * append + flush after every keypress; the LAST row per utt_id wins;
#   * the file is compacted (deduplicated, sorted) on quit/finish,
#     preserving each verdict's original timestamp;
#   * rerunning resumes automatically; a dedicated second pass over
#     selected labels:  python audit_listen.py ... --recheck bad,ultra_hard
#     (recorded with source=ear_recheck).
#
# Output CSV columns: utt_id, kw, verdict, source, timestamp
#
# This is the tool used for the full Mobvoi test/dev audit accompanying
# the paper. Audio playback uses ffplay when available (with optional
# speed-up via --speed); on Windows it falls back to winsound.

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time

# --- keyboard: single-key on Windows/POSIX ---------------------------------
try:
    import msvcrt

    def getkey():
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):      # arrow/function keys: ignore
            msvcrt.getch()
            return None
        return ch.decode(errors="ignore")
except ImportError:                        # POSIX
    import termios
    import tty

    def getkey():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

KEYMAP = {" ": "ok", "h": "hard", "H": "hard",
          "n": "very_hard", "N": "very_hard",
          "B": "ultra_hard",
          "z": "bad", "Z": "bad"}
VERDICTS = ("ok", "hard", "very_hard", "ultra_hard", "bad")
KW_OF_TXT = {"<HI_XIAOWEN>": "kw0", "<NIHAO_WENWEN>": "kw1"}
KWNAME = {"kw0": "Hi Xiaowen", "kw1": "Nihao Wenwen"}

FFPLAY = shutil.which("ffplay")


def play(path, speed=1.0):
    if FFPLAY and speed != 1.0:
        try:
            subprocess.run([FFPLAY, "-nodisp", "-autoexit",
                            "-loglevel", "quiet",
                            "-af", f"atempo={speed}", path], check=True)
            return
        except Exception:
            pass
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    elif FFPLAY:
        subprocess.run([FFPLAY, "-nodisp", "-autoexit",
                        "-loglevel", "quiet", path], check=False)
    else:
        sys.exit("no audio player found: install ffmpeg (ffplay)")


def load_positives(data_list):
    pos = []
    with open(data_list, "r", encoding="utf8") as f:
        for line in f:
            o = json.loads(line)
            kw = KW_OF_TXT.get(o["txt"].upper())
            if kw:
                pos.append((str(o["key"]), kw, o.get("wav")))
    pos.sort(key=lambda x: (x[1], x[0]))
    return pos


def build_wavmap(positives, wav_dirs):
    wavmap, missing = {}, []
    for uid, _, listed in positives:
        found = None
        for d in wav_dirs:
            p = os.path.join(d, uid + ".wav")
            if os.path.exists(p):
                found = p
                break
        if not found and listed and os.path.exists(listed):
            found = listed
        if found:
            wavmap[uid] = found
        else:
            missing.append(uid)
    return wavmap, missing


def compact(cur, out):
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "kw", "verdict", "source", "timestamp"])
        for uid in sorted(cur, key=lambda u: (cur[u][0], u)):
            kw, v, src, ts = cur[uid]
            w.writerow([uid, kw, v, src, ts])


def main():
    ap = argparse.ArgumentParser(
        description="interactive listening audit of wake-word positives")
    ap.add_argument("--data_list", required=True,
                    help="wekws-style jsonl data list (test or dev)")
    ap.add_argument("--wav_dir", action="append", default=[],
                    help="directory with <utt_id>.wav files "
                         "(repeat for several; data.list paths are the "
                         "fallback)")
    ap.add_argument("--out", required=True,
                    help="output verdict CSV (created/resumed)")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="playback speed via ffplay atempo (e.g. 1.5)")
    ap.add_argument("--recheck", default=None,
                    help="comma-separated labels to re-listen to "
                         "(e.g. bad,ultra_hard); records source=ear_recheck")
    args = ap.parse_args()
    recheck = set(args.recheck.split(",")) if args.recheck else set()

    positives = load_positives(args.data_list)
    print(f"positives: {len(positives)} "
          f"(kw0 {sum(1 for _, k, _ in positives if k == 'kw0')}, "
          f"kw1 {sum(1 for _, k, _ in positives if k == 'kw1')})")

    cur = {}
    if os.path.exists(args.out):
        for r in csv.DictReader(open(args.out, encoding="utf-8-sig")):
            cur[r["utt_id"]] = (r["kw"], r["verdict"], r["source"],
                                r.get("timestamp", ""))
        print(f"  resume: {len(cur)} verdicts already in {args.out}")

    wavmap, missing = build_wavmap(positives, args.wav_dir)
    if missing:
        mp = os.path.splitext(args.out)[0] + "_missing_wavs.txt"
        open(mp, "w").write("\n".join(missing))
        print(f"  WARNING: {len(missing)} wavs not found -> {mp}")

    if recheck:
        todo = [(u, k) for u, k, _ in positives
                if u in cur and cur[u][1] in recheck and u in wavmap]
        print(f"RECHECK mode {sorted(recheck)}: {len(todo)} items")
    else:
        todo = [(u, k) for u, k, _ in positives
                if u not in cur and u in wavmap]
        print(f"to listen: {len(todo)}")
    print("keys: SPACE=ok  h=hard  n=very_hard  B=ultra_hard  z=bad  "
          "r=replay  b=back  q=quit\n")

    fout = open(args.out, "a", newline="", encoding="utf-8-sig")
    if fout.tell() == 0:
        fout.write("utt_id,kw,verdict,source,timestamp\n")
        fout.flush()
    w = csv.writer(fout)
    src = "ear_recheck" if recheck else "ear_round1"
    i = 0
    while i < len(todo):
        uid, kw = todo[i]
        prior = f"  [now: {cur[uid][1]}]" if uid in cur else ""
        print(f"[{i + 1}/{len(todo)}]  {KWNAME.get(kw, kw)}  {uid[:10]}{prior}")
        play(wavmap[uid], args.speed)
        while True:
            ch = getkey()
            if ch is None:
                continue
            if ch == "r":
                play(wavmap[uid], 1.0)
                continue
            if ch in ("b", "\x08"):
                i = max(0, i - 1)
                print("  <- back")
                break
            if ch == "q":
                fout.close()
                compact(cur, args.out)
                print(f"stopped; compacted -> {args.out}")
                return
            v = KEYMAP.get(ch)
            if v:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                cur[uid] = (kw, v, src, ts)
                w.writerow([uid, kw, v, src, ts])
                fout.flush()
                print(f"    -> {v}")
                i += 1
                break
    fout.close()
    compact(cur, args.out)
    from collections import Counter
    c = Counter((kw, v) for kw, v, _, _ in cur.values())
    print(f"\nDONE -> {args.out}")
    for kw in ("kw0", "kw1"):
        print(f"  {kw}: " + "  ".join(
            f"{v}={c.get((kw, v), 0)}" for v in VERDICTS))


if __name__ == "__main__":
    main()
