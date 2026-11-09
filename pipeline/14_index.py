"""Step 14 – event hub: one page with everything to share, for the whole life of an event.

  14_index.py     sraz-XX/index.html + sraz-XX/<talk>/out/index.html

Works from the event dir or from any talk dir (run.sh 11, 12 and 13 call it at
the end). Only reads, so it can run at any time; a missing output just isn't
listed yet.

Before the event the page leads with the promo images and texts. Afterwards the
promo collapses and the published outputs of each talk (YouTube, social.html,
article, reels) are what stands out.

Promo texts are composed from event.md and talk.md. To change them, write the
optional editorial file sraz-XX/promo.json (a value replaces the whole text):
  {"hashtags": "#php #pehapkari", "event": "…", "talks": {"votocek": "…"}}
"""
import datetime
import json
import os
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import quote

from common import LECTURE, log

brand = __import__("11_brand")

EVENT_DIR = LECTURE if (LECTURE / "event.md").exists() else LECTURE.parent
DEFAULT_TAGS = "#php #pehapkari"

EVENT_IMAGES = [("instagram-event", "Instagram 1080×1080"), ("event-card", "Karta akce 1920×1080")]
TALK_IMAGES = [("instagram-speaker", "Instagram 1080×1080"), ("speaker-card", "Karta řečníka 1920×1080"),
               ("youtube-thumbnail-a", "YouTube náhled A"), ("youtube-thumbnail-b", "YouTube náhled B")]
OUTPUTS = [("social.html", "Příspěvky po přednášce"), ("youtube.html", "Popis a kapitoly pro YouTube"),
           ("article.html", "Článek na web"), ("article.md", "Článek (md)"), ("lecture.fcpxml", "Střih pro DaVinci")]

