"""Step 1 – ffprobe all sources → work/probe.json."""
import json
import subprocess

from common import LECTURE, config, log, save_json, src

KEYS = ["audio", "screen", "camera", "intro_png", "intro_svg", "speaker_png", "speaker_svg"]


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    raw = json.loads(out)
    fmt = raw.get("format", {})
    info = {
        "file": path.name,
        "size_mb": round(int(fmt.get("size", 0)) / 1e6, 1),
        "duration": float(fmt["duration"]) if "duration" in fmt else None,
        "creation_time": fmt.get("tags", {}).get("creation_time"),
        "video": [],
        "audio": [],
    }
    for s in raw.get("streams", []):
        if s["codec_type"] == "video":
            num, den = (s.get("r_frame_rate") or "0/1").split("/")
            anum, aden = (s.get("avg_frame_rate") or "0/1").split("/")
            info["video"].append({
                "index": s["index"], "codec": s.get("codec_name"),
                "width": s.get("width"), "height": s.get("height"),
                "fps": round(int(num) / int(den), 3) if int(den) else None,
                "avg_fps": round(int(anum) / int(aden), 3) if int(aden) else None,
                "vfr": s.get("r_frame_rate") != s.get("avg_frame_rate"),
                "pix_fmt": s.get("pix_fmt"),
                "rotation": next((sd.get("rotation") for sd in s.get("side_data_list", []) if "rotation" in sd), 0),
                "nb_frames": s.get("nb_frames"),
            })
        elif s["codec_type"] == "audio":
            info["audio"].append({
                "index": s["index"], "codec": s.get("codec_name"),
                "sample_rate": int(s.get("sample_rate", 0)), "channels": s.get("channels"),
                "layout": s.get("channel_layout"),
            })
    return info


def main():
    cfg = config()
    result = {}
    for key in KEYS:
        name = cfg.get(key)
        if not name:
            continue
        p = src(key) if isinstance(name, list) else LECTURE / name   # split recording → joined file
        if p.suffix.lower() == ".svg":
            result[key] = {"file": name, "size_mb": round(p.stat().st_size / 1e6, 1)}
            continue
        result[key] = probe(p)
        d = result[key].get("duration")
        v = result[key]["video"][0] if result[key]["video"] else {}
        log(f"{key:12s} {p.name:32s} dur={d}  {v.get('width')}x{v.get('height')}@{v.get('avg_fps')}  audio={len(result[key]['audio'])}")
    save_json("probe.json", result)


if __name__ == "__main__":
    main()
