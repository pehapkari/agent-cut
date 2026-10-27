#!/usr/bin/env bash
# Lecture pipeline runner.
#
#   pipeline/run.sh [LECTURE_DIR] [STEP...]
#
#   pipeline/run.sh                     all automatic steps 0–5 on the current dir
#   pipeline/run.sh ~/Movies/talk 4 5   only sync + transcript of another lecture
#   pipeline/run.sh . setup             create .venv and download tools only
#
# Steps 6–8 need human decisions in between (see README.md):
#   11 brand (intro, outro, cards from talk.md + ../event.md) → 6 plan → review → approve → 10 layout → fcpxml
#   7      → pick in work/highlights.md → 8 → 9
#   ytsentences → write work/youtube.json → 12 (YouTube description)
#   youtube: in talk.md → write work/social.json + work/article.json → 13 (publish)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

LECTURE="${1:-.}"
shift || true
export LECTURE_DIR="$(cd "$LECTURE" && pwd)"
STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(0 1 2 3 4 5)

setup() {
  command -v ffmpeg >/dev/null || { echo "installing ffmpeg"; brew install ffmpeg; }
  command -v uv >/dev/null || { echo "installing uv"; brew install uv; }
  [ -x "$PY" ] || uv venv --python 3.12 "$VENV"
  uv pip install --python "$PY" -q numpy scipy mlx-whisper opencv-python-headless pillow svgpathtools pyyaml fonttools
  [ -d "$HERE/remotion/node_modules" ] || (cd "$HERE/remotion" && npm ci)
  mkdir -p "$ROOT/tools/fonts" "$ROOT/tools/models"
  if [ ! -x "$ROOT/tools/ffmpeg" ]; then
    # static arm64 build WITH libass (Homebrew's bottle has none → no burned subtitles)
    local B=https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2
    local T; T="$(mktemp -d)"
    curl -sL -o "$T/ffmpeg.zip" "$B/ffmpeg.zip"
    curl -sL "$B/ffmpeg.zip.sha256" | awk '{print $1"  '"$T"'/ffmpeg.zip"}' | shasum -a 256 -c -
    unzip -q -o "$T/ffmpeg.zip" -d "$T" && mv "$T/ffmpeg" "$ROOT/tools/ffmpeg" && rm -rf "$T"
  fi
  [ -f "$ROOT/tools/fonts/Montserrat-ExtraBold.ttf" ] || curl -sL -o "$ROOT/tools/fonts/Montserrat-ExtraBold.ttf" \
    https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf
  [ -f "$ROOT/tools/models/face_detection_yunet_2023mar.onnx" ] || curl -sL -o "$ROOT/tools/models/face_detection_yunet_2023mar.onnx" \
    https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
  "$ROOT/tools/ffmpeg" -hide_banner -filters 2>/dev/null | grep -q " ass " || echo "WARNING: tools/ffmpeg has no libass"
}

step() {
  case "$1" in
    setup) setup ;;
    0|join) "$PY" "$HERE/00_join.py" ;;
    1) "$PY" "$HERE/01_probe.py" ;;
    2) "$PY" "$HERE/02_proxy.py" ;;
    3) "$PY" "$HERE/03_audio.py" ;;
    4) "$PY" "$HERE/04_sync.py" ;;
    5) "$PY" "$HERE/05_transcript.py" ;;
    6|plan) "$PY" "$HERE/06_edit.py" plan ;;
    approve) "$PY" "$HERE/06_edit.py" approve ;;
    fcpxml) "$PY" "$HERE/06_edit.py" fcpxml ;;
    7) "$PY" "$HERE/07_highlights.py" ;;
    sentences) "$PY" "$HERE/07_highlights.py" sentences ;;
    8) "$PY" "$HERE/08_reels.py" ;;
    9) "$PY" "$HERE/09_check.py" ;;
    10|layout) "$PY" "$HERE/10_layout.py" ;;
    11|brand|intro) "$PY" "$HERE/11_brand.py" ;;
    12|youtube) "$PY" "$HERE/12_youtube.py" ;;
    ytsentences) "$PY" "$HERE/12_youtube.py" sentences ;;
    13|publish) "$PY" "$HERE/13_publish.py" ;;
    studio) "$PY" "$HERE/11_brand.py" studio ;;
    *) echo "unknown step $1"; exit 1 ;;
  esac
}

[ -x "$PY" ] || setup
for s in "${STEPS[@]}"; do
  echo "=== step $s ($LECTURE_DIR)"
  step "$s"
done