PAGE = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bar: #4F5B93; --panel: #C5CFFF; --ink: #141F51; --bg: #f6f6fa; --card: #fff; --muted: #666; }}
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 16px; background: var(--bg); color: var(--ink); }}
h1 {{ font-size: 1.5rem; margin-bottom: .2rem; }}
h2 {{ font-size: 1.15rem; margin: 2.5rem 0 1rem; color: var(--bar); }}
h3 {{ font-size: 1.2rem; margin: 0; }}
a {{ color: var(--bar); }}
.meta, .bio, .note {{ color: var(--muted); margin: 0 0 .75rem; }}
.card {{ background: var(--card); border: 1px solid #ddd; border-left: 4px solid var(--bar); padding: 16px; margin-bottom: 16px; }}
.head {{ margin-bottom: 12px; }}
.images {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin-bottom: 12px; }}
figure {{ margin: 0; }}
figure img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: contain; display: block; background: var(--bg); }}
figcaption {{ font-size: .85rem; color: var(--muted); }}
pre {{ white-space: pre-wrap; background: var(--bg); padding: .8rem 1rem; font: inherit; margin: 0 0 .5rem; }}
button {{ background: var(--bar); color: #fff; border: 0; padding: .5rem 1rem; font: inherit; cursor: pointer; }}
.links {{ margin: .75rem 0 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: .25rem 1.25rem; }}
summary {{ cursor: pointer; color: var(--bar); margin-bottom: .75rem; }}
</style></head><body>
{body}
<script>
function copy(btn, id) {{
  const text = document.getElementById(id).innerText;
  const done = () => {{ btn.textContent = 'Zkopírováno ✓'; setTimeout(() => btn.textContent = 'Kopírovat text', 2000); }};
  const fallback = () => {{
    const area = document.createElement('textarea');
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand('copy');
    area.remove();
    done();
  }};
  navigator.clipboard ? navigator.clipboard.writeText(text).then(done, fallback) : fallback();
}}
</script>
</body></html>
"""


@dataclass
class Talk:
    slug: str
    dir: Path
    fm: dict
    abstract: str


def load_talks() -> list[Talk]:
    talks = []
    for md in EVENT_DIR.glob("*/talk.md"):
        fm, body = brand.front_matter(md)
        talks.append(Talk(md.parent.name, md.parent, fm, body))
    return sorted(talks, key=lambda t: (t.fm.get("order", 99), t.slug))


# ------------------------------------------------------------------ texts
def event_title(ev: dict) -> str:
    name = ev.get("name", "pražský sraz přátel PHP")
    return f"{ev['number']}. {name}" if ev.get("number") else name


def event_when(ev: dict) -> str:
    return " ".join(x for x in brand.event_when_where(ev) if x)


def event_text(ev: dict, talks: list[Talk], tags: str) -> str:
    program = "\n".join(f"{n}. {t.fm['speaker']}: {t.fm['title']}" for n, t in enumerate(talks, 1))
    partner = (ev.get("partner") or {}).get("name")
    return "\n\n".join(x for x in [
        f"{event_title(ev)}\n{event_when(ev)}", f"Program:\n{program}",
        "\n".join(x for x in [f"Partner srazu: {partner}" if partner else "", ev.get("url", "")] if x), tags] if x)


def talk_text(ev: dict, t: Talk, tags: str) -> str:
    who = f"{t.fm['speaker']}: {t.fm['title']}"
    if t.fm.get("bio"):
        who += f"\n{t.fm['bio']}"
    where = "\n".join(x for x in [event_title(ev), event_when(ev), ev.get("url", "")] if x)
    return "\n\n".join(x for x in [who, t.abstract, where, tags] if x)


# ------------------------------------------------------------------ html parts
def href(path: Path, base: Path) -> str:
    return escape(quote(os.path.relpath(path, base)), quote=True)


def figures(images: list[tuple[Path, str]], base: Path) -> str:
    figs = "".join(f'<figure><a href="{href(p, base)}" target="_blank">'
                   f'<img src="{href(p, base)}" alt="{escape(label, quote=True)}" loading="lazy"></a>'
                   f'<figcaption>{escape(label)}</figcaption></figure>' for p, label in images)
    return f'<div class="images">{figs}</div>' if figs else ""


def text_box(id_: str, text: str) -> str:
    return (f'<pre id="{id_}">{escape(text)}</pre>'
            f"<button onclick=\"copy(this, '{id_}')\">Kopírovat text</button>")


def talk_images(t: Talk) -> list[tuple[Path, str]]:
    return [(p, label) for name, label in TALK_IMAGES if (p := t.dir / "out" / "brand" / f"{name}.png").exists()]


def talk_links(t: Talk, base: Path, detail: str | None = None) -> str:
    items = [f'<a href="{detail}">Detail řečníka</a>'] if detail else []
    if t.fm.get("youtube"):
        items.append(f'<a href="{escape(t.fm["youtube"], quote=True)}">Video na YouTube</a>')
    for name, label in OUTPUTS:
        if (t.dir / "out" / name).exists():
            items.append(f'<a href="{href(t.dir / "out" / name, base)}">{label}</a>')
    if detail is None and (t.dir / "out" / "edit_plan.html").exists():   # editorial, detail page only
        items.append(f'<a href="{href(t.dir / "out" / "edit_plan.html", base)}">Návrh střihu</a>')
    if detail is None and (t.dir / "out" / "highlights.html").exists():
        items.append(f'<a href="{href(t.dir / "out" / "highlights.html", base)}">Pasáže na reels a teaser</a>')
    reels = sorted((t.dir / "out" / "reels").glob("*.mp4"))
    # the detail page lists the reels one by one, the hub only points to the folder
    if reels and detail:
        items.append(f'<a href="{href(t.dir / "out" / "reels", base)}/">Reels ({len(reels)})</a>')
    return f'<ul class="links">{"".join(f"<li>{i}</li>" for i in items)}</ul>' if items else ""


def promo(content: str, past: bool, label: str) -> str:
    return f"<details><summary>{label}</summary>{content}</details>" if past and content else content


def talk_card(ev: dict, t: Talk, text: str, past: bool, base: Path, hub: bool) -> str:
    images = talk_images(t)
    missing = "" if images else (f'<p class="note">Upoutávky zatím nejsou. Vyrobí je '
                                 f'<code>run.sh {t.dir.parent.name}/{t.slug} brand</code>.</p>')
    content = figures(images, base) + missing + text_box(f"text-{t.slug}", text)
    bio = f'<p class="bio">{escape(t.fm["bio"])}</p>' if t.fm.get("bio") else ""
    links = talk_links(t, base, href(t.dir / "out" / "index.html", base) if hub else None)
    title = escape(f"{t.fm.get('order', '')}. {t.fm['speaker']}: {t.fm['title']}")
    return (f'<section class="card"><div class="head"><h3>{title}</h3>{bio}</div>'
            f"{promo(content, past, 'Upoutávka před akcí')}{links}</section>")


def talk_page(ev: dict, t: Talk, text: str, past: bool):
    base = t.dir / "out"
    reels = sorted((base / "reels").glob("*.mp4"))
    videos = "".join(f'<li><a href="{href(p, base)}">{escape(p.stem)}</a></li>' for p in reels)
    body = (f'<p class="meta"><a href="{href(EVENT_DIR / "index.html", base)}">← {escape(event_title(ev))}</a></p>'
            f"<h1>{escape(t.fm['speaker'])}</h1><p class=\"meta\">{escape(t.fm['title'])}</p>"
            + talk_card(ev, t, text, past, base, hub=False)
            + (f"<h2>Reels ({len(reels)})</h2><ul>{videos}</ul>" if reels else ""))
    base.mkdir(exist_ok=True)
    (base / "index.html").write_text(PAGE.format(title=escape(f"{t.fm['speaker']} – {event_title(ev)}"), body=body))


def hub_page(ev: dict, talks: list[Talk], texts: dict, invite: str, past: bool):
    images = []
    for name, label in EVENT_IMAGES:
        # the event cards are the same for every talk, the first rendered one will do
        found = next((p for t in talks if (p := t.dir / "out" / "brand" / f"{name}.png").exists()), None)
        if found:
            images.append((found, label))
    event_card = f'<section class="card">{figures(images, EVENT_DIR)}{text_box("text-event", invite)}</section>'
    url = ev.get("url", "")
    site = f' · <a href="https://{escape(url, quote=True)}">{escape(url)}</a>' if url else ""
    cards = "".join(talk_card(ev, t, texts[t.slug], past, EVENT_DIR, hub=True) for t in talks)
    invitation = promo(event_card, past, "Pozvánka před akcí")
    body = (f"<h1>{escape(event_title(ev))}</h1><p class=\"meta\">{escape(event_when(ev))}{site}</p>"
            f"<h2>Pozvánka na akci</h2>{invitation}<h2>Přednášky ({len(talks)})</h2>{cards}")
    (EVENT_DIR / "index.html").write_text(PAGE.format(title=escape(event_title(ev)), body=body))


def main():
    ev, _ = brand.front_matter(EVENT_DIR / "event.md")
    spec = EVENT_DIR / "promo.json"
    overrides = json.loads(spec.read_text()) if spec.exists() else {}
    tags = overrides.get("hashtags", DEFAULT_TAGS)
    talks = load_talks()
    date = ev.get("date")
    past = isinstance(date, datetime.date) and date < datetime.date.today()
    invite = overrides.get("event") or event_text(ev, talks, tags)
    texts = {t.slug: overrides.get("talks", {}).get(t.slug) or talk_text(ev, t, tags) for t in talks}
    for t in talks:
        talk_page(ev, t, texts[t.slug], past)
    hub_page(ev, talks, texts, invite, past)
    log(f"wrote {EVENT_DIR.name}/index.html + {len(talks)} talk pages")


if __name__ == "__main__":
    main()
