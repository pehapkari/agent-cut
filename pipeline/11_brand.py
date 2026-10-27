"""Step 11 – brand graphics from data (Remotion templates in pipeline/remotion/src/brand).

  11_brand.py assets   talk.md + ../event.md → work/brand/props.json + public/
  11_brand.py studio   Remotion Studio with this lecture's data (live preview)
  11_brand.py stills   PNG cards → out/brand/*.png (+ work/brand/video-background@2x.png)
  11_brand.py intro    animated intro → work/brand/intro.mp4
  11_brand.py outro    thank-you + end screen → work/brand/outro.mp4
  11_brand.py teaser   cold open from work/teaser.json → work/brand/teaser.mp4
                       (needs sync + face track: steps 4 and 10)
  11_brand.py svg      editable SVG of every card → out/brand/svg/*.svg
  11_brand.py          all of the above

Data (no recordings needed, so it also works for promo before the event):
  <event>/event.md            front matter: number, name, date, time, venue, url,
                              image (illustration), partner {name, logo}
  <event>/<talk>/talk.md      front matter: speaker, title, photo, order (in the
                              program); body = abstract
  work/teaser.json            [{"start", "end", "text"}] – 5–6 lines of 2–3 s (main-audio
                              time) that make people watch the whole talk
Paths in the front matter are relative to the .md file. The photo is any
normal photo – the face is found automatically and kept in every crop.
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml
from fontTools.ttLib import TTFont

from common import LECTURE, OUT, TOOLS, WORK, ffmpeg_bin, load_json, log, run, src

REMOTION = Path(__file__).resolve().parent / "remotion"
BRAND = WORK / "brand"
PUBLIC = BRAND / "public"
FONT = TOOLS / "fonts" / "hagrid" / "Hagrid-Regular-trial.ttf"
TEASER_WIPE = 8 / 30   # s – clips overlap by WIPE frames, see Intro.tsx
TEASER_CLOSE = 15 / 30  # s – the last clip runs on while the bars close into the sting
TEASER_BAR = 234        # px – the teaser's bars are twice the talk layout's (BAR in kit.tsx)
TEASER_HEAD = 1080 - 2 * TEASER_BAR - 2 * 24  # px – speaker = slide height, ~3× the talk layout
TEASER_GAP = 48         # px – between the slide and the speaker
TEASER_ZOOM = 1.3       # head crop relative to the layout's
STILLS = ["event-card", "speaker-card", "video-background", "youtube-thumbnail-a",
          "youtube-thumbnail-b", "instagram-speaker", "instagram-event"]
DAYS = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
MONTHS = ["ledna", "února", "března", "dubna", "května", "června", "července",
          "srpna", "září", "října", "listopadu", "prosince"]


def front_matter(md: Path) -> tuple[dict, str]:
    text = md.read_text()
    if not text.startswith("---"):
        return {}, text.strip()
    _, head, body = text.split("---", 2)
    return yaml.safe_load(head) or {}, body.strip()


def face_box(img_path: Path) -> dict | None:
    """Largest face, normalized to the image size (YuNet, same model as 10_layout)."""
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    k = min(1.0, 1200 / max(w, h))
    small = cv2.resize(img, (int(w * k), int(h * k)))
    det = cv2.FaceDetectorYN.create(str(TOOLS / "models" / "face_detection_yunet_2023mar.onnx"), "",
                                    (small.shape[1], small.shape[0]), 0.6)
    _, faces = det.detect(small)
    if faces is None:
        log(f"WARNING no face found in {img_path.name} – photo is centered")
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4] / k
    return {"x": round(float(x / w), 4), "y": round(float(y / h), 4), "w": round(float(fw / w), 4), "h": round(float(fh / h), 4)}


def copy_asset(src: Path, name: str) -> str:
    dst = PUBLIC / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    return name


def talk_data(talk_dir: Path, slug: str) -> dict:
    md = talk_dir / "talk.md"
    if not md.exists():
        raise SystemExit(f"{md} not found")
    fm, body = front_matter(md)
    photo = None
    if fm.get("photo"):
        src = (talk_dir / fm["photo"]).resolve()
        name = copy_asset(src, f"photos/{slug}{src.suffix.lower()}")
        h, w = cv2.imread(str(src)).shape[:2]
        photo = {"file": name, "w": w, "h": h, "face": face_box(src)}
    return {"speaker": fm.get("speaker", ""), "title": fm.get("title", ""), "abstract": body, "photo": photo,
            "order": fm.get("order", 99)}


def event_data(event_md: Path) -> dict:
    fm, _ = front_matter(event_md) if event_md.exists() else ({}, "")
    when = where = ""
    if fm.get("date"):
        d = fm["date"] if isinstance(fm["date"], datetime.date) else datetime.date.fromisoformat(str(fm["date"]))
        when = f"{DAYS[d.weekday()]} {d.day}. {MONTHS[d.month - 1]}"
    if fm.get("time"):
        where = f"od {fm['time']}" + (f" v {fm['venue']}" if fm.get("venue") else "")
    image = None
    if fm.get("image"):
        src = (event_md.parent / fm["image"]).resolve()
        image = copy_asset(src, "event/image" + src.suffix.lower())
    partner = None
    if fm.get("partner"):
        p = fm["partner"]
        logo = None
        if p.get("logo"):
            src = (event_md.parent / p["logo"]).resolve()
            logo = copy_asset(src, "event/partner" + src.suffix.lower())
        partner = {"name": p.get("name", ""), "logo": logo}
    return {"name": fm.get("name", "pražský sraz přátel PHP"), "number": fm.get("number", 0),
            "when": when, "where": where, "url": fm.get("url", "pehapkari.cz"), "image": image,
            "partner": partner}


def teaser_clips() -> list[dict]:
    """Cut the teaser lines from the sources into public/teaser/: the screen
    (cropped like the layout) and a large face-tracked head with the clean audio.
    The Teaser composition lays them out with the speaker larger than in the talk."""
    spec = WORK / "teaser.json"
    if not spec.exists():
        return []
    layout = __import__("10_layout")
    offs, probe = load_json("offsets.json"), load_json("probe.json")
    crop = __import__("08_reels").screen_crop(probe["screen"]["duration"])
    track = layout.track_head(probe["camera"]["duration"])
    cw, ch = probe["camera"]["video"][0]["width"], probe["camera"]["video"][0]["height"]
    sh = TEASER_HEAD                             # the slide as tall as the speaker
    sw = min(round(sh * crop[0] / crop[1] / 2) * 2, 1920 - 2 * TEASER_GAP - TEASER_GAP - TEASER_HEAD)
    lines = json.loads(spec.read_text())
    n_main = int((max(c["end"] for c in lines) + 2) * 30)
    k, hx, hy, side = layout.head_crops(track, cw, ch, n_main, offs["camera"])
    big = min(ch, int(side * TEASER_ZOOM))      # a bit more of the body: the window is large
    (PUBLIC / "teaser").mkdir(parents=True, exist_ok=True)
    clips = []
    for i, c in enumerate(lines):
        # start/end are the spoken words; pad the end by the picture that runs on
        # under the transition (wipe to the next line, or the close into the sting)
        start = c["start"]
        dur = c["end"] + (TEASER_WIPE if i < len(lines) - 1 else TEASER_CLOSE) - start
        n = round(dur * 30)
        screen, head = f"teaser/{i:02d}-screen.mp4", f"teaser/{i:02d}-head.mp4"
        run(["ffmpeg", "-ss", f"{start - offs['screen']['offset']:.3f}", "-i", str(src("screen")), "-t", f"{dur:.3f}",
             "-an", "-vf", f"fps=30,crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]},scale={sw}:{sh}:flags=lanczos",
             "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", str(PUBLIC / screen)])
        # head: camera frames of the layout's face track, re-cropped larger
        f0 = int(round(start * 30))
        cam = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-ss", f"{max(0, k[f0]) / 30:.3f}", "-i", str(src("camera")),
                                "-map", "0:v:0", "-vf", "fps=30", "-frames:v", str(n), "-f", "rawvideo",
                                "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        enc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{TEASER_HEAD}x{TEASER_HEAD}", "-r", "30", "-i", "-",
                                "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(WORK / "audio_clean.wav"),
                                "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "14", "-preset", "fast",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", str(PUBLIC / head)],
                               stdin=subprocess.PIPE)
        frame = np.zeros((ch, cw, 3), np.uint8)
        for j in range(n):
            buf = cam.stdout.read(cw * ch * 3)
            if len(buf) == cw * ch * 3:          # else (camera ended) hold the last frame
                frame = np.frombuffer(buf, np.uint8).reshape(ch, cw, 3)
            f = f0 + j
            x = int(np.clip(hx[f] + side / 2 - big / 2, 0, cw - big))
            y = int(np.clip(hy[f] + side * 0.45 - big * 0.45, 0, ch - big))
            roi = frame[y:y + big, x:x + big]
            enc.stdin.write(cv2.resize(roi, (TEASER_HEAD, TEASER_HEAD), interpolation=cv2.INTER_LANCZOS4).tobytes())
        enc.stdin.close()
        cam.stdout.close()
        cam.terminate()
        if enc.wait() != 0:
            raise SystemExit(f"teaser head {i} failed")
        clips.append({"screen": screen, "head": head, "frames": n, "text": c["text"],
                      "screenSize": [sw, sh], "headSize": TEASER_HEAD})
    log(f"teaser: {len(clips)} clips, {sum(c['frames'] for c in clips) / 30:.1f} s, head from {big}px of camera")
    return clips


def metrics(texts: list[str]) -> dict:
    """Advance widths (per 1000 units) of every character used, for word wrapping."""
    font = TTFont(FONT)
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    scale = 1000 / font["head"].unitsPerEm
    chars = set("".join(texts))
    return {ch: round(hmtx[cmap[ord(ch)]][0] * scale) for ch in chars if ord(ch) in cmap}


def assets() -> dict:
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    copy_asset(FONT, "fonts/Hagrid-Regular.ttf")
    event = event_data(LECTURE.parent / "event.md")
    talk = talk_data(LECTURE, "speaker")
    # every talk of the event (sibling folders), for the event post
    talks = [talk_data(d, f"talk-{i}") for i, d in enumerate(sorted(LECTURE.parent.iterdir()))
             if (d / "talk.md").exists()]
    talks.sort(key=lambda t: t["order"])          # program order (talk.md "order"), else by folder
    music = None
    cfg_path = LECTURE / "lecture.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        if cfg.get("intro_music"):
            music = copy_asset(LECTURE / cfg["intro_music"], "music" + Path(cfg["intro_music"]).suffix)
    teaser = teaser_clips()
    texts = [event["name"], event["url"], event["when"], event["where"], talk["speaker"], talk["title"],
             talk["abstract"], "Díky za sledování! Podpořit nás můžete na ://"] + [c["text"] for c in teaser]
    props = {"event": event, "talk": talk, "talks": talks, "metrics": metrics(texts), "music": music,
             "teaser": teaser}
    (BRAND / "props.json").write_text(json.dumps(props, indent=1, ensure_ascii=False))
    log(f"wrote work/brand/props.json ({talk['speaker']} – {talk['title']}; {len(talks)} talks in the event)")
    return props


def npx(*args):
    cmd = ["npx", "remotion", *args]
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=REMOTION, check=True)


def bundle() -> str:
    out = BRAND / "bundle"
    npx("bundle", f"--public-dir={PUBLIC}", f"--out-dir={out}")
    return str(out)


def render(serve: str, comp: str, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    npx("render", serve, comp, str(dst), f"--props={BRAND / 'props.json'}",
        "--codec=h264", "--crf=16", "--audio-codec=aac")
    log(f"wrote {dst.relative_to(LECTURE)}")


def stills(serve: str):
    for comp in STILLS:
        npx("still", serve, comp, str(OUT / "brand" / f"{comp}.png"), f"--props={BRAND / 'props.json'}",
            "--image-format=png")
    # background under speaker + slides (10_layout.py) at 2× like the Figma export
    npx("still", serve, "video-background", str(BRAND / "video-background@2x.png"),
        f"--props={BRAND / 'props.json'}", "--image-format=png", "--scale=2")
    log(f"wrote out/brand/*.png ({len(STILLS)} cards)")


def svg():
    js = BRAND / "export.cjs"
    subprocess.run([str(REMOTION / "node_modules/.bin/esbuild"), "src/brand/export.tsx", "--bundle",
                    "--platform=node", "--jsx=automatic", "--log-level=warning", f"--outfile={js}"],
                   cwd=REMOTION, check=True)
    subprocess.run(["node", str(js), str(BRAND / "props.json"), str(PUBLIC), str(OUT / "brand" / "svg")],
                   check=True)
    log("wrote out/brand/svg/*.svg")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    props = assets()
    if cmd == "studio":
        npx("studio", f"--public-dir={PUBLIC}", f"--props={BRAND / 'props.json'}")
    elif cmd == "svg":
        svg()
    elif cmd != "assets":
        serve = bundle()
        if cmd in ("stills", "all"):
            stills(serve)
        if cmd in ("intro", "all"):
            render(serve, "Intro", BRAND / "intro.mp4")
        if cmd in ("outro", "all"):
            render(serve, "Outro", BRAND / "outro.mp4")
        if cmd in ("teaser", "all") and props["teaser"]:
            render(serve, "Teaser", BRAND / "teaser.mp4")
        if cmd == "all":
            svg()
