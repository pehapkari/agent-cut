"""Step 6 – edit plan and FCPXML timeline.

  06_edit.py plan      detect cut candidates → work/edit_plan.json + work/edit_plan.md
  06_edit.py approve   mark proposals approved   (--reject E03,E07  to drop some)
  06_edit.py fcpxml    approved cuts → out/lecture.fcpxml (DaVinci Resolve)
                       (+ intro and layout track when steps 10 / 11 have run)

All times are main-audio seconds. Nothing is deleted from media: the timeline
just skips the cut ranges, every cut carries a marker with its reason, and the
full sources stay linked so any cut can be undone by dragging the edit point.

Automatic candidates: silences > 1.5 s (adaptive RMS threshold, shortened to
0.6 s; skipped when the camera mic hears the room = audience question,
laughter) and repeated sentence starts ("to je to je"). Editorial items that need judgement
(trim of start/end and the Q&A – never kept –, slips of the tongue, technical hold-ups) live in
work/edit_manual.json – written by a human (or Claude) after reading the
transcript – and are merged in here.
"""
import hashlib
import json
import shutil
import re
import subprocess
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

import numpy as np

from common import LECTURE, OUT, WORK, config, load_json, log, save_json, src, tc

PAUSE_MIN = 1.5      # s – silences longer than this are candidates
PAUSE_KEEP = 0.6     # s – how much of a long pause stays in the edit
SILENCE_OVER_FLOOR = 12   # dB above the room-noise floor still counts as silence
BLIP = 0.15          # s – short noises (clicks, chair) inside a pause are ignored
HOP = 0.03           # s – RMS window
ROOM_OVER_FLOOR = 4  # dB – camera mic this much above its floor = audience/laughter → keep
FPS = 30             # timeline frame rate


# ------------------------------------------------------------------ detection
def rms_db(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:a:0",
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop = int(16000 * HOP)
    n = len(x) // hop
    return 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)


def room_active(s0: float, s1: float, cam_db: np.ndarray, cam_off: float) -> bool:
    """Camera mic hears the room: audience question, laughter, applause."""
    seg = cam_db[max(0, int((s0 - cam_off) / HOP)): max(0, int((s1 - cam_off) / HOP))]
    return len(seg) > 0 and np.median(seg) > np.percentile(cam_db, 10) + ROOM_OVER_FLOOR


def detect_silences(ws: list[dict]) -> list[tuple[float, float]]:
    """Pauses from an adaptive RMS threshold, never overlapping a transcribed word."""
    db = rms_db(WORK / "audio_clean.wav")
    n = len(db)
    thresh = np.percentile(db, 10) + SILENCE_OVER_FLOOR
    silent = db < thresh
    # fill short non-silent blips
    blip = int(BLIP / HOP)
    i = 0
    while i < n:
        if not silent[i]:
            j = i
            while j < n and not silent[j]:
                j += 1
            if j - i <= blip and i > 0 and j < n:
                silent[i:j] = True
            i = j
        else:
            i += 1
    # words are speech even if quiet
    for w in ws:
        silent[int(w["s"] / HOP): int(w["e"] / HOP) + 1] = False
    out, i = [], 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if (j - i) * HOP >= PAUSE_MIN:
                out.append((i * HOP, j * HOP))
            i = j
        else:
            i += 1
    log(f"silence threshold {thresh:.1f} dBFS → {len(out)} pauses ≥ {PAUSE_MIN}s")
    return out


def norm(w: str) -> str:
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[^\w]", "", w)


def words(tr: dict) -> list[dict]:
    return [w for s in tr["segments"] for w in s["words"] if norm(w["w"])]


def context(ws: list[dict], t0: float, t1: float, pad: int = 6) -> str:
    i0 = next((i for i, w in enumerate(ws) if w["e"] > t0), len(ws))
    i1 = next((i for i, w in enumerate(ws) if w["s"] >= t1), len(ws))
    before = " ".join(w["w"] for w in ws[max(0, i0 - pad):i0])
    inside = " ".join(w["w"] for w in ws[i0:i1])
    after = " ".join(w["w"] for w in ws[i1:i1 + pad])
    return f"…{before} [{inside}] {after}…".replace("  ", " ")


