"""Step 0 – join recordings that are split into several files → work/joined/.

lecture.json "audio", "screen" or "camera" may be a list of files instead of one name:
  * audio: the recorder splits long takes into consecutive files (e.g. every
    hour) → concatenated losslessly, back to back.
  * screen / camera: separate recordings with a pause in between → each part is
    placed on the main-audio timeline by audio cross-correlation, the gap holds
    the last frame (silence in the audio), and everything goes into one 30 fps
    file. Parts are trimmed to the main audio, so a camera file that also holds
    the previous talk contributes only the overlapping tail.
Nothing to do when all are single files. Originals are only read.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import LECTURE, WORK, config, log, run, tc  # noqa: E402

JOINED = WORK / "joined"


def duration(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True).stdout)


def join_audio(names: list[str]) -> Path:
    dst = JOINED / f"audio{Path(names[0]).suffix.lower()}"
    if dst.exists():
        return dst
    lst = JOINED / "audio_list.txt"
    lst.write_text("".join(f"file '{(LECTURE / n).as_posix()}'\n" for n in names))
    run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dst)])
    log(f"audio: {len(names)} files → {dst.relative_to(LECTURE)} ({tc(duration(dst))})")
    return dst


def place(main_sig, p: Path, d: float) -> dict:
    """Offset of a part vs. main audio; tries several query windows, because
    a part may overlap the main audio only at its start or end."""
    sync = __import__("04_sync")
    qlen = min(sync.QUERY_LEN, d)
    pad = np.zeros(int(qlen * sync.SR))
    ref = np.concatenate([pad, main_sig, pad])
    best = None
    for qs in sorted({min(20.0, d - qlen), max(0.0, d / 2 - qlen / 2), max(0.0, d - qlen - 20.0)}):
        k, conf = sync.xcorr_peak(ref, sync.load(p, qs, qlen))
        r = {"offset": (k - len(pad)) / sync.SR - qs, "confidence": round(conf, 2), "query_start": qs}
        if best is None or r["confidence"] > best["confidence"]:
            best = r
    if best["confidence"] < 1.5:
        # weak global peak (short overlap, distant camera mic): accept it only
        # when two independent windows inside the predicted overlap agree
        t0 = max(0.0, -best["offset"])
        t1 = min(d, len(main_sig) / sync.SR - best["offset"]) - sync.CHECK_LEN - sync.CHECK_SEARCH
        q0, q1 = best["query_start"], best["query_start"] + qlen
        spots = [t for t in np.linspace(t0, t1, 7) if t + sync.CHECK_LEN <= q0 or t >= q1] or list(np.linspace(t0, t1, 3))
        checks = [sync.check(main_sig, p, best["offset"], float(t)) for t in spots[:3]]
        agree = [c for c in checks if abs(c["delta_ms"]) <= 1000 / 30]
        log(f"  weak peak, checks: " + ", ".join(f"Δ {c['delta_ms']} ms" for c in checks))
        if len(agree) >= 2:
            best["confidence"] = 1.5
            best["verified_by"] = len(agree)
    return best


def join_video(key: str, names: list[str], main: Path) -> Path:
    dst = JOINED / f"{key}.mp4"
    if dst.exists():
        return dst
    sync = __import__("04_sync")
    log("loading main audio (16 kHz mono)")
    main_sig = sync.load(main)
    main_dur = len(main_sig) / sync.SR
    parts = []
    for n in names:
        p = LECTURE / n
        d = duration(p)
        r = place(main_sig, p, d)
        log(f"{key} part {n}: offset {r['offset']:+.3f}s (confidence {r['confidence']}), {tc(d)}")
        if r["confidence"] < 1.5:
            raise SystemExit(f"{n}: audio sync not reliable – place the parts manually")
        # keep only what overlaps the main audio
        t0, t1 = max(0.0, -r["offset"]), min(d, main_dur - r["offset"])
        if t1 <= t0:
            raise SystemExit(f"{n}: does not overlap the main audio")
        parts.append((r["offset"] + t0, t1 - t0, t0, p))
    parts.sort()
    inputs, chains = [], []
    for i, (at, d, t0, p) in enumerate(parts):
        gap = parts[i + 1][0] - (at + d) if i + 1 < len(parts) else 0.0
        if gap < 0:
            raise SystemExit(f"{key} parts overlap by {-gap:.2f}s")
        inputs += ["-ss", f"{t0:.3f}", "-t", f"{d:.3f}", "-i", str(p)]
        chains.append(f"[{i}:v]fps=30,setsar=1,tpad=stop_mode=clone:stop_duration={gap:.3f}[v{i}];"
                      f"[{i}:a]aresample=48000,apad=pad_dur={gap:.3f}[a{i}];")
        log(f"  part {i + 1} at main {tc(at)} (from {tc(t0)} of the file), then {gap:.2f}s hold")
    n = len(parts)
    fc = "".join(chains) + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    run(["ffmpeg", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "160k", str(dst)])
    log(f"{key}: {n} parts → {dst.relative_to(LECTURE)} ({tc(duration(dst))})")
    return dst


def main():
    cfg = config()
    JOINED.mkdir(parents=True, exist_ok=True)
    audio = cfg.get("audio")
    main = join_audio(audio) if isinstance(audio, list) else LECTURE / audio
    for key in ("screen", "camera"):
        if isinstance(cfg.get(key), list):
            join_video(key, cfg[key], main)
    if not any(isinstance(cfg.get(k), list) for k in ("audio", "screen", "camera")):
        log("nothing to join")


if __name__ == "__main__":
    main()
