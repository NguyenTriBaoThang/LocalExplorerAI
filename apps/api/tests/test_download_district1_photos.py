import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from download_district1_photos import (  # noqa: E402
    enrich_place_photos,
    is_allowed_commons_url,
    photo_download_url,
)


def test_commons_download_requires_https_commons_file_with_license():
    assert is_allowed_commons_url("https://upload.wikimedia.org/example.jpg")
    assert is_allowed_commons_url("https://thumb.wikimedia.org/example.jpg")
    assert not is_allowed_commons_url("http://upload.wikimedia.org/example.jpg")
    assert not is_allowed_commons_url("https://example.com/example.jpg")
    assert not is_allowed_commons_url("https://upload.wikimedia.org.example.com/example.jpg")

    photo = {
        "url": "https://upload.wikimedia.org/example.jpg",
        "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
        "license": "CC BY 4.0",
    }
    assert photo_download_url(photo) == photo["url"]


def test_enrichment_keeps_credit_and_adds_local_url_without_claiming_missing_photos(tmp_path):
    document = {
        "metadata": {"record_count": 2},
        "places": [
            {
                "ext_id": "node/12",
                "name": "Museum",
                "photo_url": "https://upload.wikimedia.org/example.jpg",
                "photos": [{
                    "url": "https://upload.wikimedia.org/example.jpg",
                    "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
                    "license": "CC BY 4.0",
                    "attribution": "Photographer",
                }],
                "details": {"images": [{
                    "url": "https://upload.wikimedia.org/example.jpg",
                    "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
                    "license": "CC BY 4.0",
                    "attribution": "Photographer",
                }]},
            },
            {"ext_id": "node/13", "name": "No photo", "photo_url": None, "photos": []},
        ],
    }

    public_dir = tmp_path / "apps" / "web" / "public" / "images" / "places" / "district1"

    def fake_fetcher(url):
        return b"fake jpeg bytes", "image/jpeg", url

    enriched, manifest = enrich_place_photos(
        document,
        root=tmp_path,
        public_dir=public_dir,
        fetcher=fake_fetcher,
    )

    assert enriched["places"][0]["local_photo_url"].startswith("/images/places/district1/")
    assert enriched["places"][0]["details"]["images"][0]["local_path"].endswith("node_12.jpg")
    assert enriched["places"][1].get("local_photo_url") is None
    assert enriched["metadata"]["local_photo_count"] == 1
    assert manifest["photo_count"] == 1
    assert manifest["entries"][0]["license"] == "CC BY 4.0"
