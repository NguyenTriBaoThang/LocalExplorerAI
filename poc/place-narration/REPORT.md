# PoC report: place narration

Run on: Intel Core 7 240H, 16 threads (AVX2 + AVX-VNNI), no GPU, Python 3.12, onnxruntime 1.22.1 (1.30 fails to load VieNeu's ONNX graphs because of a stricter external-data path check with the Hugging Face cache).
Other applications were running, so timings are indicative, not benchmarks.

## 1. Wikipedia / Wikidata matching (5 sample places)
| Place | Result | vi words | en words |
| --- | --- | --- | --- |
| Nhà thờ Đức Bà Sài Gòn | matched (20 m) | 174 | 131 |
| Bưu điện Trung tâm Sài Gòn | matched (16 m) | 118 | 40 (too short) |
| Chợ Bến Thành | matched (3 m) | 215 | 130 |
| Công viên Bến Bạch Đằng | no Wikidata candidate | — | — |
| Highlands Coffee Nhà thờ Đức Bà | no Wikidata candidate | — | — |

3/5 matched, all famous landmarks. The wrong-entity safeguard (name similarity) was not exercised, because the cafe returned no candidates at all.
After cleanup, 5 of 6 texts are long enough (>= 60 words) for narration.

## 2. Synthesis speed (generation time / audio length)
| Place | Lang | v3turbo (fp32) | v3turbo-int8 | v3nano |
| --- | --- | --- | --- | --- |
| Bưu điện Trung tâm | vi | 43.1 s / 30.4 s | 38.2 s / 31.8 s | 12.8 s / 33.7 s |
| Bưu điện Trung tâm | en | — | — | — |
| Chợ Bến Thành | vi | 76.8 s / 48.3 s | 73.3 s / 49.6 s | 27.5 s / 53.2 s |
| Chợ Bến Thành | en | 74.0 s / 46.5 s | 66.7 s / 48.2 s | 23.5 s / 54.5 s |
| Nhà thờ Đức Bà | vi | 49.9 s / 32.0 s | 43.3 s / 33.0 s | 19.4 s / 34.7 s |
| Nhà thờ Đức Bà | en | 71.8 s / 36.5 s | 58.0 s / 39.5 s | 19.9 s / 44.4 s |

| Mode | Sample rate | Load | Real-time factor | Peak RSS | Size | Voice |
| --- | --- | --- | --- | --- | --- | --- |
| v3turbo | 48 kHz | 19.2 s | 1.42–1.97 (mean 1.63) | 2966 MB | 94 KB/s | default |
| v3turbo-int8 | 48 kHz | 40.1 s | 1.20–1.48 (mean 1.37) | 2382 MB | 94 KB/s | Thiện Minh |
| v3nano | 24 kHz | 78.5 s | 0.38–0.56 (mean 0.47) | 851 MB | 47 KB/s | default |

Real-time factor = generation time / audio length; below 1.0 is faster than real time.
Voices differ between runs (turbo fp32 and nano used their default voice, int8 used "Thiện Minh"), so quality is not strictly comparable.

## 3. Findings
- **Turbo is slower than real time on this CPU** (RTF about 1.2–2.0): a 30–50 s clip takes 40–77 s. int8 is only about 15–20 % faster even though the CPU supports AVX-VNNI.
- **Nano is about 3–4x faster** (RTF 0.38–0.56, under 1 GB RAM) but VieNeu itself documents weaker English and code-switched text.
- Go/no-go "about 90 s of speech in under about 15 s": **not met** by any mode. Nano needs roughly 35–50 s for 90 s of speech.
- Output carries VieNeu's default audio watermark (`apply_watermark=True`).
- All model weights involved report Apache-2.0 on Hugging Face (Turbo, Nano, v2, Codec, MOSS tokenizer). Training-data licensing was not checked.

## 4. Open items
- Audio quality has not been judged: it needs a human listener (Vietnamese and English).
- English quality with Turbo/Nano is unverified; a separate English voice may be needed.
- Match quality for lesser-known places, and a retry for "Bến Bạch Đằng" under its short name.

## 5. Implication for the design
Scope is landmarks only, so the set of places that get narration is small. Generating audio ahead of time (batch, then cache) removes the wait for the first listener, which a CPU-bound on-demand request cannot avoid.

## 6. Decision after listening
- The reviewer listened to the `v3turbo` samples and judged the quality acceptable. v3 Turbo is the chosen model; Nano is not needed on quality grounds.
- Because Turbo runs slower than real time on CPU (RTF about 1.4–2.0), narration must be generated ahead of time (batch for the landmarks, then cache by content hash). Generate-on-request is kept only as a fallback when the source text changes.
- Not yet judged: English quality with Turbo, and the int8 variant (only about 15–20 % faster, so little reason to prefer it).
