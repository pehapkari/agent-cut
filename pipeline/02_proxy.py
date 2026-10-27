"""Step 2 – 720p / 30 fps constant-frame-rate proxies for analysis → work/proxy/.

Proxies are CFR so frame grabs are predictable even for VFR phone footage.
Final renders always read the originals.
"""
import sys

from common import WORK, log, run, src

PROXY = WORK / "proxy"


def make_proxy(key: str, force: bool) -> None:
    dst = PROXY / f"{key}.mp4"
    if dst.exists() and not force:
        log(f"{dst.name} exists, skipping (use --force)")
        return
    tmp = dst.with_suffix(".part.mp4")
    run([
        "ffmpeg", "-i", str(src(key)),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale=-2:720:flags=bicubic,fps=30",
        "-c:v", "h264_videotoolbox", "-b:v", "2500k",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart", str(tmp),
    ])
    tmp.rename(dst)
    log(f"wrote {dst}")


def main():
    force = "--force" in sys.argv
    PROXY.mkdir(parents=True, exist_ok=True)
    for key in ("camera", "screen"):
        make_proxy(key, force)


if __name__ == "__main__":
    main()
