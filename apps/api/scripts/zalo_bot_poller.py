import os
import re
import sys
import time
from typing import Optional, List
import httpx

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.bot_service import bot_service
from app.services.ticket_service import ticket_service

POLL_TIMEOUT_SECONDS = 25
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
CANDIDATE_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]

PROD_WEB_DOMAIN = "https://www.localexplorerai.site"

CONFIRMATION_TRIGGERS = [
    "chốt", "chot", "ok", "oke", "okay", "đồng ý", "dong y", 
    "tạo vé", "tao ve", "xuất vé", "xuat ve", "lấy vé", "lay ve",
    "lên lịch", "len lich", "gửi link", "gui link", "qua web",
    "xem web", "link web", "xem link", "cho tao qua web", "cho xin link",
    "duyet", "duyệt", "được đấy", "duoc day", "chốt nha", "chot nha"
]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)
    except Exception:
        try:
            safe_msg = str(msg).encode("ascii", errors="backslashreplace").decode("ascii")
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}", flush=True)
        except Exception:
            pass


def resolve_token() -> str:
    cfg = bot_service.get_config()
    token = cfg.get("bot_token")
    if not token:
        raise RuntimeError("Zalo Bot Token not configured!")
    return str(token).strip()


def bot_url(token: str, method: str) -> str:
    return f"https://bot-api.zaloplatforms.com/bot{token}/{method}"


def delete_webhook(client: httpx.Client, token: str) -> None:
    try:
        res = client.post(bot_url(token, "deleteWebhook"), timeout=10)
        log(f"deleteWebhook -> {res.status_code} {res.text[:120]}")
    except Exception as e:
        log(f"deleteWebhook error: {e}")


def track_and_discover_members(chat_id: str, sender_name: str, text: str):
    """Keep a list of discovered member names for groups."""
    try:
        store = bot_service._read_store()
        sessions = store.get("sessions", [])
        for s in sessions:
            if s.get("id") == str(chat_id):
                members = s.get("discovered_members", [])
                if sender_name and sender_name not in members:
                    members.append(sender_name)
                # Check for mentions like @Name
                for m in re.findall(r"@([A-Za-z0-9_\s\u00C0-\u024F\u1EA0-\u1EF9]+)", text):
                    m = m.strip()
                    if m and m not in members and m.lower() not in ("bot", "bothk2t", "all"):
                        members.append(m)
                s["discovered_members"] = members
                break
        store["sessions"] = sessions
        bot_service._write_store(store)
    except Exception as e:
        log(f"Member discovery error: {e}")


def is_user_confirming_or_requesting_ticket(text: str) -> bool:
    low = text.lower().strip()
    return any(trigger in low for trigger in CONFIRMATION_TRIGGERS)


def clean_zalo_output(text: str) -> str:
    """Ensure no broken markdown links or wrong domains exist in Zalo messages."""
    # 1. Convert any hallucinated domain to live production domain
    sanitized = re.sub(r'https?://(?:www\.)?localexplorer\.ai/?', f'{PROD_WEB_DOMAIN}/', text)
    sanitized = re.sub(r'https?://localexplorerai\.site/?', f'{PROD_WEB_DOMAIN}/', sanitized)
    
    # 2. Convert markdown link [label](url) or [url](url) to just raw url
    sanitized = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', r'\2', sanitized)
    
    # 3. Clean any trailing/leading bracket attached directly to url
    sanitized = re.sub(r'(https?://[^\s\]\)\*]+)[\]\)]+', r'\1', sanitized)
    
    return sanitized.strip()


