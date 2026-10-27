"""Step 0 – join recordings that are split into several files → work/joined/.

lecture.json "audio" or "screen" may be a list of files instead of one name:
  * audio: the recorder splits long takes into consecutive files (e.g. every
    hour) → concatenated losslessly, back to back.
  * screen: separate recordings with a pause in between → each part is placed
    on the main-audio timeline by audio cross-correlation, the gap holds the
    last frame (silence in the audio), and everything goes into one 30 fps file.
Nothing to do when both are single files. Originals are only read.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import LECTURE, WORK, config, ffmpeg_bin, log, run, tc  # noqa: E402

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


def join_screen(names: list[str], main: Path) -> Path:
    dst = JOINED / "screen.mp4"
    if dst.exists():
        return dst
    sync = __import__("04_sync")
    log("loading main audio (16 kHz mono)")
    main_sig = sync.load(main)
    parts = []
    for n in names:
        p = LECTURE / n
        d = duration(p)
        r = sync.find_offset(main_sig, p, d)
        log(f"screen part {n}: offset {r['offset']:+.3f}s (confidence {r['confidence']}), {tc(d)}")
        if r["confidence"] < 1.5:
            raise SystemExit(f"{n}: audio sync not reliable – place the parts manually")
        parts.append((r["offset"], d, p))
    parts.sort()
    inputs, chains = [], []
    for i, (off, d, p) in enumerate(parts):
        gap = parts[i + 1][0] - (off + d) if i + 1 < len(parts) else 0.0
        if gap < 0:
            raise SystemExit(f"screen parts overlap by {-gap:.2f}s")
        inputs += ["-i", str(p)]
        chains.append(f"[{i}:v]fps=30,setsar=1,tpad=stop_mode=clone:stop_duration={gap:.3f}[v{i}];"
                      f"[{i}:a]aresample=48000,apad=pad_dur={gap:.3f}[a{i}];")
        log(f"  part {i + 1} at main {tc(off)}, then {gap:.2f}s hold")
    n = len(parts)
    fc = "".join(chains) + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    run(["ffmpeg", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "160k", str(dst)])
    log(f"screen: {n} parts → {dst.relative_to(LECTURE)} ({tc(duration(dst))})")
    return dst


def main():
    cfg = config()
    JOINED.mkdir(parents=True, exist_ok=True)
    audio = cfg.get("audio")
    main = join_audio(audio) if isinstance(audio, list) else LECTURE / audio
    if isinstance(cfg.get("screen"), list):
        join_screen(cfg["screen"], main)
    if not any(isinstance(cfg.get(k), list) for k in ("audio", "screen")):
        log("nothing to join")


if __name__ == "__main__":
    main()