def detect_repeats(ws: list[dict]) -> list[dict]:
    """Immediately repeated 2–4 word sequences (restarted sentence starts).

    Single-word doubles ("výrazně, výrazně", "pozor, pozor") are mostly
    deliberate emphasis in Czech, so they are left to the editor (edit_manual.json).
    """
    out, i = [], 0
    while i < len(ws):
        hit = None
        for n in (4, 3, 2):
            a = [norm(w["w"]) for w in ws[i:i + n]]
            b = [norm(w["w"]) for w in ws[i + n:i + 2 * n]]
            if len(b) == n and a == b:
                if ws[i + n]["s"] - ws[i + n - 1]["e"] > 1.0:   # separated by a pause → likely deliberate
                    continue
                hit = n
                break
        if hit:
            t0, t1 = ws[i]["s"], ws[i + hit]["s"]
            out.append({"type": "repeat", "start": t0, "end": t1,
                        "why": f"opakovaný start: „{' '.join(w['w'] for w in ws[i:i + hit])}“"})
            i += hit
        else:
            i += 1
    return out


def plan():
    tr = load_json("transcript.json")
    ws = words(tr)
    items = []
    cam_db = rms_db(src("camera"))
    cam_off = load_json("offsets.json")["camera"]["offset"]
    for s0, s1 in detect_silences(ws):
        if room_active(s0, s1, cam_db, cam_off):
            log(f"pause {tc(s0)} ({s1 - s0:.1f}s) kept – camera mic hears the room (audience/laughter)")
            continue
        cut0, cut1 = s0 + PAUSE_KEEP / 2, s1 - PAUSE_KEEP / 2
        items.append({"type": "pause", "start": cut0, "end": cut1,
                      "why": f"pauza {s1 - s0:.1f} s → zkráceno na {PAUSE_KEEP} s"})
    items += detect_repeats(ws)
    manual = WORK / "edit_manual.json"
    keeps = []
    if manual.exists():
        m = json.loads(manual.read_text())
        keeps = [k for k in m if k["type"] == "keep"]
        items += [k for k in m if k["type"] != "keep"]
        log(f"merged {manual.name} ({len(m) - len(keeps)} cuts, {len(keeps)} keep-ranges)")
    else:
        log("no work/edit_manual.json – only automatic candidates")
    # "keep" ranges veto automatic candidates that touch them
    items = [it for it in items if it["type"] not in ("pause", "repeat") or not any(it["start"] < k["end"] and it["end"] > k["start"] for k in keeps)]

    # merge overlaps (manual items win the "why")
    items.sort(key=lambda x: (x["start"], -x["end"]))
    merged = []
    for it in items:
        if merged and it["start"] < merged[-1]["end"]:   # touching cuts stay separate (reject one, keep other)
            m = merged[-1]
            if m["type"] in ("trim", "tech") or it["end"] <= m["end"]:
                m["end"] = max(m["end"], it["end"])
                continue
            m["end"] = max(m["end"], it["end"])
            m["why"] += f"; {it['why']}"
            continue
        merged.append(dict(it))

    old = {}
    if (WORK / "edit_plan.json").exists():
        old = {(round(i["start"], 1), i["type"]): i.get("status") for i in load_json("edit_plan.json")["cuts"]}
    for n, it in enumerate(merged, 1):
        it["id"] = f"E{n:03d}"
        it["start"], it["end"] = round(it["start"], 3), round(it["end"], 3)
        it["context"] = context(ws, it["start"], it["end"])
        it["status"] = old.get((round(it["start"], 1), it["type"]), "proposed")
    save_json("edit_plan.json", {"pause_keep": PAUSE_KEEP, "cuts": merged})
    write_md(merged)


