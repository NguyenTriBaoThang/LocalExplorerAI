# PoC: place narration (Wikipedia/Wikidata text + VieNeu TTS)

Throwaway experiment, **not** part of the product. It does not touch `apps/`.
Goal: decide whether a "listen to this place" feature is worth building.

## Questions
1. For places in `data/sai_gon_places.json`, how many have a correct, usable Wikipedia/Wikidata article (vi and en)?
2. How good and how fast is VieNeu on this CPU, in Vietnamese and in English?
3. Does a content-keyed cache (place + language + voice + text hash) behave as expected?

## Decisions already made
- TTS: VieNeu (open source, runs on CPU). Compare with a separate English voice if English is weak.
- Audio is generated on the first request, then cached. It never plays automatically.
- Text sources: Wikipedia and Wikidata only, with attribution (CC BY-SA).
- Per-place reviews are out of scope.
- **Scope: the voice guide is offered only for famous landmarks and historic sites**, i.e. places that have a matched Wikipedia/Wikidata article. Other places (cafes, small venues, parks without an article) show no listen button. The PoC result for the 5 sample places supports this: only the 3 well-known landmarks matched.

## Sample places
| id | name | why |
| --- | --- | --- |
| sai-gon-nha-tho-duc-ba-sai-gon | Nhà thờ Đức Bà Sài Gòn | landmark, expected rich articles |
| sai-gon-buu-dien-trung-tam-sai-gon | Bưu điện Trung tâm Sài Gòn | landmark |
| sai-gon-cho-ben-thanh | Chợ Bến Thành | market, expected rich articles |
| sai-gon-cong-vien-ben-bach-dang | Công viên Bến Bạch Đằng | riverside, thinner coverage |
| sai-gon-highlands-coffee-nha-tho-duc-ba | Highlands Coffee Nhà thờ Đức Bà | negative control: a cafe whose name contains a landmark, tests wrong-entity matching |

## Steps
0. Check machine and VieNeu licenses (code: Apache 2.0; **weights licence still to be confirmed on each model card**).
1. Match each place to a Wikidata entity (name plus coordinates) and verify the match by distance.
2. Fetch the lead section from viwiki and enwiki; store title, URL, revision, licence, fetched_at.
3. Trim to about 150–250 words, normalise for TTS, keep the attribution string.
4. Generate vi and en audio; record time, real-time factor, memory, file size.
5. Exercise the cache (miss, hit, changed text).
6. Write `REPORT.md` with a table per place and the go/no-go criteria below.

## Go / no-go
- At least 3 of 5 places have a correct Vietnamese article match.
- The Vietnamese voice sounds acceptable to the reviewer (a person must listen).
- About 90 s of speech is generated in under about 15 s on CPU.
- English is acceptable, or a fallback English voice is chosen.

## Layout (planned)
```
poc/place-narration/
  README.md
  REPORT.md        # written at the end
  src/             # scripts
  out/             # text and metadata (audio under out/audio is git-ignored)
```
