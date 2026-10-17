"""Download a small curated set of location-specific Wikimedia Commons photos.

Only explicit file titles and exact source-dataset place names are included.
The Commons API's license metadata is saved alongside each local asset.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "apps" / "web" / "public" / "images" / "places" / "hcmc"
MANIFEST_PATH = ROOT / "data" / "raw" / "hcmc_commons_photo_manifest.json"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "LocalExplorerAI/1.0 (HCMC photo attribution; contact project maintainers)"

# source_id -> (exact local dataset name, Wikimedia Commons file title)
CURATED_FILES = {
    "sai-gon-bao-tang-chung-tich-chien-tranh": (
        "Bảo tàng Chứng tích Chiến tranh",
        "Bảo tàng chứng tích chiến tranh Thành phố, năm 2018 (Danh sách thảm sát Thạnh Phong) (2).jpg",
    ),
    "sai-gon-pho-di-bo-nguyen-hue": (
        "Phố đi bộ Nguyễn Huệ",
        "Phố đi bộ Nguyễn Huệ trong sự kiện HIFF 2024.jpg",
    ),
    "sai-gon-nha-hat-thanh-pho-ho-chi-minh": (
        "Nhà hát Thành phố Hồ Chí Minh",
        "Nhà hát lớn Thành phố Hồ Chí Minh.JPG",
    ),
    "sai-gon-dinh-doc-lap": (
        "Dinh Độc Lập",
        "Dinh Độc Lập 3.jpg",
    ),
    "sai-gon-ben-nha-rong": (
        "Bến Nhà Rồng",
        "Bến Nhà Rồng.jpg",
    ),
    "sai-gon-chua-vinh-nghiem": (
        "Chùa Vĩnh Nghiêm",
        "Chùa Vĩnh Nghiêm.jpg",
    ),
    "sai-gon-chua-giac-lam": (
        "Chùa Giác Lâm",
        "Chua Giac Lam Gate.JPG",
    ),
    "sai-gon-chua-ba-thien-hau": (
        "Chùa Bà Thiên Hậu",
        "Thien Hau Temple, Ho Chi Minh City PB309855.jpg",
    ),
    "sai-gon-nha-tho-tan-dinh": (
        "Nhà thờ Tân Định",
        "Nhà thờ Tân Định.JPG",
    ),
    "sai-gon-cho-binh-tay": (
        "Chợ Bình Tây",
        "Chợ Bình Tây.jpg",
    ),
    "sai-gon-hoi-quan-nghia-an": (
        "Hội quán Nghĩa An",
        "Nghĩa An hội quán.jpg",
    ),
    "sai-gon-landmark-81": (
        "Landmark 81",
        "Landmark 81.png",
    ),
    "sai-gon-bitexco-financial-tower": (
        "Bitexco Financial Tower",
        "Bitexco Financial Tower.jpg",
    ),
    "sai-gon-dam-sen": (
        "Đầm Sen",
        "Cá chép nhào lộn, Công viên Đầm Sen.JPG",
    ),
    "sai-gon-dia-dao-cu-chi-ben-duoc": (
        "Địa đạo Củ Chi - Bến Dược",
        "Cu Chi Viet Cong Tunnels (10037511375).jpg",
    ),
}


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=40) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Commons API retry limit exceeded")


def plain(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def get_page(title: str) -> dict:
    query = "action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Cextmetadata%7Csize&iiurlwidth=1200&titles=" + quote("File:" + title)
    data = fetch_json(API + "?" + query)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        raise RuntimeError(f"Commons file not found: {title}")
    info = pages[0].get("imageinfo", [{}])[0]
    meta = info.get("extmetadata", {})
    license_name = plain(meta.get("LicenseShortName", {}).get("value", ""))
    license_url = plain(meta.get("LicenseUrl", {}).get("value", ""))
    artist = plain(meta.get("Artist", {}).get("value", ""))
    credit = plain(meta.get("Credit", {}).get("value", ""))
    if not license_name or not license_url:
        raise RuntimeError(f"Commons API supplied no explicit license for {title}")
    if not info.get("thumburl"):
        raise RuntimeError(f"Commons API returned no raster thumbnail for {title}")
    return {
        "page_title": pages[0]["title"],
        "source_url": "https://commons.wikimedia.org/wiki/" + quote(pages[0]["title"].replace(" ", "_"), safe="/:()_,.-"),
        "remote_url": info["thumburl"],
        "license": license_name,
        "license_url": license_url,
        "attribution": artist or "Author not stated on Commons file page",
        "credit_line": credit,
        "mime": "image/jpeg",
    }


def download(url: str, target: Path) -> tuple[int, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get_content_type()
        content = response.read()
    if not content_type.startswith("image/") or len(content) < 1024:
        raise RuntimeError(f"Unexpected image response ({content_type}, {len(content)} bytes) from {url}")
    target.write_bytes(content)
    return len(content), hashlib.sha256(content).hexdigest(), content_type


def main() -> None:
    source_rows = json.loads((ROOT / "data" / "sai_gon_places.json").read_text(encoding="utf-8"))
    rows_by_id = {row["id"]: row for row in source_rows}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for source_id, (expected_name, file_title) in CURATED_FILES.items():
        row = rows_by_id.get(source_id)
        if row is None or row.get("name") != expected_name:
            raise RuntimeError(f"Source row mismatch for {source_id}: expected {expected_name!r}")
        info = get_page(file_title)
        suffix = Path(file_title).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise RuntimeError(f"Unsupported image extension for {file_title}")
        filename = f"{source_id}{suffix}"
        target = OUTPUT_DIR / filename
        byte_count, digest, content_type = download(info["remote_url"], target)
        entries.append({
            "source_id": source_id,
            "name": expected_name,
            "local_url": f"/images/places/hcmc/{filename}",
            "local_path": target.relative_to(ROOT).as_posix(),
            "remote_url": info["remote_url"],
            "source_url": info["source_url"],
            "title": info["page_title"],
            "license": info["license"],
            "license_url": info["license_url"],
            "attribution": info["attribution"],
            "credit_line": info["credit_line"],
            "content_type": content_type,
            "byte_count": byte_count,
            "sha256": digest,
        })
        print(f"Downloaded: {expected_name} — {info['license']}")
        time.sleep(2.5)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps({"source": "Wikimedia Commons API", "entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(entries)} photos and attribution records to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