TYPE_CZ = {"trim": "ořez", "pause": "pauza", "repeat": "opakovaný start", "slip": "přeřek",
           "tech": "technické zdržení", "other": "jiné"}


def write_md(cuts: list[dict]):
    cfg = config()
    total = sum(c["end"] - c["start"] for c in cuts)
    dur = load_json("offsets.json")["main_duration"]
    by_type = {}
    for c in cuts:
        by_type.setdefault(c["type"], []).append(c)
    lines = [f"# Návrh střihu: {cfg.get('title', '')}", "",
             f"Časy = hlavní audio. Celkem {len(cuts)} střihů, ubere {tc(total)} "
             f"→ výsledná délka ≈ {tc(dur - total)} (z {tc(dur)}).", "",
             "Schválení: odpověz „OK“, nebo vypiš ID, která nechceš (např. *bez E004, E017*). "
             "Nic se nemaže – v timeline jsou to jen střihy s markerem, plná média zůstávají.", "",
             "| typ | počet | ubere |", "|---|---:|---:|"]
    for t, cs in by_type.items():
        lines.append(f"| {TYPE_CZ.get(t, t)} | {len(cs)} | {sum(c['end'] - c['start'] for c in cs):.0f} s |")
    lines.append("")
    for t in ("trim", "tech", "slip", "repeat", "other", "pause"):
        cs = by_type.get(t)
        if not cs:
            continue
        lines += [f"## {TYPE_CZ.get(t, t).capitalize()}", ""]
        if t == "pause":
            lines += ["Všechny pauzy delší než 1,5 s zkrácené na 0,6 s (bez obsahu, proto jen přehled).", "",
                      "| ID | od | do | délka |", "|---|---|---|---:|"]
            lines += [f"| {c['id']} | {tc(c['start'])} | {tc(c['end'])} | {c['end'] - c['start']:.1f} s |" for c in cs]
        else:
            lines += ["| ID | od | do | délka | proč | kontext ([vystřiženo]) |", "|---|---|---|---:|---|---|"]
            for c in cs:
                ctx = c["context"].replace("|", "\\|")
                if len(ctx) > 220:
                    ctx = ctx[:100] + " … " + ctx[-100:]
                lines.append(f"| {c['id']} | {tc(c['start'])} | {tc(c['end'])} | {c['end'] - c['start']:.1f} s "
                             f"| {c['why']} | {ctx} |")
        lines.append("")
    (WORK / "edit_plan.md").write_text("\n".join(lines))
    log("wrote work/edit_plan.md")


def approve():
    data = load_json("edit_plan.json")
    reject = set()
    for a in sys.argv[2:]:
        if a.startswith("--reject"):
            reject |= {x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()}
    for c in data["cuts"]:
        c["status"] = "rejected" if c["id"] in reject else "approved"
    save_json("edit_plan.json", data)
    log(f"approved {sum(c['status'] == 'approved' for c in data['cuts'])}, rejected {len(reject)}")


# --------------------------------------------------------------------- FCPXML
def frames(t: float) -> int:
    return int(round(t * FPS))


def rt(n_frames: int) -> str:
    """Frame count → FCPXML rational time string."""
    f = Fraction(n_frames, FPS)
    return f"{f.numerator}/{f.denominator}s" if f.denominator != 1 else f"{f.numerator}s"


def keep_ranges(cuts: list[dict], dur: float) -> list[tuple[float, float, list]]:
    """Main-audio ranges kept after the approved cuts, with markers for cuts."""
    cuts = sorted(cuts, key=lambda c: c["start"])
    keep, t, pending = [], 0.0, []
    for c in cuts:
        if c["start"] > t:
            keep.append([t, c["start"], pending])
            pending = []
        pending = pending + [c]
        t = max(t, c["end"])
    if t < dur:
        keep.append([t, dur, pending])
    return [(a, b, m) for a, b, m in keep if b - a >= 1 / FPS]


