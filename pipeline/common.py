"""Shared helpers for the lecture pipeline.

Every step works on a *lecture directory* (default: current working dir, or
$LECTURE_DIR). Originals are only ever read. Outputs go to <lecture>/work and
<lecture>/out.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LECTURE = Path(os.environ.get("LECTURE_DIR", os.getcwd())).resolve()
WORK = LECTURE / "work"
OUT = LECTURE / "out"
CONFIG = LECTURE / "lecture.json"
# pipeline-local binaries, fonts and models (next to pipeline/, shared by all lectures)
TOOLS = Path(__file__).resolve().parent.parent / "tools"

AUDIO_EXT = {".wav", ".flac", ".mp3", ".m4a", ".aif", ".aiff"}
VIDEO_EXT = {".mov", ".mp4", ".mkv", ".m4v", ".avi"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ffmpeg_bin() -> str:
    """ffmpeg with libass if available (tools/ffmpeg), otherwise system one."""
    local = TOOLS / "ffmpeg"
    return str(local) if local.exists() else (shutil.which("ffmpeg") or "ffmpeg")


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    if cmd[0] == "ffmpeg":
        cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y"] + cmd[1:]
    log("$ " + " ".join(cmd if len(" ".join(cmd)) < 400 else cmd[:12] + ["…"]))
    res = subprocess.run(cmd, capture_output=quiet, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr[-4000:] if res.stderr else "")
        raise SystemExit(f"command failed ({res.returncode}): {cmd[0]}")
    return res


def _autodetect() -> dict:
    files = sorted(p for p in LECTURE.iterdir() if p.is_file() and not p.name.startswith("."))
    audio = [p for p in files if p.suffix.lower() in AUDIO_EXT]
    videos = [p for p in files if p.suffix.lower() in VIDEO_EXT]
    screen = [p for p in videos if p.suffix.lower() == ".mkv"]  # OBS default
    camera = [p for p in videos if p not in screen]
    svgs = [p for p in files if p.suffix.lower() == ".svg"]
    speaker_svg = [p for p in svgs if "speaker" in p.name]
    intro_svg = [p for p in svgs if p not in speaker_svg]

    def png_for(svg: Path | None) -> str | None:
        if not svg:
            return None
        for cand in (svg.with_name(svg.stem + "@2x.png"), svg.with_suffix(".png")):
            if cand.exists():
                return cand.name
        return None

    first = lambda lst: lst[0] if lst else None
    return {
        "title": "",
        "speaker": "",
        "language": "cs",
        "audio": first(audio).name if audio else None,
        "screen": first(screen).name if screen else None,
        "camera": first(camera).name if camera else None,
        "intro_svg": first(intro_svg).name if intro_svg else None,
        "intro_png": png_for(first(intro_svg)),
        "speaker_svg": first(speaker_svg).name if speaker_svg else None,
        "speaker_png": png_for(first(speaker_svg)),
        "whisper_model": "mlx-community/whisper-large-v3-mlx",
        "whisper_prompt": "",
        # crop of the projected slides inside the 720p camera proxy (w:h:x:y),
        # used for visual sync when the screen recording has no audio
        "projection_crop": None,
    }


def config() -> dict:
    """Load lecture.json; create it by auto-detection on first run."""
    if not CONFIG.exists():
        cfg = _autodetect()
        CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        log(f"created {CONFIG.name} by auto-detection – check it!")
    cfg = json.loads(CONFIG.read_text())
    talk = LECTURE / "talk.md"                  # speaker / title live in talk.md (11_brand.py)
    if talk.exists() and talk.read_text().startswith("---"):
        import yaml
        fm = yaml.safe_load(talk.read_text().split("---", 2)[1]) or {}
        cfg.update({k: fm[k] for k in ("speaker", "title") if fm.get(k)})
    return cfg


def src(key: str) -> Path:
    name = config().get(key)
    if not name:
        raise SystemExit(f"lecture.json: '{key}' is not set")
    if isinstance(name, list):                  # split recording → joined by 00_join.py
        p = WORK / "joined" / f"{key}{Path(name[0]).suffix.lower() if key == 'audio' else '.mp4'}"
        if not p.exists():
            raise SystemExit(f"{p} not found – run step 0 (join) first")
        return p
    p = LECTURE / name
    if not p.exists():
        raise SystemExit(f"missing source file: {p}")
    return p


def load_json(name: str) -> dict:
    p = WORK / name
    if not p.exists():
        raise SystemExit(f"{p} not found – run the previous step first")
    return json.loads(p.read_text())


def save_json(name: str, data) -> Path:
    WORK.mkdir(exist_ok=True)
    p = WORK / name
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    log(f"wrote {p.relative_to(LECTURE)}")
    return p


def tc(sec: float, ms: bool = False) -> str:
    """Seconds → H:MM:SS(.mmm)."""
    sign = "-" if sec < 0 else ""
    sec = abs(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if ms:
        return f"{sign}{int(h)}:{int(m):02d}:{s:06.3f}"
    return f"{sign}{int(h)}:{int(m):02d}:{int(s):02d}"
