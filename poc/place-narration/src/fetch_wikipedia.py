"""Step 1-2: match places to Wikidata entities and fetch Wikipedia lead sections.

Standard library only. Respects the Wikimedia API etiquette: descriptive User-Agent, serial requests, small delay.
Matching needs BOTH proximity (coordinates) and name similarity, so a cafe named after a nearby landmark
is not matched to the landmark.
"""
import difflib, json, math, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "out"
UA = "LocalExplorerAI-PoC/0.1 (https://github.com/NguyenTriBaoThang/LocalExplorerAI; research prototype)"
PLACE_IDS = [
    "sai-gon-nha-tho-duc-ba-sai-gon",
    "sai-gon-buu-dien-trung-tam-sai-gon",
    "sai-gon-cho-ben-thanh",
    "sai-gon-cong-vien-ben-bach-dang",
    "sai-gon-highlands-coffee-nha-tho-duc-ba",
]
MAX_KM = 0.6
MIN_NAME_RATIO = 0.6


def get(url: str, params: dict) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(0.6)
    return data


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def match(place: dict) -> dict:
    cands = []
    for lang in ("vi", "en"):
        res = get("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": place["name"], "language": lang, "limit": 6, "format": "json"})
        cands += [c["id"] for c in res.get("search", [])]
    ids = list(dict.fromkeys(cands))
    if not ids:
        return {"status": "no_candidates"}
    ents = get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(ids[:20]), "props": "claims|sitelinks|labels", "languages": "vi|en", "format": "json"})["entities"]
    best, rows = None, []
    for qid, e in ents.items():
        coord = (e.get("claims", {}).get("P625") or [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        labels = [e.get("labels", {}).get(l, {}).get("value", "") for l in ("vi", "en")]
        ratio = max((difflib.SequenceMatcher(None, fold(place["name"]), fold(l)).ratio() for l in labels if l), default=0)
        dist = km(place["lat"], place["lon"], coord["latitude"], coord["longitude"]) if coord else None
        sl = e.get("sitelinks", {})
        row = {"qid": qid, "labels": labels, "name_ratio": round(ratio, 2), "distance_km": None if dist is None else round(dist, 3),
               "viwiki": sl.get("viwiki", {}).get("title"), "enwiki": sl.get("enwiki", {}).get("title")}
        rows.append(row)
        ok = dist is not None and dist <= MAX_KM and ratio >= MIN_NAME_RATIO and (row["viwiki"] or row["enwiki"])
        if ok and (best is None or ratio > best["name_ratio"]):
            best = row
    rows.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0))
    return {"status": "matched" if best else "rejected_all", "match": best, "considered": rows[:6]}


def lead(lang: str, title: str) -> dict | None:
    res = get(f"https://{lang}.wikipedia.org/w/api.php", {"action": "query", "prop": "extracts|info", "exintro": 1, "explaintext": 1, "inprop": "url",
                                                          "titles": title, "redirects": 1, "format": "json", "formatversion": 2})
    page = res["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        return None
    return {"lang": lang, "title": page["title"], "url": page["fullurl"], "revision": page.get("lastrevid"), "license": "CC BY-SA 4.0",
            "text": page["extract"].strip(), "chars": len(page["extract"]), "words": len(page["extract"].split())}


def main():
    data = json.load(open(ROOT / "data" / "sai_gon_places.json", encoding="utf-8"))
    items = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
    by_id = {i["id"]: i for i in items}
    summary = []
    for pid in PLACE_IDS:
        place = by_id[pid]
        print("→", place["name"])
        m = match(place)
        rec = {"place_id": pid, "name": place["name"], "lat": place["lat"], "lon": place["lon"], "fetched_at": datetime.now(timezone.utc).isoformat(), **m, "articles": {}}
        if m.get("match"):
            for lang, key in (("vi", "viwiki"), ("en", "enwiki")):
                if m["match"].get(key):
                    art = lead(lang, m["match"][key])
                    if art:
                        rec["articles"][lang] = art
        (OUT / f"{pid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append({"place": place["name"], "status": m["status"], "qid": (m.get("match") or {}).get("qid"),
                        "dist_km": (m.get("match") or {}).get("distance_km"), "name_ratio": (m.get("match") or {}).get("name_ratio"),
                        "vi_words": rec["articles"].get("vi", {}).get("words"), "en_words": rec["articles"].get("en", {}).get("words")})
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
