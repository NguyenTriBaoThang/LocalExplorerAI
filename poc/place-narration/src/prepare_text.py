"""Step 3: turn Wikipedia lead sections into narration text for TTS.

No LLM: only deterministic cleanup, so no fact can be added. Attribution is kept in the JSON, not read aloud.
"""
import json, re
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"
MAX_WORDS = 220      # about 90 s of speech
MIN_WORDS = 60       # below this the lead is too thin for a narration


def clean(text: str, lang: str) -> str:
    text = re.sub(r"\[[^\]]*\]", "", text)                      # footnote markers like [1]
    for _ in range(3):                                           # nested parentheses: names in other languages, dates, IPA
        text = re.sub(r"\s*\([^()]*\)", "", text)
    word_to = " đến " if lang == "vi" else " to "
    text = re.sub(r"(\d)\s*[–—-]\s*(\d)", rf"\1{word_to}\2", text)  # 1886–1891
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def trim(text: str, limit: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out, count = [], 0
    for s in sentences:
        n = len(s.split())
        if out and count + n > limit:
            break
        out.append(s)
        count += n
    return " ".join(out)


def main():
    rows = []
    for f in sorted(OUT.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        for lang, art in rec.get("articles", {}).items():
            text = trim(clean(art["text"], lang), MAX_WORDS)
            words = len(text.split())
            (OUT / f"{rec['place_id']}.{lang}.txt").write_text(text + "\n", encoding="utf-8")
            rows.append({"place": rec["name"], "lang": lang, "raw_words": art["words"], "clean_words": words, "usable": words >= MIN_WORDS})
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
