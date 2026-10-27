"""Step 3 – clean main audio → work/audio_clean.wav.

mono → stereo, light FFT denoise, gentle compression, gain + peak limiter and
finally a *linear* loudnorm to -14 LUFS / -1 dBTP (the limiter makes room so
loudnorm never falls back to its pumping "dynamic" mode).
"""
import json
import re

from common import WORK, log, run, save_json, src

TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.0, 11.0
PRE = ("pan=stereo|c0=c0|c1=c0,highpass=f=70,afftdn=nr=10:nf=-40:tn=1,"
       "acompressor=threshold=-30dB:ratio=2.5:attack=5:release=150")


def loudnorm_stats(stderr: str, key: str) -> dict:
    return json.loads(re.findall(r"\{[^{}]*\"%s\"[^{}]*\}" % key, stderr)[-1])


def measure(inp: str, chain: str) -> dict:
    res = run(["ffmpeg", "-i", inp, "-af",
               f"{chain},loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
               "-f", "null", "-"])
    return loudnorm_stats(res.stderr, "input_i")


def main():
    WORK.mkdir(exist_ok=True)
    inp = str(src("audio"))

    log("pass 1/3: measure loudness")
    m0 = measure(inp, PRE)
    gain = TARGET_I - float(m0["input_i"])
    log(f"source I={m0['input_i']} TP={m0['input_tp']} → gain {gain:+.1f} dB")

    chain = f"{PRE},volume={gain:.2f}dB,alimiter=limit=-2dB:level=false:attack=2:release=60"
    log("pass 2/3: measure after gain + limiter")
    m = measure(inp, chain)
    log(f"limited I={m['input_i']} TP={m['input_tp']} LRA={m['input_lra']}")

    log("pass 3/3: linear loudnorm")
    # linear mode needs target LRA ≥ measured LRA (wide-range talks, e.g. quiet Q&A)
    lra = min(50.0, max(TARGET_LRA, float(m["input_lra"]) + 1.0))
    ln = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={lra:.1f}"
          f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json")
    dst = WORK / "audio_clean.wav"
    res = run(["ffmpeg", "-i", inp, "-af", f"{chain},{ln}",
               "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])
    out = loudnorm_stats(res.stderr, "output_i")
    log(f"result: I={out['output_i']} TP={out['output_tp']} type={out['normalization_type']}")
    if out["normalization_type"] != "linear":
        log("WARNING: loudnorm fell back to dynamic mode")
    latency = compensate_latency(inp, dst)
    save_json("audio_clean.json", {"source": m0, "gain_db": gain, "limited": m, "result": out,
                                   "latency_compensated_samples": latency, "filter": f"{chain},loudnorm"})


def pcm(path, start, dur, sr=16000):
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(start), "-t", str(dur), "-i", str(path),
                          "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def compensate_latency(orig: str, dst) -> int:
    """Filters (afftdn, alimiter look-ahead) delay the output by a few ms.
    Measure it against the original by cross-correlation and shift it back,
    so audio_clean shares the original's timeline (sync offsets stay valid)."""
    import numpy as np
    from scipy import signal
    sr, t = 48000, 300.0
    a = pcm(orig, t - 0.5, 61.0, sr)
    b = pcm(dst, t, 60.0, sr)
    c = signal.correlate(a, b, mode="valid", method="fft")
    lag = int(np.argmax(np.abs(c))) - int(0.5 * sr)        # b(t) == a(t + lag)
    delay = -lag
    log(f"filter latency: {delay} samples ({delay / sr * 1000:.2f} ms)")
    if delay <= 0:
        return 0
    tmp = dst.with_suffix(".shift.wav")
    run(["ffmpeg", "-i", str(dst), "-af", f"atrim=start_sample={delay},asetpts=PTS-STARTPTS,apad=pad_len={delay}",
         "-c:a", "pcm_s24le", str(tmp)])
    tmp.replace(dst)
    b = pcm(dst, t, 60.0, sr)
    c = signal.correlate(a, b, mode="valid", method="fft")
    log(f"after compensation: {int(np.argmax(np.abs(c))) - int(0.5 * sr)} samples")
    return delay


if __name__ == "__main__":
    main()
