"""Adapt previously imported SQLite catalog rows for a local demo; dry-run by default.

Does not import accounts, approve evidence, invent slots, or change production defaults.
Run with --source <old local_explorer.db> [--apply]. Back up the target DB first.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))

from sqlalchemy import select
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import Experience, POI
from app.services.evidence_service import entity_is_operationally_verified

NOTICE = 'Dữ liệu chuyển từ bản cũ để demo; giá và khung giờ chỉ tham khảo, không dùng đặt chỗ thật.'


def identity(table, value):
    return value if len(value) <= 36 else str(uuid5(NAMESPACE_URL, f'MLAI_DA/{table}/{value}'))


def normalized(value):
    value = re.sub(r'\([^)]*\)', '', value).replace('đ', 'd').replace('Đ', 'D')
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def photo_index():
    index = {}
    osm = json.loads((ROOT / 'data/raw/district1_osm_places_with_local_photos.json').read_text(encoding='utf-8'))
    commons = json.loads((ROOT / 'data/raw/hcmc_commons_photo_manifest.json').read_text(encoding='utf-8'))
    for row in osm['places']:
        photos = row.get('photos', [])
        for photo in photos:
            url = photo.get('local_url', '')
            if url.startswith('/images/places/') and '..' not in url and (ROOT / 'apps/web/public' / url.lstrip('/')).is_file():
                index.setdefault(normalized(row['name']), []).append(photo)
    for photo in commons['entries']:
        url = photo.get('local_url', '')
        if url.startswith('/images/places/') and '..' not in url and (ROOT / 'apps/web/public' / url.lstrip('/')).is_file():
            index.setdefault(normalized(photo['name']), []).append(photo)
    return index


def adapt_poi(db, poi, source, photos):
    """Keep old metadata; only downgrade unverifiable legacy publication to demo."""
    details = dict(poi.details or {})
    if 'legacy_import' in details:
        return False
    details['legacy_import'] = {
        'source': 'MLAI_DA', 'verification_status': source['verification_status'],
        'image_urls': list(poi.image_urls or []),
    }
    facts = details.get('venue_facts') or {}
    urls = details.get('source_urls') or {}
    source_url = details.get('source_url') or urls.get('venue_official') or facts.get('facts_source') or urls.get('openstreetmap')
    if not poi.source_url and isinstance(source_url, str) and source_url.startswith('https://'):
        poi.source_url = source_url[:1000]
    hours = facts.get('public_hours') or details.get('opening_hours')
    if not poi.opening_hours and isinstance(hours, str):
        poi.opening_hours = hours[:200]
    fee_note = facts.get('fee_note')
    if not poi.ticket_info and isinstance(fee_note, str):
        poi.ticket_info = fee_note[:200]
    if not poi.tags:
        poi.tags = sorted({tag for exp in poi.experiences for tag in (exp.intent_tags or [])})
    if source['verification_status'] == 'verified' and not entity_is_operationally_verified(db, 'poi', poi):
        poi.verification_status = 'simulated'
        details['demo_notice'] = NOTICE
        # This sentence was a legacy assertion, not independently verified evidence.
        if poi.description.startswith('Điểm đến đã kiểm chứng:'):
            details['legacy_import']['description'] = poi.description
            poi.description = 'Địa điểm tham khảo: ' + poi.name
    matching = photos.get(normalized(poi.name), [])
    if matching:
        existing = details.get('images') or []
        details['images'] = matching + [p for p in existing if p.get('local_url') not in {m['local_url'] for m in matching}]
        poi.image_urls = list(dict.fromkeys([p['local_url'] for p in matching] + (poi.image_urls or [])))
    poi.details = details
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = make_url(settings.database_url)
    if settings.app_env not in {'development', 'test'} or url.host not in {'localhost', '127.0.0.1'}:
        parser.error('Only a local development database is supported')
    source = sqlite3.connect(f'file:{args.source.resolve().as_posix()}?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    photos = photo_index()
    report = {'pois_adapted': 0, 'experiences_to_demo': 0, 'photos_linked': 0}
    with SessionLocal() as db:
        for row in source.execute('SELECT id, name, verification_status FROM pois'):
            poi = db.get(POI, identity('pois', row['id']))
            if poi is None or poi.name != row['name']:
                raise ValueError(f'Imported place missing or changed: {row["id"]}')
            if adapt_poi(db, poi, row, photos):
                report['pois_adapted'] += 1
                report['photos_linked'] += bool(photos.get(normalized(poi.name)))
        for row in source.execute("SELECT id FROM experiences WHERE verification_status='verified'"):
            exp = db.get(Experience, identity('experiences', row['id']))
            if exp is None:
                raise ValueError(f'Imported experience missing: {row["id"]}')
            if exp.verification_status == 'verified' and not entity_is_operationally_verified(db, 'experience', exp):
                details = dict(exp.poi.details)
                legacy = dict(details['legacy_import'])
                legacy['experience_statuses'] = {**legacy.get('experience_statuses', {}), exp.id: exp.verification_status}
                details['legacy_import'] = legacy
                exp.poi.details = details
                exp.verification_status = 'simulated'
                report['experiences_to_demo'] += 1
        db.flush()
        if args.apply:
            db.commit()
        else:
            db.rollback()
    source.close()
    print(json.dumps({'applied': args.apply, **report}, ensure_ascii=False))


if __name__ == '__main__':
    main()
