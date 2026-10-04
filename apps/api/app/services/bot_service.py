import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

STORE_FILE = Path(__file__).resolve().parent.parent / 'bot_store.json'

DEFAULT_PERSONA = (
    'Bạn là Trợ lý Hướng dẫn viên Du lịch Thông minh (Tour Guide AI) của nền tảng Local Explorer AI tại TP. Hồ Chí Minh.\n\n'
    'Nhiệm vụ cốt lõi:\n'
    '1. Chào đón du khách nồng nhiệt, gần gũi và mến khách theo phong cách bản địa Sài Gòn.\n'
    '2. Khéo léo trò chuyện và phỏng vấn để thu thập 5 chiều thông tin quan trọng:\n'
    '   - Thành viên đoàn (Đi 1 mình, Cặp đôi, Nhóm gia đình có trẻ em/người cao tuổi, Nhóm bạn trẻ).\n'
    '   - Sở thích trải nghiệm (Ẩm thực hẻm, Cà phê di sản, Làng nghề làm gốm / giấy dó, Lịch sử văn hóa).\n'
    '   - Thời gian rảnh (Buổi sáng, buổi chiều, cả ngày hoặc nhiều ngày).\n'
    '   - Mức ngân sách dự kiến (VND) cho chuyến đi.\n'
    '   - Ràng buộc cá nhân (Ăn chay, kiêng ngọt, thích đi bộ hay cần ô tô, chống say xe).\n'
    '3. Ghi nhớ các thông tin này vào hồ sơ khách hàng (Customer Memory) để gợi ý các địa điểm POI phù hợp.\n'
    '4. Giới thiệu khách truy cập website Local Explorer AI để xem lịch trình tối ưu hóa bằng thuật toán AI.'
)

DEFAULT_CONFIG = {
    'bot_token': os.getenv("ZALO_BOT_TOKEN", ""),
    'webhook_url': os.getenv("ZALO_WEBHOOK_URL", ""),
    'secret_token': os.getenv("ZALO_WEBHOOK_SECRET", ""),
    'is_active': False,
    'auto_reply_enabled': False,
    'persona_system_prompt': DEFAULT_PERSONA,
    'ai_model': 'gemini-1.5-flash',
    'temperature': 0.7,
    'forward_to_n8n': False,
    'forward_n8n_url': os.getenv("ZALO_FORWARD_WEBHOOK_URL", ""),
}

DEFAULT_SYSTEM_SETTINGS = {
    'planner_max_stops': 6,
    'travel_penalty_scale': 1.0,
    'buffer_minutes': 20,
    'min_budget_vnd': 200000,
    'max_budget_vnd': 20000000,
    'routing_provider': "goong",
    'map_provider': 'goong',
    'goong_api_key': os.getenv("GOONG_API_KEY", ""),
    'goong_maptiles_key': os.getenv("GOONG_MAPTILES_API_KEY", ""),
    'gemini_api_key': os.getenv("GEMINI_API_KEY", ""),
    'openai_model': 'gpt-4o-mini',
    'verified_provider_boost': 1.25,
    'site_announcement': 'Chào mừng đến với Local Explorer AI - Hệ thống hỗ trợ du lịch bản địa thông minh',
    'maintenance_mode': False,
}

DEFAULT_SESSIONS = []

DEFAULT_MESSAGES = {}


