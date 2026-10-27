"""Step 5 – transcribe work/audio_clean.wav with mlx-whisper (word timestamps).

→ work/transcript.json  (segments + words, times in main-audio seconds)
→ work/transcript.md    (readable, paragraphs with timestamps)
"""
import json
import time

from common import WORK, config, log, save_json, tc

PARA_GAP = 2.0     # pause that starts a new paragraph
PARA_MAX = 75.0    # max paragraph length in seconds


def transcribe(cfg: dict) -> dict:
    import mlx_whisper

    audio = WORK / "audio_clean.wav"
    if not audio.exists():
        raise SystemExit("work/audio_clean.wav missing – run 03_audio.py")
    log(f"transcribing with {cfg['whisper_model']} (this takes a while)")
    t0 = time.time()
    res = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=cfg["whisper_model"],
        language=cfg.get("language", "cs"),
        word_timestamps=True,
        initial_prompt=cfg.get("whisper_prompt") or None,
        condition_on_previous_text=False,       # avoids repetition loops
        hallucination_silence_threshold=2.0,
        verbose=False,
    )
    log(f"done in {(time.time() - t0) / 60:.1f} min")
    segments = []
    for s in res["segments"]:
        segments.append({
            "id": s["id"], "start": round(s["start"], 3), "end": round(s["end"], 3),
            "text": s["text"].strip(),
            "avg_logprob": round(s.get("avg_logprob", 0), 3),
            "no_speech_prob": round(s.get("no_speech_prob", 0), 3),
            "words": [{"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3),
                       "p": round(w.get("probability", 0), 3)} for w in s.get("words", [])],
        })
    return {"model": cfg["whisper_model"], "language": res.get("language"), "segments": segments}


def write_md(data: dict, cfg: dict) -> None:
    paras, cur = [], []
    for s in data["segments"]:
        if cur and (s["start"] - cur[-1]["end"] > PARA_GAP or s["end"] - cur[0]["start"] > PARA_MAX):
            paras.append(cur)
            cur = []
        cur.append(s)
    if cur:
        paras.append(cur)
    lines = [f"# Přepis: {cfg.get('title') or cfg['audio']}", "",
             f"Časy odpovídají hlavnímu audiu (`{cfg['audio']}` / `work/audio_clean.wav`).", ""]
    for p in paras:
        lines.append(f"**[{tc(p[0]['start'])}]** " + " ".join(s["text"] for s in p))
        lines.append("")
    (WORK / "transcript.md").write_text("\n".join(lines))
    log(f"wrote work/transcript.md ({len(paras)} paragraphs)")


def main():
    cfg = config()
    import sys
    if (WORK / "transcript.json").exists() and "--force" not in sys.argv:
        log("transcript.json exists – regenerating only transcript.md (use --force to re-transcribe)")
        data = json.loads((WORK / "transcript.json").read_text())
    else:
        data = transcribe(cfg)
        save_json("transcript.json", data)
    write_md(data, cfg)


if __name__ == "__main__":
    main()
