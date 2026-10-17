import json
import struct
from uuid import uuid4
from datetime import timedelta
import httpx
import pytest
from sqlalchemy import select
from app.models.entities import MeshyJob
from app.services import meshy
from app.core.config import settings
from tests.helpers import bearer_for, make_user

URL = "/api/admin/meshy/jobs"

def payload(**kw):
    return {"request_key": str(uuid4()), "display_name": "Test model", "prompt": "a small building", "latitude": 10.77, "longitude": 106.69, "max_credits": 20, **kw}

def glb(doc=None):
    data = json.dumps(doc or {"asset": {"version": "2.0"}}).encode()
    data += b' ' * ((-len(data)) % 4)
    return b'glTF' + struct.pack('<IIII', 2, 20+len(data), len(data), 0x4E4F534A) + data

@pytest.fixture
def mocked(monkeypatch, tmp_path, db_session):
    monkeypatch.setattr(settings, 'meshy_storage_dir', str(tmp_path))
    monkeypatch.setattr(meshy, 'key', lambda db: 'test-key-not-real')
    calls = []
    def request(db, method, path, data=None):
        calls.append((method, path, data))
        return {"result": str(uuid4())}
    monkeypatch.setattr(meshy, 'request', request)
    return calls

def test_generation_budget_idempotency_permissions(client, db_session, mocked, monkeypatch):
    body = payload()
    assert client.post(URL, json=body).status_code == 401
    traveler = bearer_for(make_user(db_session, 'traveler'))
    assert client.post(URL, json=body, headers=traveler).status_code == 403
    headers = bearer_for(make_user(db_session, 'admin'))
    first = client.post(URL, json=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()['status'] == 'pending'
    assert client.post(URL, json=body, headers=headers).json()['id'] == first.json()['id']
    assert len(mocked) == 1
    monkeypatch.setattr(settings, 'meshy_daily_credits', 20)
    assert client.post(URL, json=payload(), headers=headers).status_code == 429
    assert len(mocked) == 1

def test_private_preview_publication_and_unpublish(client, db_session, mocked):
    headers = bearer_for(make_user(db_session, 'admin'))
    job = client.post(URL, json=payload(), headers=headers).json()
    row = db_session.get(MeshyJob, job['id'])
    row.status = 'ready'; db_session.commit()
    path = meshy.asset(row.id); path.parent.mkdir(); path.write_bytes(glb())
    public = f'/api/meshy/jobs/{row.id}/asset'
    assert client.get(public).status_code == 404
    assert 'meshy-' + row.id not in client.get('/api/models-3d/calibration').json()
    assert client.get(f'{URL}/{row.id}/asset').status_code == 401
    assert client.post(f'{URL}/{row.id}/publish', headers=headers).status_code == 409
    assert client.get(f'{URL}/{row.id}/asset', headers=headers).status_code == 200
    assert client.post(f'{URL}/{row.id}/previewed', headers=headers).status_code == 200
    assert client.post(f'{URL}/{row.id}/publish', headers=headers).status_code == 200
    assert client.get(public).status_code == 200
    cal = client.get('/api/models-3d/calibration').json()['meshy-' + row.id]
    assert 'prompt' not in cal and 'actor_id' not in cal
    assert client.get('/api/landmark-stories/meshy-' + row.id).status_code == 200
    assert client.post(f'{URL}/{row.id}/unpublish', headers=headers).status_code == 200
    assert client.get(public).status_code == 404

def test_refine_never_bills_twice(client, db_session, mocked):
    headers = bearer_for(make_user(db_session, 'admin'))
    job = client.post(URL, json=payload(), headers=headers).json()
    row = db_session.get(MeshyJob, job['id']); row.status = 'ready'; db_session.commit()
    route = f'{URL}/{row.id}/refine'
    a = client.post(route, json={'request_key': str(uuid4()), 'max_credits': 10}, headers=headers)
    b = client.post(route, json={'request_key': str(uuid4()), 'max_credits': 10}, headers=headers)
    assert a.status_code == b.status_code == 200
    assert a.json()['id'] == b.json()['id']
    assert len(mocked) == 2
    assert mocked[-1][2]['preview_task_id'] == row.task_id

def test_uncertain_post_is_not_replayed(client, db_session, mocked, monkeypatch):
    def fail(*a): raise httpx.ReadTimeout('hidden upstream detail')
    monkeypatch.setattr(meshy, 'request', fail)
    headers = bearer_for(make_user(db_session, 'admin')); body = payload()
    a = client.post(URL, json=body, headers=headers)
    assert a.json()['status'] == 'uncertain'
    assert 'hidden upstream detail' not in a.text
    assert client.post(URL, json=body, headers=headers).json()['id'] == a.json()['id']

def test_input_and_asset_validation(client, db_session, mocked):
    headers = bearer_for(make_user(db_session, 'admin'))
    for invalid in [payload(latitude=100), payload(kind='image', images=['https://127.0.0.1/key']), payload(max_credits=0)]:
        assert client.post(URL, json=invalid, headers=headers).status_code == 422
    assert not mocked
    for data in [b'bad', glb({'buffers':[{'uri':'https://evil.invalid/x'}]}), glb({'images':[{'uri':'../file'}]})]:
        with pytest.raises(ValueError): meshy.validate_glb(data)
    meshy.validate_glb(glb())
    with pytest.raises(ValueError): meshy.download('http://127.0.0.1/secret', str(uuid4()))

def test_poll_restart_download_and_resume(db_session, monkeypatch, mocked, client):
    headers = bearer_for(make_user(db_session, 'admin'))
    job = client.post(URL, json=payload(), headers=headers).json()
    # Give the worker a new Session connected to the same fixture database.
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(meshy, 'SessionLocal', sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    monkeypatch.setattr(meshy, 'request', lambda *a: {'status':'SUCCEEDED','progress':100,'model_urls':{'glb':'https://assets.meshy.ai/test'}})
    def download(url, job_id):
        path=meshy.asset(job_id); path.parent.mkdir(exist_ok=True); path.write_bytes(glb())
    monkeypatch.setattr(meshy, 'download', download)
    meshy.tick(); db_session.expire_all()
    assert db_session.get(MeshyJob, job['id']).status == 'ready'
    row = db_session.get(MeshyJob, job['id']); row.status='pending'; row.created_at=meshy.now()-timedelta(hours=3); db_session.commit()
    meshy.tick(); db_session.expire_all()
    assert db_session.get(MeshyJob, job['id']).status == 'timeout'
    assert client.post(f'{URL}/{row.id}/resume', headers=headers).status_code == 200
    meshy.tick(); db_session.expire_all()
    assert db_session.get(MeshyJob, job['id']).status == 'ready'

def test_image_request_and_reconcile(client, db_session, mocked, monkeypatch):
    import base64
    headers = bearer_for(make_user(db_session, 'admin'))
    image = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'fixture').decode()
    response = client.post(URL, json=payload(kind='image', images=[image], max_credits=30), headers=headers)
    assert response.status_code == 200, response.text
    assert mocked[-1][1] == '/openapi/v1/multi-image-to-3d'
    assert mocked[-1][2]['image_urls'] == [image]
    row = db_session.get(MeshyJob, response.json()['id'])
    assert 'images' not in row.metadata_json
    row.status = 'uncertain'; row.task_id = None; db_session.commit()
    task_id = str(uuid4())
    monkeypatch.setattr(meshy, 'request', lambda *a: {'type': 'text-to-3d-preview'})
    assert client.post(f'{URL}/{row.id}/reconcile', json={'task_id':task_id}, headers=headers).status_code == 422
    monkeypatch.setattr(meshy, 'request', lambda *a: {'type': 'multi-image-to-3d'})
    restored = client.post(f'{URL}/{row.id}/reconcile', json={'task_id':task_id}, headers=headers)
    assert restored.status_code == 200
    assert restored.json()['task_id'] == task_id
    assert restored.json()['status'] == 'pending'