class BotService:
    def __init__(self):
        self._ensure_store()

    def _ensure_store(self):
        if not STORE_FILE.exists():
            data = {
                'config': DEFAULT_CONFIG,
                'system_settings': DEFAULT_SYSTEM_SETTINGS,
                'sessions': DEFAULT_SESSIONS,
                'messages': DEFAULT_MESSAGES,
            }
            STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _read_store(self) -> Dict[str, Any]:
        self._ensure_store()
        try:
            return json.loads(STORE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {
                'config': DEFAULT_CONFIG,
                'system_settings': DEFAULT_SYSTEM_SETTINGS,
                'sessions': DEFAULT_SESSIONS,
                'messages': DEFAULT_MESSAGES,
            }

    def _write_store(self, data: Dict[str, Any]):
        STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def get_config(self) -> Dict[str, Any]:
        store = self._read_store()
        return store.get('config', DEFAULT_CONFIG)

    def update_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        store = self._read_store()
        cfg = store.get('config', DEFAULT_CONFIG)
        cfg.update(patch)
        store['config'] = cfg
        self._write_store(store)
        return cfg

    def get_system_settings(self) -> Dict[str, Any]:
        store = self._read_store()
        return store.get('system_settings', DEFAULT_SYSTEM_SETTINGS)

    def update_system_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        store = self._read_store()
        settings = store.get('system_settings', DEFAULT_SYSTEM_SETTINGS)
        settings.update(patch)
        store['system_settings'] = settings
        self._write_store(store)
        return settings

    def get_sessions(self) -> List[Dict[str, Any]]:
        store = self._read_store()
        return store.get('sessions', [])

    def get_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        store = self._read_store()
        return store.get('messages', {}).get(chat_id, [])

    def ensure_session(self, chat_id: str, chat_type: str, sender_name: str) -> Dict[str, Any]:
        """Create an admin-visible session for a Zalo chat the first time it messages the bot."""
        store = self._read_store()
        sessions = store.get('sessions', [])
        existing = next((s for s in sessions if s.get('id') == chat_id), None)
        if existing:
            return existing
        is_group = chat_type == 'group'
        session = {
            'id': chat_id,
            'chat_type': chat_type,
            'customer_name': f'Nhóm Zalo ({sender_name})' if is_group else sender_name,
            'customer_phone': '',
            'travel_party': 'group_friends' if is_group else 'unknown',
            'budget_vnd': 0,
            'interest_tags': [],
            'dietary_or_special': '',
            'extracted_summary': 'Phiên mới từ Zalo Bot – chưa trích xuất nhu cầu.',
            'last_message_at': datetime.now(timezone.utc).isoformat(),
            'message_count': 0,
            'status': 'active',
        }
        store['sessions'] = [session, *sessions]
        self._write_store(store)
        return session

    def add_message(self, chat_id: str, sender_type: str, sender_name: str, text: str):
        store = self._read_store()
        messages = store.get('messages', {})
        if chat_id not in messages:
            messages[chat_id] = []
        msg_id = f'msg-{int(time.time() * 1000)}'
        new_msg = {
            'id': msg_id,
            'sender_type': sender_type,
            'sender_name': sender_name,
            'text': text,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        messages[chat_id].append(new_msg)
        store['messages'] = messages

        # Update session last message and count
        sessions = store.get('sessions', [])
        for s in sessions:
            if s['id'] == chat_id:
                s['last_message_at'] = new_msg['created_at']
                s['message_count'] = len(messages[chat_id])
                break
        store['sessions'] = sessions
        self._write_store(store)
        return new_msg

    async def test_zalo_connection(self, token: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.get_config()
        bot_token = token or cfg.get('bot_token')
        if not bot_token:
            return {'ok': False, 'error': 'Chưa cấu hình Zalo Bot Token.'}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                me_resp = await client.get(f'https://bot-api.zaloplatforms.com/bot{bot_token}/getMe')
                me_data = me_resp.json()
            except Exception as e:
                me_data = {'ok': False, 'error': str(e)}

            try:
                hook_resp = await client.get(f'https://bot-api.zaloplatforms.com/bot{bot_token}/getWebhookInfo')
                hook_data = hook_resp.json()
            except Exception as e:
                hook_data = {'ok': False, 'error': str(e)}

        is_connected = me_data.get('ok', False)
        return {
            'ok': is_connected,
            'bot_info': me_data.get('result', {}),
            'webhook_info': hook_data.get('result', {}),
            'me_raw': me_data,
            'hook_raw': hook_data,
            'tested_at': datetime.now(timezone.utc).isoformat(),
        }

    async def sync_zalo_webhook(self, token: Optional[str] = None, webhook_url: Optional[str] = None, secret_token: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.get_config()
        bot_token = token or cfg.get('bot_token')
        url = webhook_url or cfg.get('webhook_url')
        secret = secret_token or cfg.get('secret_token')

        if not bot_token:
            return {'ok': False, 'error': 'Chưa cấu hình Zalo Bot Token.'}
        if not url:
            return {'ok': False, 'error': 'Chưa cung cấp Webhook URL.'}

        payload = {'url': url}
        if secret:
            payload['secret_token'] = secret

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f'https://bot-api.zaloplatforms.com/bot{bot_token}/setWebhook',
                    json=payload,
                )
                data = resp.json()
                if data.get('ok'):
                    self.update_config({'webhook_url': url, 'secret_token': secret})
                return data
            except Exception as e:
                return {'ok': False, 'error': str(e)}

    async def delete_zalo_webhook(self, token: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.get_config()
        bot_token = token or cfg.get('bot_token')
        if not bot_token:
            return {'ok': False, 'error': 'Chưa cấu hình Zalo Bot Token.'}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f'https://bot-api.zaloplatforms.com/bot{bot_token}/deleteWebhook')
                return resp.json()
            except Exception as e:
                return {'ok': False, 'error': str(e)}

    async def send_zalo_message(self, chat_id: str, text: str, token: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.get_config()
        bot_token = token or cfg.get('bot_token')
        if not bot_token:
            return {'ok': False, 'error': 'Chưa cấu hình Zalo Bot Token.'}

        payload = {
            'chat_id': str(chat_id),
            'text': text,
            'parse_mode': 'markdown',
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f'https://bot-api.zaloplatforms.com/bot{bot_token}/sendMessage',
                    json=payload,
                )
                data = resp.json()
                # Record into conversation history as admin message
                self.add_message(chat_id, 'admin', 'Admin Quản Trị Viên', text)
                return data
            except Exception as e:
                return {'ok': False, 'error': str(e)}

    async def test_goong_maps(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.get_system_settings()
        key = api_key or cfg.get('goong_api_key')
        if not key:
            return {'ok': False, 'error': 'Chưa cấu hình Goong API Key.'}

        start = time.time()
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(
                    'https://rsapi.goong.io/geocode',
                    params={'address': 'Chợ Bến Thành, Quận 1, TP Hồ Chí Minh', 'api_key': key}
                )
                latency_ms = int((time.time() - start) * 1000)
                data = resp.json()
                results = data.get('results', [])
                if resp.status_code == 200 and results:
                    return {
                        'ok': True,
                        'latency_ms': latency_ms,
                        'formatted_address': results[0].get('formatted_address'),
                        'location': results[0].get('geometry', {}).get('location'),
                        'status': data.get('status', 'OK'),
                    }
                return {'ok': False, 'latency_ms': latency_ms, 'data': data}
            except Exception as e:
                return {'ok': False, 'error': str(e)}


bot_service = BotService()
