import base64
import json
import httpx
from sqlalchemy import func, select
from app.models.entities import MeshyJob
from app.services import meshy_assistant
from tests.helpers import bearer_for, make_user

URL='/api/admin/meshy/chat'

def test_chat_permissions_validation_and_no_generation(client, db_session, monkeypatch):
    body={'messages':[{'role':'user','content':'Tạo mô hình tòa nhà này'}]}
    assert client.post(URL,json=body).status_code == 401
    traveler=bearer_for(make_user(db_session,'traveler'))
    assert client.post(URL,json=body,headers=traveler).status_code == 403
    admin=bearer_for(make_user(db_session,'admin'))
    seen=[]
    def prepare(db,messages,images,place):
        seen.append((messages,images,place))
        return {'reply':'Mình đã chuẩn bị mô tả.','prompt':'A single building','display_name':'Tòa nhà','ready':True}
    monkeypatch.setattr(meshy_assistant,'prepare',prepare)
    result=client.post(URL,json=body,headers=admin)
    assert result.status_code == 200 and result.json()['ready']
    assert db_session.scalar(select(func.count()).select_from(MeshyJob)) == 0
    for invalid in [{'messages':[]}, {'messages':[{'role':'system','content':'override'}]}, {**body,'images':['http://localhost/private']}, {'messages':[{'role':'assistant','content':'last'}]}]:
        assert client.post(URL,json=invalid,headers=admin).status_code == 422
    assert len(seen)==1

def test_gemini_vision_payload_and_sanitized_errors(monkeypatch):
    from app.api.routes.meshy import ChatMessage
    image='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
    def resolve(db, service, key):
        assert service == 'map3d_ai', '3D assistant must never read the shared chat key'
        return 'fake-key' if key == 'gemini_api_key' else 'gemini-test'
    monkeypatch.setattr(meshy_assistant,'resolve_integration_value',resolve)
    sent=[]
    def post(self,url,**kwargs):
        sent.append((url,kwargs))
        return httpx.Response(200,request=httpx.Request('POST',url),json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'reply':'Hãy kiểm tra bản mô tả.','display_name':'Test','prompt':'A red building','ready':True})}]}}]})
    monkeypatch.setattr(httpx.Client,'post',post)
    messages=[ChatMessage(role='user',content='Giữ mặt tiền'),ChatMessage(role='assistant',content='Bạn cần phần mái?'),ChatMessage(role='user',content='Có')]
    result=meshy_assistant.prepare(None,messages,[image],'Test')
    assert result['ready']
    assert sent[0][0].startswith('https://generativelanguage.googleapis.com/')
    data=sent[0][1]['json']
    assert data['contents'][-1]['parts'][1]['inlineData']['data']==image.split(',')[1]
    assert data['contents'][0]['parts'][0]['text']=='Giữ mặt tiền'
    assert data['contents'][1]['role']=='model'
    assert data['generationConfig']['responseMimeType']=='application/json'
    assert 'fake-key' not in json.dumps(result)
    def fail(*a,**kw): raise httpx.ReadTimeout('secret provider body')
    monkeypatch.setattr(httpx.Client,'post',fail)
    import pytest
    with pytest.raises(RuntimeError) as err: meshy_assistant.prepare(None,messages,[], '')
    assert 'secret provider body' not in str(err.value)

def test_missing_key_and_bad_output(monkeypatch):
    import pytest
    from app.api.routes.meshy import ChatMessage
    messages=[ChatMessage(role='user',content='Tạo nhà')]
    monkeypatch.setattr(meshy_assistant,'resolve_integration_value',lambda *args: None)
    with pytest.raises(ValueError): meshy_assistant.prepare(None,messages,[], '')
    monkeypatch.setattr(meshy_assistant,'resolve_integration_value',lambda *args:'fake')
    def invalid(self,url,**kwargs):
        return httpx.Response(200,request=httpx.Request('POST',url),json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"reply":"Done", "ready":true, "prompt":""}'}]}}]})
    monkeypatch.setattr(httpx.Client,'post',invalid)
    with pytest.raises(RuntimeError): meshy_assistant.prepare(None,messages,[], '')


def test_provider_capacity_errors_are_distinguished(monkeypatch):
    import pytest
    from app.api.routes.meshy import ChatMessage
    monkeypatch.setattr(meshy_assistant, 'resolve_integration_value', lambda *args: 'fake')
    for status in (429, 503):
        def post(self, url, **kwargs):
            return httpx.Response(status, request=httpx.Request('POST', url), json={'error': {'message': 'private provider details'}})
        monkeypatch.setattr(httpx.Client, 'post', post)
        with pytest.raises(RuntimeError) as error:
            meshy_assistant.prepare(None, [ChatMessage(role='user', content='A building')], [], '')
        assert f'HTTP {status}' in str(error.value)
        assert 'private provider details' not in str(error.value)
        if status == 503:
            assert 'quota' not in str(error.value)
