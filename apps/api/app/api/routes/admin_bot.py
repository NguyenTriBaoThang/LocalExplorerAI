from typing import Any, Dict, Optional
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models.entities import AuditLog, Experience, Itinerary, POI, Provider, User
from app.services.bot_service import bot_service

router = APIRouter(tags=['Admin Bot & Systems'])


class BotConfigPatch(BaseModel):
    bot_token: Optional[str] = None
    webhook_url: Optional[str] = None
    secret_token: Optional[str] = None
    is_active: Optional[bool] = None
    auto_reply_enabled: Optional[bool] = None
    persona_system_prompt: Optional[str] = None
    ai_model: Optional[str] = None
    temperature: Optional[float] = None
    forward_to_n8n: Optional[bool] = None
    forward_n8n_url: Optional[str] = None


class SystemSettingsPatch(BaseModel):
    planner_max_stops: Optional[int] = Field(default=None, ge=2, le=15)
    travel_penalty_scale: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    buffer_minutes: Optional[int] = Field(default=None, ge=5, le=120)
    min_budget_vnd: Optional[int] = None
    max_budget_vnd: Optional[int] = None
    routing_provider: Optional[str] = None
    map_provider: Optional[str] = None
    goong_api_key: Optional[str] = None
    goong_maptiles_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    verified_provider_boost: Optional[float] = None
    site_announcement: Optional[str] = None
    maintenance_mode: Optional[bool] = None


class SendMessageRequest(BaseModel):
    chat_id: str
    text: str


class SyncWebhookRequest(BaseModel):
    webhook_url: Optional[str] = None
    secret_token: Optional[str] = None


class TestConnectionRequest(BaseModel):
    bot_token: Optional[str] = None


class TestMapsRequest(BaseModel):
    goong_api_key: Optional[str] = None


# --- Bot Management Endpoints ---

@router.get('/api/admin/bot/config', dependencies=[Depends(require_admin)])
def get_bot_config():
    cfg = bot_service.get_config()
    token = cfg.get('bot_token', '')
    sensitive_fields = {'bot_token', 'secret_token', 'webhook_url', 'forward_n8n_url'}
    safe_config = {key: value for key, value in cfg.items() if key not in sensitive_fields}
    return {
        **safe_config,
        'bot_configured': bool(token),
    }


@router.post('/api/admin/bot/config', dependencies=[Depends(require_admin)])
def update_bot_config(payload: BotConfigPatch):
    patch = payload.model_dump(exclude_unset=True)
    sensitive_fields = {'bot_token', 'secret_token', 'webhook_url', 'forward_n8n_url'}
    if sensitive_fields.intersection(patch):
        raise HTTPException(status_code=422, detail='Bot tokens and webhook URLs cannot be stored in the legacy plaintext settings file. Configure them as server environment secrets.')
    updated = bot_service.update_config(patch)
    safe_config = {key: value for key, value in updated.items() if key not in sensitive_fields}
    return {'status': 'success', 'config': safe_config, 'bot_configured': bool(updated.get('bot_token'))}


@router.post('/api/admin/bot/test-connection', dependencies=[Depends(require_admin)])
async def test_bot_connection(payload: Optional[TestConnectionRequest] = None):
    token = payload.bot_token if payload else None
    result = await bot_service.test_zalo_connection(token)
    return result


@router.post('/api/admin/bot/sync-webhook', dependencies=[Depends(require_admin)])
async def sync_bot_webhook(payload: Optional[SyncWebhookRequest] = None):
    url = payload.webhook_url if payload else None
    secret = payload.secret_token if payload else None
    result = await bot_service.sync_zalo_webhook(webhook_url=url, secret_token=secret)
    return result


@router.post('/api/admin/bot/delete-webhook', dependencies=[Depends(require_admin)])
async def delete_bot_webhook():
    result = await bot_service.delete_zalo_webhook()
    return result


@router.get('/api/admin/bot/sessions', dependencies=[Depends(require_admin)])
def list_bot_sessions():
    sessions = bot_service.get_sessions()
    return sessions


@router.get('/api/admin/bot/sessions/{chat_id}/messages', dependencies=[Depends(require_admin)])
def get_bot_session_messages(chat_id: str):
    messages = bot_service.get_messages(chat_id)
    return messages


