"""Step 13 – texts for publishing the talk: social posts and a web article.

  13_publish.py social    work/social.json → out/social.html + out/social/NN_slug.png
  13_publish.py article   work/article.json → out/article.md
  13_publish.py social-text   only the texts (keeps the rendered images)
  13_publish.py           both

Needs the YouTube link in talk.md (`youtube:`), the edit (step 6, for times in
the published video) and step 11 (brand props, for the post images).

work/social.json is the editorial part (written by a human or by Claude):
  {"claim": "…", "summary": "…", "hashtags": "#php …",
   "posts": [{"id": "H4", "quote": "…", "text": "…", "frame": 1151.2}, …]}
claim + summary = the general post for the whole talk. Every post is one point
of the talk, taken from a highlight (work/highlights.json, the reel hooks):
quote goes on the image (default: the highlight's hook), text is the post
(default: its caption), frame picks the speaker's frame for the image
(main-audio time; default: the clearest face in the first seconds).

work/article.json – the talk retold for the web, in the voice of the elephant
(agent-cut/slon.md):
  {"perex": "…", "sections": [{"start": 168.6, "title": "…", "text": "…"}, …],
   "takeaways": ["…", …]}
Times are main-audio seconds (like youtube.json); links point to the same
moment in the YouTube video.
"""
import json
import re
import shutil
import sys
from html import escape

import cv2
import yaml

from common import LECTURE, OUT, TOOLS, WORK, load_json, log, run, src

brand = __import__("11_brand")
reels = __import__("08_reels")
youtube = __import__("12_youtube")

FRAME_TRIES = [0.4, 0.9, 1.4, 1.9, 2.4, 2.9, 3.4]  # s after the start of a point

HTML = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} – sociální sítě</title>
<style>
:root {{ --bar: #4F5B93; --panel: #C5CFFF; --ink: #141F51; --bg: #f6f6fa; --card: #fff; --muted: #666; }}
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 16px; background: var(--bg); color: var(--ink); }}
h1 {{ font-size: 1.5rem; margin-bottom: .2rem; }}
h2 {{ font-size: 1.15rem; margin: 2.5rem 0 1rem; color: var(--bar); }}
p.meta {{ color: var(--muted); margin-top: 0; }}
a {{ color: var(--bar); }}
.post {{ display: grid; grid-template-columns: 320px 1fr; gap: 20px; background: var(--card); border: 1px solid #ddd;
         border-left: 4px solid var(--bar); padding: 16px; margin-bottom: 16px; }}
