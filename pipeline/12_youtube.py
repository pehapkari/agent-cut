"""Step 12 – YouTube description with chapters → out/youtube.md.

  12_youtube.py sentences   sentences that survive the cut, timed in the final
                            video (intro + approved cuts) → work/sentences_video.md
  12_youtube.py             work/youtube.json → out/youtube.md

work/youtube.json is the editorial part (written by a human or by Claude after
reading the transcript):
  {"description": "…", "chapters": [{"start": 123.4, "title": "…"}, …], "footer": "…"}
Chapter starts are main-audio seconds (same as transcript / highlights); they
are mapped onto the timeline of out/lecture.fcpxml, so the intro in front and
every approved cut are accounted for. Teaser + intro get their own 0:00 chapter.
"""
import subprocess
import sys

from html import escape

from common import OUT, WORK, config, load_json, log, save_json, tc

edit = __import__("06_edit")
hl = __import__("07_highlights")

MIN_CHAPTER = 10  # s – YouTube ignores chapters shorter than this

HTML = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} – YouTube popisek</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 16px; background: #f6f6fa; color: #1d1d2b; }}
h1 {{ font-size: 1.4rem; margin-bottom: .2rem; }}
p.meta {{ color: #666; margin-top: 0; }}
pre {{ white-space: pre-wrap; background: #fff; border: 1px solid #ddd; border-left: 4px solid #4F5B93; padding: 1rem; font: inherit; }}
button {{ background: #4F5B93; color: #fff; border: 0; padding: .6rem 1.2rem; font: inherit; cursor: pointer; }}
</style></head><body>
<h1>{title}</h1>
<p class="meta">Popisek pro YouTube · délka videa {length} (včetně intra)</p>
<button onclick="navigator.clipboard.writeText(document.getElementById('t').innerText).then(() => this.textContent = 'Zkopírováno ✓')">Kopírovat popisek</button>
<pre id="t">{text}</pre>
</body></html>
"""


def timeline():
    """main-audio time → seconds in the exported video (as built by 06_edit.fcpxml)."""
    offs = load_json("offsets.json")
    approved = [c for c in load_json("edit_plan.json")["cuts"] if c["status"] == "approved"]
    lead = [b for b in (edit.bumper("teaser"), edit.bumper("intro")) if b]
    tl = sum(b[1] for b in lead)
    segs = []  # (main_f0, main_f1, timeline_f0)
    for a0, a1, _ in edit.keep_ranges(approved, offs["main_duration"]):
        f0, f1 = edit.frames(a0), edit.frames(a1)
        segs.append((f0, f1, tl))
        tl += f1 - f0

    def to_video(t: float) -> float | None:
        """None when t falls inside a cut."""
        f = edit.frames(t)
        for f0, f1, v0 in segs:
            if f0 <= f < f1:
                return (v0 + f - f0) / edit.FPS
        return None

    intro_s = segs[0][2] / edit.FPS if segs else 0.0
    outro = edit.bumper("outro")
    return to_video, intro_s, (tl + (outro[1] if outro else 0)) / edit.FPS


def yt(sec: float) -> str:
    """YouTube timestamp: M:SS or H:MM:SS."""
    s = int(sec)
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def dump_sentences():
    to_video, intro_s, total = timeline()
    lines = ["# Věty v časech výsledného videa", "",
             f"Intro 0:00–{yt(intro_s)}, délka videa {tc(total)}. Vlevo čas ve videu, v závorce hlavní audio "
             "(do work/youtube.json se píše čas hlavního audia).", ""]
    n = 0
    for s in hl.sentences(hl.all_words()):
        v = to_video(s["start"])
        if v is None:
            continue
        lines.append(f"**{yt(v)}** ({s['start']:.2f}) {s['text']}")
        n += 1
    (WORK / "sentences_video.md").write_text("\n".join(lines) + "\n")
    log(f"wrote work/sentences_video.md ({n} sentences)")


def build():
    to_video, intro_s, total = timeline()
    data = load_json("youtube.json")
    rows, problems = [(0.0, "Ukázka" if edit.bumper("teaser") else "Intro")] if intro_s else [], []
    for c in sorted(data["chapters"], key=lambda c: c["start"]):
        v = to_video(c["start"])
        if v is None:
            problems.append(f"{c['title']}: {tc(c['start'])} is inside a cut")
            continue
        c["video"] = round(v, 2)
        rows.append((v, c["title"]))
    if not rows or rows[0][0] > 0:
        problems.append("first chapter must start at 0:00")
    for (a, t), (b, _) in zip(rows, rows[1:] + [(total, "")]):
        if b - a < MIN_CHAPTER:
            problems.append(f"{t}: only {b - a:.0f} s (YouTube needs ≥ {MIN_CHAPTER} s)")
    if len(rows) < 3:
        problems.append("YouTube needs at least 3 chapters")
    save_json("youtube.json", data)

    text = [data["description"].strip(), "", "Kapitoly:"]
    text += [f"{yt(v)} {t}" for v, t in rows]
    if data.get("footer"):
        text += ["", data["footer"].strip()]
    OUT.mkdir(exist_ok=True)
    (OUT / "youtube.md").write_text("\n".join(text) + "\n")
    (OUT / "youtube.html").write_text(HTML.format(title=escape(config().get("title") or "YouTube"),
                                                  length=tc(total), text=escape("\n".join(text))))
    log(f"wrote out/youtube.md + out/youtube.html ({len(rows)} chapters, video {tc(total)})")
    for p in problems:
        log(f"WARNING {p}")


if __name__ == "__main__":
    dump_sentences() if sys.argv[1:] == ["sentences"] else build()
