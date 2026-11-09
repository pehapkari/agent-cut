"""Step 7 – reels candidates.

  07_highlights.py sentences   dump numbered sentences with times → work/sentences.md
                               (reading aid for picking passages)
  07_highlights.py             validate work/highlights.json → work/highlights.md
                               + out/highlights.html (reels + teaser, for people)

work/highlights.json is the editorial pick (written by a human or by Claude
after reading the transcript): list of
  {"id", "slug", "start", "end", "hook", "why", "title", "caption"}
start/end are snapped to word boundaries; 30–60 s is enforced.
"""
import json
from pathlib import Path
import re
import sys
from html import escape

from common import LECTURE, OUT, WORK, config, load_json, log, save_json, tc

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
    # t0/t1 may already include LEAD/TAIL from a previous run → compare without
    # them, so that snapping is idempotent
    first = min(ws, key=lambda w: abs(w["s"] - (t0 + LEAD)))
    last = min(ws, key=lambda w: abs(w["e"] - (t1 - TAIL)))
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
    write_html(hl)
    for p in problems:
        log("WARNING " + p)


HTML = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pasáže – {speaker}</title>
<style>
:root {{ --bar: #4F5B93; --ink: #141F51; --bg: #f6f6fa; --card: #fff; --muted: #666; --key: #fff2a8; --ok: #1e7b3a; }}
body {{ font: 16px/1.55 system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 16px; background: var(--bg); color: var(--ink); }}
h1 {{ font-size: 1.5rem; margin: .3rem 0 .2rem; }}
h2 {{ font-size: 1.15rem; margin: 2.2rem 0 .8rem; color: var(--bar); }}
h3 {{ font-size: 1.1rem; margin: 0; }}
a {{ color: var(--bar); }}
.meta {{ color: var(--muted); margin: 0 0 .75rem; }}
.card {{ background: var(--card); border: 1px solid #ddd; border-left: 4px solid var(--bar); padding: 14px 16px; margin-bottom: 14px; }}
.card.selected {{ border-left-color: var(--ok); }}
.card header {{ display: flex; flex-wrap: wrap; gap: .3rem 1rem; align-items: baseline; margin-bottom: .5rem; }}
.time {{ font-variant-numeric: tabular-nums; color: var(--muted); }}
.badge {{ font-size: .85rem; padding: 0 .5rem; border-radius: 3px; background: var(--bg); }}
.selected .badge {{ color: var(--ok); }}
.hook {{ font-size: 1.1rem; font-weight: 600; margin: 0 0 .4rem; }}
.why {{ color: var(--muted); margin: 0 0 .6rem; }}
mark {{ background: var(--key); }}
pre {{ white-space: pre-wrap; background: var(--bg); padding: .6rem .8rem; font: inherit; margin: 0 0 .4rem; }}
button {{ background: var(--bar); color: #fff; border: 0; padding: .35rem .9rem; font: inherit; cursor: pointer; }}
summary {{ cursor: pointer; color: var(--bar); margin: .6rem 0 .3rem; }}
ol.teaser {{ background: var(--card); border: 1px solid #ddd; border-left: 4px solid var(--bar); padding: 12px 16px 12px 2.5rem; }}
ol.teaser li {{ margin: .3rem 0; }}
video {{ max-width: 270px; display: block; margin-top: .5rem; }}
video.wide {{ max-width: 100%; width: 720px; }}
</style></head><body>
<p class="meta"><a href="index.html">← {speaker}</a></p>
<h1>Pasáže na reels a teaser</h1>
<p class="meta">{title} · časy v hlavním audiu (stejné jako v přepisu a návrhu střihu)</p>
{body}
<script>
function copy(btn, id) {{
  const text = document.getElementById(id).innerText;
  navigator.clipboard.writeText(text).then(() => {{ btn.textContent = 'Zkopírováno ✓'; setTimeout(() => btn.textContent = 'Kopírovat popisek', 2000); }});
}}
</script>
</body></html>
"""


def write_html(hl: list[dict]):
    """out/highlights.html – reel candidates (+ teaser lines) for people to read and pick."""
    cfg = config()

    def marked(text: str, keys: list[str]) -> str:
        out = escape(text)
        for k in sorted({k for k in keys if k}, key=len, reverse=True):
            out = re.sub(rf"(?<![\w>])({re.escape(escape(k))})(?![\w<])", r"<mark>\1</mark>", out)
        return out

    cards = []
    for n, h in enumerate(hl, 1):
        sel = h.get("selected")
        video = ""
        if h.get("render", {}).get("file") and (LECTURE / h["render"]["file"]).exists():
            src = Path(h["render"]["file"]).relative_to("out").as_posix()
            video = f'<video controls preload="metadata" src="{escape(src, quote=True)}"></video>'
        elif (OUT / "reels" / "preview" / f"H{n}_{h['slug']}.mp4").exists():
            video = (f'<p class="meta">Náhled (poloviční rozlišení, titulky bez ručních oprav)</p>'
                     f'<video controls preload="metadata" src="reels/preview/H{n}_{escape(h["slug"], quote=True)}.mp4"></video>')
        cid = f"cap-{h['id']}"
        cards.append(
            f'<article class="card{" selected" if sel else ""}" id="{escape(h["id"])}"><header>'
            f'<h3>{n}. {escape(h["title"])}</h3>'
            f'<span class="time">{tc(h["start"])} – {tc(h["end"])} · {h["end"] - h["start"]:.0f} s</span>'
            f'<span class="badge">{"vybráno" if sel else "kandidát"} · {escape(h["id"])}</span></header>'
            f'<p class="hook">„{escape(h["hook"])}“</p><p class="why">{escape(h["why"])}</p>'
            f'<pre id="{cid}">{escape(h.get("caption", ""))}</pre>'
            f'<button onclick="copy(this, \'{cid}\')">Kopírovat popisek</button>'
            f'<details><summary>Přepis pasáže (klíčová slova žlutě)</summary>'
            f'<p>{marked(h.get("text", ""), h.get("keywords", []))}</p></details>{video}</article>')
    body = ["<h2>Kandidáti na reels (" + str(len(hl)) + ")</h2>", "".join(cards)]
    tp = WORK / "teaser.json"
    if tp.exists():
        lines = json.loads(tp.read_text())
        body.append(f"<h2>Teaser před hlavním videem ({len(lines)} vět, "
                    f"{sum(t['end'] - t['start'] for t in lines):.0f} s)</h2><ol class=\"teaser\">"
                    + "".join(f'<li><span class="time">{tc(t["start"])} · {t["end"] - t["start"]:.1f} s</span> '
                              f'– {escape(t["text"])}</li>' for t in lines) + "</ol>")
        if (OUT / "opening.mp4").exists():
            body.append('<p class="meta">Začátek videa tak, jak ho uvidí divák: teaser a znělka '
                        '(náhled, plná verze je work/brand/teaser.mp4)</p>'
                        '<video class="wide" controls preload="metadata" src="opening.mp4"></video>')
    OUT.mkdir(exist_ok=True)
    (OUT / "highlights.html").write_text(HTML.format(speaker=escape(cfg.get("speaker", "")),
                                                     title=escape(cfg.get("title", "")), body="".join(body)))
    log("wrote out/highlights.html")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sentences":
        dump_sentences()
    else:
        build()