.post.main {{ grid-template-columns: 320px 1fr; }}
.media img, .media video {{ width: 100%; display: block; margin-bottom: 8px; }}
.media video {{ max-height: 420px; background: #000; }}
.claim {{ font-size: 1.35rem; font-weight: 700; margin: 0 0 .5rem; }}
.quote {{ font-weight: 600; margin: 0 0 .5rem; }}
pre {{ white-space: pre-wrap; background: var(--bg); padding: .8rem 1rem; font: inherit; margin: .5rem 0; }}
button {{ background: var(--bar); color: #fff; border: 0; padding: .5rem 1rem; font: inherit; cursor: pointer; }}
.files {{ font-size: .9rem; color: var(--muted); }}
@media (max-width: 720px) {{ .post, .post.main {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>{title}</h1>
<p class="meta">{speaker} · {event} · <a href="{url}">YouTube</a></p>
<h2>Hlavní příspěvek – celá přednáška</h2>
{main}
<h2>Pointy přednášky ({n}) – obrázek nebo reels + text</h2>
{posts}
<script>
function copy(btn, id) {{
  navigator.clipboard.writeText(document.getElementById(id).innerText).then(() => btn.textContent = 'Zkopírováno ✓');
}}
</script>
</body></html>
"""

POST = """<div class="post{cls}">
<div class="media">{media}</div>
<div>{head}
<pre id="{id}">{text}</pre>
<button onclick="copy(this, '{id}')">Kopírovat text</button>
<p class="files">{files}</p>
</div></div>
"""


# ------------------------------------------------------------------ shared data
def talk() -> dict:
    fm, abstract = brand.front_matter(LECTURE / "talk.md")
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/)([\w-]{11})", str(fm.get("youtube", "")))
    if not m:
        raise SystemExit("talk.md: add `youtube: https://www.youtube.com/watch?v=…` to the front matter")
    event, _ = brand.front_matter(LECTURE.parent / "event.md")
    return {**fm, "abstract": abstract, "yt_id": m.group(1), "event": event}


def link(t: dict, sec: float | None) -> str:
    return f"https://youtu.be/{t['yt_id']}" + (f"?t={int(sec)}" if sec else "")


def event_name(t: dict) -> str:
    e = t["event"]
    return f"{e['number']}. {e.get('name', 'pražský sraz přátel PHP')}" if e.get("number") else e.get("name", "")


# ------------------------------------------------------------------ social
def best_frame(main_t: float, tries: list[float], dst) -> dict | None:
    """Camera frame with the clearest face around main_t → dst, as a brand Photo."""
    cam = WORK / "social" / "frames"
    cam.mkdir(parents=True, exist_ok=True)
    offs = load_json("offsets.json")["camera"]
    det, best = None, None
    for i, dt in enumerate(tries):
        t = main_t + dt
        f = cam / f"{i}.png"
        run(["ffmpeg", "-ss", f"{t - reels.offset_at(offs, t):.3f}", "-i", str(src("camera")),
             "-frames:v", "1", str(f)])
        img = cv2.imread(str(f))
        h, w = img.shape[:2]
        if det is None:
            det = cv2.FaceDetectorYN.create(str(TOOLS / "models" / "face_detection_yunet_2023mar.onnx"), "",
                                            (w, h), 0.6)
        _, faces = det.detect(img)
        if faces is None:
            continue
        x, y, fw, fh, *_, score = max(faces, key=lambda r: r[2] * r[3])
        if not best or score > best[0]:
            best = (score, f, {"x": x / w, "y": y / h, "w": fw / w, "h": fh / h}, w, h)
    if not best:
        return None
    _, f, face, w, h = best
    shutil.copy(f, dst)
    return {"file": f"quotes/{dst.name}", "w": w, "h": h,
            "face": {k: round(float(v), 4) for k, v in face.items()}}


def post_images(posts: list[dict]):
    """Render instagram-quote cards (Remotion, needs work/brand from step 11)."""
    props = json.loads((brand.BRAND / "props.json").read_text())
    (brand.PUBLIC / "quotes").mkdir(parents=True, exist_ok=True)
    props["metrics"] |= brand.metrics([f"„{p['quote']}“" for p in posts] + [" · "])
    jobs = []
    for p in posts:
        photo = best_frame(p["frame"], [0.0] if p["frame_set"] else FRAME_TRIES,
                           brand.PUBLIC / "quotes" / f"{p['name']}.png")
        f = brand.BRAND / f"quote-{p['name']}.json"
        f.write_text(json.dumps({**props, "quote": {"text": p["quote"], "photo": photo}}, ensure_ascii=False))
        jobs.append((f, OUT / "social" / f"{p['name']}.png"))
    serve = brand.bundle()
    for f, dst in jobs:
        brand.npx("still", serve, "instagram-quote", str(dst), f"--props={f}", "--image-format=png")


def social(images: bool = True):
    t = talk()
    data = load_json("social.json")
    hl = {h["id"]: h for h in load_json("highlights.json")}
    to_video, _, total = youtube.timeline()
    tags = data.get("hashtags", "").strip()
    posts = []
    for n, p in enumerate(data["posts"], 1):
        h = hl[p["id"]]
        v = to_video(h["start"])
        if v is None:
            log(f"WARNING {p['id']} starts inside a cut – link without time")
        posts.append({"name": f"{n:02d}_{h['slug']}", "quote": p.get("quote") or h["hook"],
                      "text": p.get("text") or h["caption"], "video": v,
                      "frame": p.get("frame", h["start"]), "frame_set": "frame" in p,
                      "reel": (h.get("render") or {}).get("file")})
    (OUT / "social").mkdir(parents=True, exist_ok=True)
    if images:
        post_images(posts)

    main_text = "\n\n".join(x for x in [data["claim"].strip(), data["summary"].strip(),
                                        f"▶ {t['speaker']}: {t['title']} ({minutes(total)})\n{link(t, None)}",
                                        tags] if x)
    main = POST.format(cls=" main", id="main",
                       media='<img src="brand/instagram-speaker.png" alt=""><img src="brand/youtube-thumbnail-a.png" alt="">',
                       head=f'<p class="claim">{escape(data["claim"])}</p>', text=escape(main_text),
                       files="obrázky: brand/instagram-speaker.png, brand/youtube-thumbnail-a.png")
    cards = []
    for p in posts:
        at = f"Celá přednáška od {youtube.yt(p['video'])}" if p["video"] is not None else "Celá přednáška"
        text = "\n\n".join(x for x in [p["text"].strip(), f"▶ {at}: {link(t, p['video'])}", tags] if x)
        img = f"social/{p['name']}.png"
        reel = f"../{p['reel']}" if p["reel"] else None
        media = f'<img src="{img}" alt="">' + (f'<video src="{reel}" controls preload="none"></video>' if reel else "")
        files = f"obrázek: out/{img}" + (f" · reels: {p['reel']}" if reel else "")
        cards.append(POST.format(cls="", id=p["name"], media=media,
                                 head=f'<p class="quote">„{escape(p["quote"])}“</p>', text=escape(text), files=files))
    (OUT / "social.html").write_text(HTML.format(
        title=escape(t["title"]), speaker=escape(t["speaker"]), event=escape(event_name(t)),
        url=link(t, None), main=main, n=len(posts), posts="".join(cards)))
    log(f"wrote out/social.html ({len(posts)} posts + main)")


def minutes(sec: float) -> str:
    return f"{round(sec / 60)} min"


# ------------------------------------------------------------------ article
def article():
    t = talk()
    data = load_json("article.json")
    to_video, _, total = youtube.timeline()
    chapters = [{"time": "0:00", "seconds": 0, "title": "Ukázka"}]
    for c in load_json("youtube.json")["chapters"]:
        v = to_video(c["start"])
        if v is not None:
            chapters.append({"time": youtube.yt(v), "seconds": int(v), "title": c["title"]})
    fm = {"title": t["title"], "speaker": t["speaker"], "event": event_name(t),
          "date": str(t["event"].get("date", "")), "youtube": f"https://www.youtube.com/watch?v={t['yt_id']}",
          "youtube_id": t["yt_id"], "duration": youtube.yt(total), "narrator": "slon",
          "description": t["abstract"], "chapters": chapters}
    body = [data["perex"].strip()]
    for s in data["sections"]:
        v = to_video(s["start"])
        if v is None:
            raise SystemExit(f"article: section '{s['title']}' starts inside a cut ({s['start']})")
        body += [f"## {s['title']}", f"[▶ {youtube.yt(v)}]({link(t, v)})", s["text"].strip()]
    if data.get("takeaways"):
        body += ["## Co si odnést", "\n".join(f"- {x}" for x in data["takeaways"])]
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)
    OUT.mkdir(exist_ok=True)
    (OUT / "article.md").write_text(f"---\n{head}---\n\n" + "\n\n".join(body) + "\n")
    log(f"wrote out/article.md ({len(data['sections'])} sections)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("social", "all"):
        social()
    if cmd == "social-text":                    # texts only, keep the rendered images
        social(images=False)
    if cmd in ("article", "all"):
        article()
