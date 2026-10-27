"""Step 7 – reels candidates.

  07_highlights.py sentences   dump numbered sentences with times → work/sentences.md
                               (reading aid for picking passages)
  07_highlights.py             validate work/highlights.json → work/highlights.md

work/highlights.json is the editorial pick (written by a human or by Claude
after reading the transcript): list of
  {"id", "slug", "start", "end", "hook", "why", "title", "caption"}
start/end are snapped to word boundaries; 30–60 s is enforced.
"""
import re
import sys

from common import WORK, load_json, log, save_json, tc

MIN_LEN, MAX_LEN = 30.0, 60.0
LEAD, TAIL = 0.15, 0.35        # breathing room around first/last word


def all_words() -> list[dict]:
    tr = load_json("transcript.json")
    return [w for s in tr["segments"] for w in s["words"] if w["w"].strip()]


def sentences(ws: list[dict]) -> list[dict]:
    out, cur = [], []
    for w in ws:
        cur.append(w)
        if re.search(r"[.?!…]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"start": s[0]["s"], "end": s[-1]["e"], "text": " ".join(w["w"] for w in s)} for s in out]


def dump_sentences():
    ss = sentences(all_words())
    lines = ["# Věty s časy", ""]
    for i, s in enumerate(ss):
        lines.append(f"`{i:04d}` **{tc(s['start'], ms=True)}–{tc(s['end'], ms=True)}** {s['text']}")
    (WORK / "sentences.md").write_text("\n".join(lines) + "\n")
    log(f"wrote work/sentences.md ({len(ss)} sentences)")


def snap(ws, t0, t1):
    first = min(ws, key=lambda w: abs(w["s"] - t0))
    last = min(ws, key=lambda w: abs(w["e"] - t1))
    inside = [w for w in ws if first["s"] <= w["s"] <= last["s"]]
    return first["s"] - LEAD, last["e"] + TAIL, " ".join(w["w"] for w in inside)


def build():
    ws = all_words()
    hl = load_json("highlights.json")
    problems = []
    for h in hl:
        h["start"], h["end"], h["text"] = snap(ws, h["start"], h["end"])
        h["start"], h["end"] = round(h["start"], 3), round(h["end"], 3)
        d = h["end"] - h["start"]
        if not MIN_LEN <= d <= MAX_LEN:
            problems.append(f"{h['id']}: length {d:.1f}s outside {MIN_LEN:.0f}–{MAX_LEN:.0f}s")
    save_json("highlights.json", hl)
    lines = ["# Kandidáti na reels", "",
             "Časy = hlavní audio. Vyber čísla (např. *1, 3, 4*), případně uprav titulek/popisek.", ""]
    for n, h in enumerate(hl, 1):
        lines += [
            f"## {n}. {h['title']}",
            "",
            f"- **Čas:** {tc(h['start'])} – {tc(h['end'])} ({h['end'] - h['start']:.0f} s)",
            f"- **Hook:** „{h['hook']}“",
            f"- **Proč funguje:** {h['why']}",
            f"- **Titulek na videu:** {h['title']}",
            f"- **Popisek:** {h['caption']}",
            "",
            "<details><summary>Přepis pasáže</summary>",
            "",
            h["text"],
            "",
            "</details>",
            "",
        ]
    (WORK / "highlights.md").write_text("\n".join(lines))
    log(f"wrote work/highlights.md ({len(hl)} candidates)")
    for p in problems:
        log("WARNING " + p)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sentences":
        dump_sentences()
    else:
        build()