def generate_ai_reply_with_memory(chat_id: str, new_user_text: str, sender_name: str) -> str:
    cfg = bot_service.get_config()
    system_prompt = cfg.get("persona_system_prompt") or ""

    # Fetch discovered members for this chat
    store = bot_service._read_store()
    members = []
    session_info = {}
    for s in store.get("sessions", []):
        if s.get("id") == str(chat_id):
            members = s.get("discovered_members", [])
            session_info = s
            break

    member_context = ""
    if members:
        member_context = f"\n[Thông tin nhóm]: Các thành viên đã nhận diện trong nhóm này gồm: {', '.join(members)}."

    current_cleaned = re.sub(r"@Bot\s+\S+", "", new_user_text).strip()
    if not current_cleaned:
        current_cleaned = new_user_text

    wants_ticket = is_user_confirming_or_requesting_ticket(current_cleaned)

    ticket_info = None
    if wants_ticket:
        try:
            ticket_info = ticket_service.generate_ticket(
                chat_id=str(chat_id),
                customer_name=sender_name,
                intent_summary="Khám phá Sài Gòn",
                budget_vnd=session_info.get("budget_vnd") or 450000,
                group_size=len(members) if len(members) > 1 else 2
            )
        except Exception as e:
            log(f"Error generating ticket: {e}")

    if wants_ticket and ticket_info and ticket_info.get("ticket_code"):
        ticket_code = ticket_info["ticket_code"]
        ticket_url = ticket_info.get("claim_url_prod") or ticket_info["url_prod"]
        cost_str = f"{ticket_info.get('estimated_cost_vnd', 0):,} ₫"
        phase_instruction = (
            f"\n\n[GIAI ĐOẠN 2: KHÁCH ĐÃ ĐỒNG Ý / CHỐT LỊCH TRÌNH]:\n"
            f"- Khách đã yêu cầu hoặc đồng ý chốt lịch, hãy xuất Vé Điện Tử (Smart Travel Pass) ngay:\n"
            f"  + Mã vé: #{ticket_code}\n"
            f"  + Link mở trực tiếp (TEXT TRẦN, KHÔNG DÙNG NGOẶC []): {ticket_url}\n"
            f"  + Dự toán: {cost_str}\n"
            f"- QUY TẮC BẮT BUỘC:\n"
            f"  1. Gửi ĐÚNG đường dẫn text trần: {ticket_url} (Tuyệt đối KHÔNG viết cú pháp [Link]({ticket_url}) vì sẽ bị lỗi 404 trên Zalo).\n"
            f"  2. Nhắc khách: 'Bạn có thể mở xem trực tiếp lộ trình & bản đồ, hoặc bấm 1-chạm Lưu vé vào tài khoản trên web để tự động tạo tài khoản cá nhân lưu giữ vĩnh viễn!'."
        )
    else:
        phase_instruction = (
            f"\n\n[GIAI ĐOẠN 1: TƯ VẤN, GỢI Ý & HỎI Ý KIẾN KHÁCH]:\n"
            f"- TUYỆT ĐỐI CHƯA ĐƯỢC XUẤT MÃ VÉ HAY GỬI LINK VÉ vì khách chưa chốt lịch!\n"
            f"- Nhiệm vụ của bạn bây giờ:\n"
            f"  1. Hỏi thăm thành phần đoàn (cặp đôi, bạn bè, gia đình), sở thích (ẩm thực, cà phê chill, làm gốm, di sản văn hóa), thời gian rảnh và mức ngân sách dự kiến.\n"
            f"  2. Đưa ra 1 gợi ý lịch trình sơ bộ gồm 3-4 điểm đến hấp dẫn để khách/nhóm thảo luận.\n"
            f"  3. BẮT BUỘC KẾT THÚC BẰNG CÂU HỎI: Hỏi khách xem có ưng ý với lịch trình này không và có muốn em CHỐT LỊCH để xuất Mã Vé Du Lịch Thông Minh (Smart Travel Pass) cùng link bản đồ web không."
        )

    full_system = system_prompt + member_context + phase_instruction

    past_messages = bot_service.get_messages(chat_id)
    contents = []

    for msg in past_messages[-10:]:
        role = "model" if msg.get("sender_type") in ("bot", "admin") else "user"
        text = msg.get("text", "").strip()
        cleaned = re.sub(r"@Bot\s+\S+", "", text).strip()
        sender = msg.get("sender_name", "")
        if cleaned:
            contents.append({
                "role": role,
                "parts": [{"text": f"[{sender}]: {cleaned}" if role == "user" else cleaned}]
            })

    contents.append({
        "role": "user",
        "parts": [{"text": f"[{sender_name}]: {current_cleaned}"}]
    })

    payload = {
        "system_instruction": {"parts": [{"text": full_system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": float(cfg.get("temperature", 0.7)),
            "maxOutputTokens": 800,
        }
    }

    ai_reply = ""
    with httpx.Client(timeout=20.0) as ai_client:
        for model in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            try:
                res = ai_client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        reply_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if reply_text.strip():
                            log(f"Gemini AI ({model}) generated reply ({len(reply_text)} chars)")
                            ai_reply = reply_text.strip()
                            break
                log(f"Model {model} returned status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                log(f"Model {model} error: {e}")

    if not ai_reply:
        ai_reply = f"Dạ em chào {sender_name}! Em đã ghi nhận ý kiến của mình nha!"

    # Clean and sanitize Zalo formatting
    cleaned_reply = clean_zalo_output(ai_reply)

    # Fallback safety: If user explicitly asked to finalize / get ticket, ensure ticket is in reply
    if wants_ticket and ticket_info and ticket_info.get("ticket_code"):
        ticket_code = ticket_info["ticket_code"]
        clean_url = ticket_info.get("claim_url_prod") or ticket_info["url_prod"]
        if clean_url not in cleaned_reply:
            cleaned_reply += (
                f"\n\n🎫 Mã vé Smart Travel Pass: #{ticket_code}\n"
                f"🔗 Xem trực tiếp lộ trình & bản đồ: {clean_url}\n"
                f"💡 (Trên web có nút 'Lưu vé vào tài khoản' để bạn tự tạo tài khoản cá nhân lưu giữ vĩnh viễn nha!)"
            )

    return cleaned_reply


def update_customer_intake_memory(chat_id: str, text: str):
    try:
        store = bot_service._read_store()
        sessions = store.get("sessions", [])
        for s in sessions:
            if s.get("id") == str(chat_id):
                tags = s.get("interest_tags", [])
                text_low = text.lower()
                if "gom" in text_low or "gốm" in text_low:
                    if "Làm gốm thủ công" not in tags:
                        tags.append("Làm gốm thủ công")
                if "ca ngay" in text_low or "cả ngày" in text_low:
                    if "Lịch trình cả ngày" not in tags:
                        tags.append("Lịch trình cả ngày")
                if "an" in text_low or "ẩm thực" in text_low:
                    if "Ẩm thực địa phương" not in tags:
                        tags.append("Ẩm thực địa phương")
                if "200k" in text_low or "200.000" in text_low:
                    s["budget_vnd"] = 200000
                s["interest_tags"] = tags
                s["extracted_summary"] = f"Yêu cầu: {', '.join(tags)} | Ngân sách: {s.get('budget_vnd', 0):,} đ"
                break
        store["sessions"] = sessions
        bot_service._write_store(store)
    except Exception as e:
        log(f"Error updating intake memory: {e}")


def send_message(client: httpx.Client, token: str, chat_id: str, text: str) -> None:
    try:
        response = client.post(
            bot_url(token, "sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=15
        )
        log(f"sendMessage -> {response.status_code} {response.text[:120]}")
    except Exception as e:
        log(f"sendMessage error: {e}")


def handle_event(client: httpx.Client, token: str, event: dict) -> None:
    event_name = event.get("event_name", "")
    message = event.get("message") or {}
    chat = message.get("chat") or {}
    sender = (message.get("from") or {}).get("display_name") or "bạn"
    chat_id = str(chat.get("id", ""))
    chat_type = "group" if str(chat.get("chat_type", "")).upper() == "GROUP" else "private"
    text = (message.get("text") or "").strip()

    log(f"EVENT {event_name} | {chat_type} {chat_id} | {sender}: {text!r}")
    if not chat_id or event_name != "message.text.received" or not text:
        return

    # Track discovered members in group
    track_and_discover_members(chat_id, sender, text)

    bot_service.ensure_session(chat_id, chat_type, sender)
    bot_service.add_message(chat_id, "user", sender, text)
    update_customer_intake_memory(chat_id, text)

    if not bot_service.get_config().get("auto_reply_enabled", True):
        log("Auto-reply disabled in Admin; message stored only.")
        return

    reply = generate_ai_reply_with_memory(chat_id, text, sender)
    send_message(client, token, chat_id, reply)
    bot_service.add_message(chat_id, "bot", "Bot botHK2T (Tour Guide AI)", reply)


def poll_forever() -> None:
    token = resolve_token()
    with httpx.Client() as client:
        delete_webhook(client, token)
        log("Zalo AI Tour Guide (Consulting -> Confirmation -> Ticketing) is actively running...")
        while True:
            try:
                response = client.post(
                    bot_url(token, "getUpdates"),
                    json={"timeout": str(POLL_TIMEOUT_SECONDS)},
                    timeout=POLL_TIMEOUT_SECONDS + 10,
                )
                payload = response.json()
            except (httpx.TimeoutException, ValueError):
                continue
            except httpx.HTTPError as error:
                log(f"Network error: {error}; retrying in 3s")
                time.sleep(3)
                continue

            if payload.get("ok"):
                result = payload.get("result")
                events = result if isinstance(result, list) else [result]
                for event in filter(None, events):
                    try:
                        handle_event(client, token, event)
                    except Exception as error:
                        log(f"Failed to handle event: {error!r}")
                continue

            code = payload.get("error_code")
            description = payload.get("description", "")
            if code == 408:
                continue
            if "webhook" in description.lower():
                log("Webhook re-registered, deleting it again...")
                delete_webhook(client, token)
                continue
            log(f"getUpdates error: {payload}")
            time.sleep(3)


if __name__ == "__main__":
    poll_forever()
