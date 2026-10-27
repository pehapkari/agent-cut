"""Step 4 – find offsets of camera and screen vs. main audio → work/offsets.json.

Convention:  main_time = source_time + offset
(offset > 0 → the source started *after* the main audio recorder.)

Audio method: 16 kHz mono, band-pass 200–4000 Hz, FFT cross-correlation of the
first ~5 min of each source against the whole main audio. The offset is then
re-measured on two other windows (≈40 % and ≈80 % of the overlap) to verify it
and to estimate clock drift.

Visual method (screen recording with silent audio): per-frame "how much the
picture changed" signal of the screen proxy vs. the projected area in the
camera proxy (lecture.json: projection_crop). Slide changes give sharp spikes
in both; their cross-correlation gives the screen→camera lag, and the camera's
audio offset chains it to the main audio. Verified on two more windows.
"""
import subprocess

import numpy as np
from scipy import signal

from common import WORK, config, log, save_json, src

SR = 16000
QUERY_LEN = 300.0     # seconds of the source used for the global search
CHECK_LEN = 60.0      # seconds per verification window
CHECK_SEARCH = 5.0    # ± seconds searched around the predicted offset
FRAME_TOL = 1 / 30    # max acceptable deviation (one camera frame)


def load(path, start=0.0, dur=None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.3f}", "-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)
    return prep(x)


_SOS = signal.butter(4, [200, 4000], btype="band", fs=SR, output="sos")


def prep(x: np.ndarray) -> np.ndarray:
    x = signal.sosfiltfilt(_SOS, x.astype(np.float64))
    return x / (np.std(x) + 1e-9)


def xcorr_peak(ref: np.ndarray, query: np.ndarray):
    """Lag (samples) where query best matches inside ref, plus confidence."""
    c = signal.correlate(ref, query, mode="valid", method="fft")
    c = np.abs(c)
    k = int(np.argmax(c))
    # parabolic sub-sample refinement
    if 0 < k < len(c) - 1:
        a, b, d = c[k - 1], c[k], c[k + 1]
        k_f = k + 0.5 * (a - d) / (a - 2 * b + d)
    else:
        k_f = float(k)
    # confidence: peak vs. best peak outside ±0.5 s
    guard = int(0.5 * SR)
    masked = c.copy()
    masked[max(0, k - guard): k + guard] = 0
    conf = float(c[k] / (masked.max() + 1e-9))
    return k_f, conf


def find_offset(main: np.ndarray, path, src_dur: float) -> dict:
    qlen = min(QUERY_LEN, src_dur)
    # start the query a bit in, the first seconds are often silence/handling
    qstart = min(20.0, max(0.0, src_dur - qlen))
    query = load(path, qstart, qlen)
    # search with the query padded so that negative offsets are found too
    pad = np.zeros(len(query))
    ref = np.concatenate([pad, main, pad])
    k, conf = xcorr_peak(ref, query)
    offset = (k - len(pad)) / SR - qstart
    return {"offset": round(offset, 4), "confidence": round(conf, 2), "query_start": qstart, "query_len": qlen}


def check(main: np.ndarray, path, offset: float, at: float) -> dict:
    query = load(path, at, CHECK_LEN)
    m_start = at + offset - CHECK_SEARCH
    i0 = int(round(m_start * SR))
    ref = main[max(0, i0): i0 + len(query) + int(2 * CHECK_SEARCH * SR)]
    k, conf = xcorr_peak(ref, query)
    local = (max(0, i0) + k) / SR - at
    return {"at_source": round(at, 1), "at_main": round(at + offset, 1), "offset": round(local, 4),
            "delta_ms": round((local - offset) * 1000, 1), "confidence": round(conf, 2)}


def max_volume(path) -> float:
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-t", "600", "-i", str(path),
                          "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True)
    for line in res.stderr.splitlines():
        if "max_volume" in line:
            return float(line.split("max_volume:")[1].split()[0])
    return -999.0  # no audio stream


# ---------------------------------------------------------------- visual sync
VFPS = 30


def change_signal(proxy, crop: str | None) -> np.ndarray:
    cache = WORK / "sync_cache" / f"{proxy.stem}_{(crop or 'full').replace(':', '-')}.npy"
    if cache.exists():
        return np.load(cache)
    vf = f"fps={VFPS}" + (f",crop={crop}" if crop else "") + ",scale=64:36:flags=area,format=gray"
    log(f"extracting change signal from {proxy.name}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(proxy), "-vf", vf,
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64).astype(np.float32)
    d = np.concatenate([[0], np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))])
    d = np.clip(d - signal.medfilt(d, 31), 0, None)   # keep sudden changes only
    d = (d - d.mean()) / (d.std() + 1e-9)
    cache.parent.mkdir(exist_ok=True)
    np.save(cache, d)
    return d


