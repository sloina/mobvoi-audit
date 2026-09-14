#!/usr/bin/env python3
# whisper_flagging.py -- ASR-based pre-filtering of Mobvoi positive
# utterances, as used in the label-noise audit accompanying the paper.
#
# Transcribes every positive utterance of a split with faster-whisper
# (base model by default), prompted with the two wake words, and applies
# two matching criteria to each transcript:
#
#   * core   (primary): the wake-word core must appear in a short
#            transcript; otherwise the utterance is flagged.
#   * strict (supplementary): the transcript must be exactly the wake
#            word, up to one extra character; utterances that pass the
#            core criterion but fail strict are flagged additionally.
#
# An utterance is FLAGGED (sent to manual listening) when either
# criterion fails. On the paper's test split the core criterion flags
# 1,879 Hi Xiaowen and 3,564 Nihao Wenwen positives; strict adds 55.
#
# Resume-aware: rerunning skips utterances already in the output CSV.
#
# Output columns:
#   utt_id, kw, text, match, reason, strict_match, strict_reason,
#   flagged, sec

import argparse
import csv
import json
import os
import time
import unicodedata


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return "".join(ch for ch in s if ch.isalnum())


# wake-word cores, incl. common homophone transcriptions
CORES = {
    "kw0": ["小问", "小問", "xiaowen", "嗨小", "hixiao", "haixiao",
            "小温", "小溫", "小文", "小闻"],
    "kw1": ["问问", "問問", "wenwen", "你好问", "你好問",
            "温温", "溫溫", "文文", "闻闻"],
}

# exact acceptable transcriptions (normalized) for the strict criterion
ACCEPT = {
    "kw0": {"嗨小问", "嗨小問", "小问", "小問", "嗨小温", "嗨小溫",
            "嗨小文", "嗨小闻", "hixiaowen", "haixiaowen", "xiaowen"},
    "kw1": {"你好问问", "你好問問", "问问", "問問", "你好问", "你好問",
            "你好温温", "你好溫溫", "你好文文", "你好闻闻",
            "nihaowenwen", "wenwen", "你好问吗", "你好問嗎"},
}

PROMPT = "你好问问。嗨小问。"
KW_OF_ID = {0: "kw0", 1: "kw1"}


def core_verdict(text, kw, maxlen=8):
    t = norm(text)
    if not t:
        return 0, "empty"
    if not any(norm(c) in t for c in CORES[kw]):
        return 0, "no_core"
    if len(t) > maxlen:
        return 0, "core_in_long"
    return 1, "clean"


def strict_verdict(text, kw):
    t = norm(text)
    if not t:
        return 0, "empty"
    if t in ACCEPT[kw]:
        return 1, "exact"
    for a in ACCEPT[kw]:
        if a in t and len(t) <= len(a) + 1:
            return 1, "near_exact"
    return 0, "other_speech"


def main():
    ap = argparse.ArgumentParser(
        description="whisper-based flagging of Mobvoi positives")
    ap.add_argument("--positives_json", required=True,
                    help="SLR87 metadata json for the split "
                         "(e.g. p_test.json or p_dev.json)")
    ap.add_argument("--wav_dir", required=True,
                    help="directory with <utt_id>.wav files")
    ap.add_argument("--out", required=True,
                    help="output CSV (created/resumed)")
    ap.add_argument("--model", default="base",
                    help="faster-whisper model size (default: base; the "
                         "audit deliberately used the small base model, as "
                         "larger models tended to normalize corrupted "
                         "speech toward the prompted keyword)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute_type", default="int8")
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    done = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig") as f:
            done = {r["utt_id"] for r in csv.DictReader(f)}

    todo = []
    for e in json.load(open(args.positives_json, encoding="utf-8")):
        kw = KW_OF_ID.get(e.get("keyword_id"))
        if kw and e["utt_id"] not in done:
            todo.append((e["utt_id"], kw))
    print(f"to transcribe: {len(todo)} (already done: {len(done)})")

    model = WhisperModel(args.model, device=args.device,
                         compute_type=args.compute_type)

    new_file = not os.path.exists(args.out)
    fout = open(args.out, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(fout)
    if new_file:
        w.writerow(["utt_id", "kw", "text", "match", "reason",
                    "strict_match", "strict_reason", "flagged", "sec"])
        fout.flush()

    t0 = time.time()
    for i, (uid, kw) in enumerate(todo, 1):
        p = os.path.join(args.wav_dir, uid + ".wav")
        t1 = time.time()
        try:
            segs, _ = model.transcribe(
                p, language="zh", beam_size=1, initial_prompt=PROMPT,
                condition_on_previous_text=False)
            text = "".join(s.text for s in segs).strip()
        except Exception as e:
            text = f"<ERROR {e}>"
        m, reason = core_verdict(text, kw)
        sm, sreason = strict_verdict(text, kw)
        flagged = int(m == 0 or sm == 0)
        w.writerow([uid, kw, text, m, reason, sm, sreason, flagged,
                    f"{time.time() - t1:.1f}"])
        fout.flush()
        if i % 50 == 0:
            el = time.time() - t0
            print(f"  {i}/{len(todo)}  ({el / 60:.0f} min, "
                  f"eta {el / i * (len(todo) - i) / 60:.0f} min)",
                  flush=True)
    fout.close()

    # summary
    rows = list(csv.DictReader(open(args.out, encoding="utf-8-sig")))
    import collections
    tab = collections.defaultdict(lambda: [0, 0])
    add = collections.Counter()
    for r in rows:
        tab[r["kw"]][int(r["flagged"])] += 1
        if r["match"] == "1" and r["strict_match"] == "0":
            add[r["kw"]] += 1
    print("\n=== flagging summary (flagged -> manual listening) ===")
    for kw in sorted(tab):
        f1, f0 = tab[kw][1], tab[kw][0]
        n = f0 + f1
        print(f"  {kw}: flagged {f1}/{n} ({100 * f1 / n:.1f}%), "
              f"of which strict-only: {add.get(kw, 0)}")


if __name__ == "__main__":
    main()