@router.post('/api/admin/bot/send-message', dependencies=[Depends(require_admin)])
async def send_bot_message(payload: SendMessageRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail='Nội dung tin nhắn không được để trống.')
    result = await bot_service.send_zalo_message(payload.chat_id, payload.text)
    return result


# --- Website System Parameters Endpoints ---

@router.get('/api/admin/system/settings', dependencies=[Depends(require_admin)])
def get_system_settings():
    current = bot_service.get_system_settings()
    secret_keys = {'goong_api_key', 'goong_maptiles_key', 'gemini_api_key'}
    safe = {key: value for key, value in current.items() if key not in secret_keys}
    safe.update({f'{key}_configured': bool(current.get(key)) for key in secret_keys})
    return safe


@router.post('/api/admin/system/settings', dependencies=[Depends(require_admin)])
def update_system_settings(payload: SystemSettingsPatch):
    patch = payload.model_dump(exclude_unset=True)
    secret_keys = {'goong_api_key', 'goong_maptiles_key', 'gemini_api_key'}
    if secret_keys.intersection(patch):
        raise HTTPException(status_code=422, detail='Store API credentials through the encrypted Integrations page.')
    updated = bot_service.update_system_settings(patch)
    return {'status': 'success', 'settings': updated}


@router.post('/api/admin/system/test-maps', dependencies=[Depends(require_admin)])
async def test_maps_connection(payload: Optional[TestMapsRequest] = None):
    key = payload.goong_api_key if payload else None
    result = await bot_service.test_goong_maps(key)
    return result


@router.get('/api/admin/system/metrics', dependencies=[Depends(require_admin)])
def get_system_metrics(db: Session = Depends(get_db)):
    user_count = db.scalar(select(func.count(User.id))) or 0
    provider_count = db.scalar(select(func.count(Provider.id))) or 0
    poi_count = db.scalar(select(func.count(POI.id))) or 0
    poi_verified = db.scalar(select(func.count(POI.id)).where(POI.verification_status == 'verified')) or 0
    experience_count = db.scalar(select(func.count(Experience.id))) or 0
    itinerary_count = db.scalar(select(func.count(Itinerary.id))) or 0
    audit_count = db.scalar(select(func.count(AuditLog.id))) or 0

    sessions = bot_service.get_sessions()
    total_messages = sum(s.get('message_count', 0) for s in sessions)

    return {
        'users_total': user_count,
        'providers_total': provider_count,
        'pois_total': poi_count,
        'pois_verified': poi_verified,
        'experiences_total': experience_count,
        'itineraries_created': itinerary_count,
        'audit_logs_count': audit_count,
        'bot_sessions_total': len(sessions),
        'bot_messages_total': total_messages,
        'feasibility_success_rate': None,
        'feasibility_metric_available': False,
    }


# --- Direct Zalo Bot Webhook Receiver ---

@router.get('/api/bot/webhook')
def verify_zalo_webhook():
    return {'status': 'ok', 'service': 'Local Explorer AI - Zalo Bot Webhook'}


@router.post('/api/bot/webhook')
async def handle_zalo_webhook(request: Request, x_bot_api_secret_token: Optional[str] = Header(default=None)):
    body = await request.json()
    cfg = bot_service.get_config()
    expected_secret = cfg.get('secret_token')

    if not expected_secret:
        raise HTTPException(status_code=503, detail='Webhook secret is not configured.')
    if not x_bot_api_secret_token or not secrets.compare_digest(x_bot_api_secret_token, expected_secret):
        raise HTTPException(status_code=403, detail='Invalid secret token.')

    # Process incoming message
    message = body.get('message', {})
    chat = message.get('chat', {})
    chat_id = str(chat.get('id', ''))
    from_user = message.get('from', {})
    user_name = from_user.get('first_name') or from_user.get('username') or 'Du khách'
    text = message.get('text', '')

    if chat_id and text:
        bot_service.add_message(chat_id, 'user', user_name, text)

        # Forward to n8n if enabled
        if cfg.get('forward_to_n8n') and cfg.get('forward_n8n_url'):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=3.0) as client:
                    await client.post(cfg['forward_n8n_url'], json=body)
            except Exception:
                pass

    return {'status': 'processed'}