def bumper(name: str) -> tuple[Path, int, bool] | None:
    """Rendered teaser / intro / outro (11_brand.py): path, length in frames, has audio."""
    path = WORK / "brand" / f"{name}.mp4"
    if not path.exists():
        return None
    # DaVinci keeps media it already knows by path: a re-rendered teaser.mp4 would
    # show the old version → link it under a name carrying a hash of its content
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
    versioned = WORK / "brand" / "edit" / f"{name}-{digest}.mp4"
    if not versioned.exists():
        versioned.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, versioned)  # a copy: a hard link would follow in-place re-renders
    path = versioned
    probe = lambda *a: subprocess.run(["ffprobe", "-v", "error", *a, "-of", "csv=p=0", str(path)],
                                      capture_output=True, text=True).stdout.strip()
    return path, frames(float(probe("-show_entries", "format=duration"))), \
        bool(probe("-select_streams", "a", "-show_entries", "stream=index"))


def fcpxml():
    cfg = config()
    offs = load_json("offsets.json")
    probe = load_json("probe.json")
    data = load_json("edit_plan.json")
    approved = [c for c in data["cuts"] if c["status"] == "approved"]
    if not approved and data["cuts"]:
        raise SystemExit("no approved cuts – run `06_edit.py approve` after review")

    # use the offset at the middle of each file so that drift splits evenly
    def mid_offset(key):
        o = offs[key]
        return o["offset"] + o.get("drift_ppm", 0) * 1e-6 * (o["duration"] / 2 - o.get("query_start", 0) - o.get("query_len", 0) / 2)

    src_info = {
        "camera": {"path": src("camera"), "off": mid_offset("camera"), "dur": probe["camera"]["duration"],
                   "w": probe["camera"]["video"][0]["width"], "h": probe["camera"]["video"][0]["height"],
                   "fps": round(probe["camera"]["video"][0]["fps"])},
        "screen": {"path": src("screen"), "off": offs["screen"]["offset"], "dur": probe["screen"]["duration"],
                   "w": probe["screen"]["video"][0]["width"], "h": probe["screen"]["video"][0]["height"],
                   "fps": round(probe["screen"]["video"][0]["fps"])},
        "audio": {"path": WORK / "audio_clean.wav", "off": 0.0, "dur": offs["main_duration"]},
    }
    log(f"camera offset (mid) {src_info['camera']['off']:.4f}s, screen {src_info['screen']['off']:.4f}s")

    def url(p: Path) -> str:
        return "file://" + quote(str(p.resolve()))

    res = [f'<format id="r0" name="FFVideoFormat1080p{FPS}" frameDuration="{rt(1)}" width="1920" height="1080"/>']
    assets = []
    for i, key in enumerate(("camera", "screen"), 1):
        s = src_info[key]
        res.append(f'<format id="r{i}" frameDuration="1/{s["fps"]}s" width="{s["w"]}" height="{s["h"]}"/>')
        assets.append(f'<asset id="{key}" name="{escape(s["path"].name)}" start="0s" duration="{rt(frames(s["dur"]))}" '
                      f'hasVideo="1" hasAudio="0" format="r{i}" videoSources="1">'
                      f'<media-rep kind="original-media" src="{url(s["path"])}"/></asset>')
    a = src_info["audio"]
    assets.append(f'<asset id="audio" name="audio_clean.wav" start="0s" duration="{rt(frames(a["dur"]))}" '
                  f'hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000">'
                  f'<media-rep kind="original-media" src="{url(a["path"])}"/></asset>')

    # optional: layout render (10_layout.py) on top; teaser + intro in front, outro at the end (11_brand.py)
    program = WORK / "layout" / "program.mp4"
    if program.exists():
        src_info["program"] = {"path": program, "off": 0.0, "dur": offs["main_duration"]}
        assets.append(f'<asset id="program" name="program.mp4" start="0s" duration="{rt(frames(offs["main_duration"]))}" '
                      f'hasVideo="1" hasAudio="0" format="r0" videoSources="1">'
                      f'<media-rep kind="original-media" src="{url(program)}"/></asset>')
        log("layout track: work/layout/program.mp4")
    bumpers = {}
    for name in ("teaser", "intro", "outro"):
        b = bumper(name)
        if not b:
            continue
        path, n, has_audio = bumpers[name] = b
        audio_attrs = 'hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000"' if has_audio else 'hasAudio="0"'
        assets.append(f'<asset id="{name}" name="{name}.mp4" start="0s" duration="{rt(n)}" '
                      f'hasVideo="1" format="r0" videoSources="1" {audio_attrs}>'
                      f'<media-rep kind="original-media" src="{url(path)}"/></asset>')
        log(f"{name}: {path.relative_to(LECTURE)} ({n} frames)")

    def bumper_clip(name, offset):
        _, n, has_audio = bumpers[name]
        return (f'<asset-clip ref="{name}" offset="{rt(offset)}" start="0s" duration="{rt(n)}" '
                f'name="{name}"' + (' audioRole="effects"' if has_audio else '') + '/>')

    spine, tl = [], 0
    for name in ("teaser", "intro"):
        if name in bumpers:
            spine.append(bumper_clip(name, tl))
            tl += bumpers[name][1]
    for a0, a1, markers in keep_ranges(approved, offs["main_duration"]):
        f0, f1 = frames(a0), frames(a1)
        dur = f1 - f0
        cam = src_info["camera"]
        cam_in = f0 - frames(cam["off"])
        cam_ok = cam_in >= 0 and cam_in + dur <= frames(cam["dur"])
        inner = []
        # markers (reason of the cut that precedes this range)
        parent_start = cam_in if cam_ok else 0
        for m in markers:
            inner.append(f'<marker start="{rt(parent_start)}" duration="{rt(1)}" '
                         f'value="{escape(m["id"] + " " + TYPE_CZ.get(m["type"], m["type"]) + ": " + m["why"])}"/>')
        # connected clips, clipped to each source's availability
        # V1 camera, V2 screen (raw angles for manual tweaks), V4 layout on top, A audio_clean
        lanes = [("screen", 1)] + ([] if cam_ok else [("camera", 2)]) + [("audio", -1)]
        if "program" in src_info:
            lanes.append(("program", 3))
        for key, lane in lanes:
            s = src_info[key]
            s_in = f0 - frames(s["off"])
            lo, hi = max(0, -s_in), min(dur, frames(s["dur"]) - s_in)
            if hi - lo <= 0:
                continue
            inner.append(f'<asset-clip ref="{key}" lane="{lane}" offset="{rt(parent_start + lo)}" '
                         f'start="{rt(s_in + lo)}" duration="{rt(hi - lo)}" name="{key}"'
                         + (' audioRole="dialogue"' if key == "audio" else "") + "/>")
        body = "".join(inner)
        if cam_ok:
            spine.append(f'<asset-clip ref="camera" offset="{rt(tl)}" start="{rt(cam_in)}" duration="{rt(dur)}" '
                         f'name="camera">{body}</asset-clip>')
        else:
            spine.append(f'<gap name="gap" offset="{rt(tl)}" start="0s" duration="{rt(dur)}">{body}</gap>')
        tl += dur

    if "outro" in bumpers:
        spine.append(bumper_clip("outro", tl))
        tl += bumpers["outro"][1]

    title = escape(cfg.get("title") or "lecture")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
  <resources>
    {chr(10).join('    ' + r for r in res).strip()}
    {chr(10).join('    ' + r for r in assets).strip()}
  </resources>
  <library>
    <event name="{title}">
      <project name="{title}">
        <sequence format="r0" duration="{rt(tl)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
            {(chr(10) + '            ').join(spine)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""
    OUT.mkdir(exist_ok=True)
    (OUT / "lecture.fcpxml").write_text(xml)
    log(f"wrote out/lecture.fcpxml – {len(spine)} clips, length {tc(tl / FPS)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"plan": plan, "approve": approve, "fcpxml": fcpxml}[cmd]()