def peak(x: np.ndarray, guard: int) -> tuple[int, float]:
    k = int(np.argmax(x))
    m = x.copy()
    m[max(0, k - guard): k + guard] = 0
    return k, float(x[k] / (m.max() + 1e-9))


def visual_offset(cam_offset: float, crop: str | None, dur: float) -> dict:
    s = change_signal(WORK / "proxy" / "screen.mp4", None)
    c = change_signal(WORK / "proxy" / "camera.mp4", crop)
    x = signal.correlate(c, s, mode="full", method="fft")
    k, conf = peak(x, VFPS)
    lag = (k - (len(s) - 1)) / VFPS          # camera_time = screen_time + lag
    log(f"screen→camera lag {lag:+.3f}s (conf {conf:.1f})")
    checks = []
    win = 180 * VFPS
    for f in (0.4, 0.8):
        a = int(f * (len(s) - win))
        r0 = a + int(round(lag * VFPS)) - 90
        if r0 < 0 or r0 + win + 180 > len(c):
            continue
        xc = signal.correlate(c[r0:r0 + win + 180], s[a:a + win], mode="valid")
        kk, cc = peak(xc, VFPS // 2)
        local = (r0 + kk - a) / VFPS
        checks.append({"at_source": round(a / VFPS, 1), "offset": round(local + cam_offset, 4),
                       "delta_ms": round((local - lag) * 1000, 1), "confidence": round(cc, 2)})
    return {"method": "visual (slide changes vs. projection in camera)", "offset": round(lag + cam_offset, 4),
            "screen_to_camera": round(lag, 4), "confidence": round(conf, 2), "projection_crop": crop,
            "duration": round(dur, 3), "checks": checks,
            "ok": conf > 1.5 and all(abs(c["delta_ms"]) <= 2000 / VFPS for c in checks),
            "precision": "±1–2 frames @30fps (screen has no lip-sync, fine for cutting)"}


def main():
    cfg = config()
    main_path = src("audio")
    log("loading main audio (16 kHz mono)")
    main_sig = load(main_path)
    main_dur = len(main_sig) / SR
    result = {"convention": "main_time = source_time + offset (seconds)", "main": cfg["audio"],
              "main_duration": round(main_dur, 3)}

    for key in ("camera", "screen"):
        path = src(key)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)
        vol = max_volume(path)
        if vol < -80:
            log(f"{key}: audio is silent ({vol} dB) → visual sync")
            if key != "screen" or "camera" not in result:
                raise SystemExit(f"{key}: no usable audio and no visual reference – set offset manually")
            r = visual_offset(result["camera"]["offset"], cfg.get("projection_crop"), dur)
            for c in r["checks"]:
                log(f"{key}: check @{c['at_source']}s Δ {c['delta_ms']} ms (conf {c['confidence']})")
            if not r["ok"]:
                log(f"WARNING: {key} visual sync not verified – check manually")
            result[key] = r
            continue
        log(f"{key}: global search")
        r = find_offset(main_sig, path, dur)
        log(f"{key}: offset {r['offset']:+.3f}s confidence {r['confidence']}")
        # verification windows inside the overlap
        ov_start = max(0.0, -r["offset"])
        ov_end = min(dur, main_dur - r["offset"]) - CHECK_LEN - CHECK_SEARCH
        checks = [check(main_sig, path, r["offset"], ov_start + f * (ov_end - ov_start)) for f in (0.4, 0.8)]
        for c in checks:
            log(f"{key}: check @{c['at_source']}s → {c['offset']:+.4f}s (Δ {c['delta_ms']} ms, conf {c['confidence']})")
        # drift: linear fit through global + checks
        xs = [r["query_start"] + r["query_len"] / 2] + [c["at_source"] + CHECK_LEN / 2 for c in checks]
        ys = [r["offset"]] + [c["offset"] for c in checks]
        slope = float(np.polyfit(xs, ys, 1)[0]) if len(xs) > 1 else 0.0
        total_drift = slope * dur
        r.update({
            "method": "audio cross-correlation",
            "duration": round(dur, 3),
            "checks": checks,
            "drift_ppm": round(slope * 1e6, 1),
            "drift_over_file_ms": round(total_drift * 1000, 1),
            "ok": all(abs(c["delta_ms"]) / 1000 <= FRAME_TOL for c in checks) and r["confidence"] > 1.5,
        })
        if not r["ok"]:
            log(f"WARNING: {key} sync not verified within one frame – check manually")
        result[key] = r

    save_json("offsets.json", result)


if __name__ == "__main__":
    main()
