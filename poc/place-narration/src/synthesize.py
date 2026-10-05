"""Step 4: synthesize narration audio with VieNeu and record timings.

Usage: python src/synthesize.py v3turbo|v3nano|v3turbo-int8 [voice name]
"""
import json, resource, sys, time
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"
MIN_WORDS = 60


def main(mode: str, voice_name: str | None = None):
    from vieneu import Vieneu
    t0 = time.time()
    kwargs = {"precision": "int8"} if mode.endswith("-int8") else {}
    tts = Vieneu(mode=mode.replace("-int8", ""), **kwargs)
    load_s = time.time() - t0
    voices = tts.list_preset_voices()
    print(f"[{mode}] loaded in {load_s:.1f}s, sample_rate={tts.sample_rate}, voices={voices[:8]}", flush=True)
    names = [v[1] if isinstance(v, (tuple, list)) else str(v) for v in voices]
    voice = voice_name if voice_name in names else None
    print(f"[{mode}] voice={voice or 'default'}", flush=True)
    audio_dir = OUT / "audio" / mode
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for txt in sorted(OUT.glob("*.txt")):
        pid, lang = txt.stem.rsplit(".", 1)
        text = txt.read_text(encoding="utf-8").strip()
        if len(text.split()) < MIN_WORDS:
            continue
        t1 = time.time()
        wav = tts.infer(text, voice=voice) if voice else tts.infer(text)
        gen_s = time.time() - t1
        dur = len(wav) / tts.sample_rate
        target = audio_dir / f"{pid}.{lang}.wav"
        tts.save(wav, target)
        row = {"mode": mode, "place": pid, "lang": lang, "words": len(text.split()), "gen_s": round(gen_s, 1), "audio_s": round(dur, 1),
               "rtf": round(gen_s / dur, 2) if dur else None, "wav_kb": target.stat().st_size // 1024,
               "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}
        row['voice'] = voice or 'default'
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    (OUT / f"synth_{mode}.json").write_text(json.dumps({"load_s": round(load_s, 1), "sample_rate": tts.sample_rate, "voices": [list(v) for v in voices], "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
