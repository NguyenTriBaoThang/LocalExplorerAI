"""HTTP and WebSocket routes for owner-approved itinerary collaboration."""

from __future__ import annotations

import asyncio
import json
import ipaddress
import logging
import threading
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.auth_cookies import ACCESS_NAMES
from app.api.authn import authenticate_principal
from app.api.guards import public, require_user
from app.api.permissions import P
from app.auth import AuthError
from app.core.client_ip import client_ip
from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.auth_entities import AuthSession
from app.models.entities import Itinerary, User
from app.services.auth_runtime import token_service, version_checker
from app.services.itinerary_collaboration_hub import collaboration_hub
from app.services.itinerary_collaboration_service import (
    CollaborationError,
    create_invite,
    find_invite_itinerary,
    list_proposals,
    load_invite,
    proposal_summary,
    review_proposal,
    revoke_invite,
    submit_proposal,
)
from app.services.planner_service import PlannerService
from app.services.rbac_service import DbRoleMatrix


log = logging.getLogger(__name__)
router = APIRouter(tags=["Itinerary collaboration"])
_MAX_PENDING_INVITE_AUTH_PER_IP = 32
_MAX_PENDING_INVITE_AUTH_TOTAL = 256
_MAX_INVITE_AUTH_FRAME_BYTES = 8192
_pending_invite_auth_lock = threading.Lock()
_pending_invite_auth_by_ip: dict[str, int] = {}
_pending_invite_auth_total = 0


def _reserve_invite_auth_slot(client_key: str) -> bool:
    global _pending_invite_auth_total
    with _pending_invite_auth_lock:
        pending_for_ip = _pending_invite_auth_by_ip.get(client_key, 0)
        if (pending_for_ip >= _MAX_PENDING_INVITE_AUTH_PER_IP
                or _pending_invite_auth_total >= _MAX_PENDING_INVITE_AUTH_TOTAL):
            return False
        _pending_invite_auth_by_ip[client_key] = pending_for_ip + 1
        _pending_invite_auth_total += 1
        return True


def _release_invite_auth_slot(client_key: str) -> None:
    global _pending_invite_auth_total
    with _pending_invite_auth_lock:
        pending_for_ip = _pending_invite_auth_by_ip.get(client_key, 0)
        if pending_for_ip <= 0:
            return
        if pending_for_ip == 1:
            _pending_invite_auth_by_ip.pop(client_key, None)
        else:
            _pending_invite_auth_by_ip[client_key] = pending_for_ip - 1
        _pending_invite_auth_total -= 1


def _http_error(error: CollaborationError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def _optional_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User | None:
    try:
        _, user = authenticate_principal(request, response, db, required=False)
        return user
    except AuthError:
        return None


def _can_collaborate(db: Session, user: User | None) -> bool:
    return bool(
        user and user.is_active and user.role == "traveler"
        and P.ITINERARY_COLLABORATE in DbRoleMatrix(db).permissions_for(user.role)
    )


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    allowed = {item.rstrip("/") for item in settings.cors_origin_list}
    allowed.add(settings.web_app_url.rstrip("/"))
    if settings.portal_app_url:
        allowed.add(settings.portal_app_url.rstrip("/"))
    if origin.rstrip("/") in allowed:
        return True
    parts = urlsplit(origin)
    expected_scheme = "https" if websocket.url.scheme in {"wss", "https"} else "http"
    peer = websocket.client.host if websocket.client else ""
    try:
        peer_ip = ipaddress.ip_address(peer)
        trusted = any(
            peer_ip in ipaddress.ip_network(item.strip(), strict=False)
            for item in settings.trusted_proxy_ips.split(",") if item.strip()
        )
    except ValueError:
        trusted = False
    forwarded = websocket.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if trusted and forwarded in {"http", "https"}:
        expected_scheme = forwarded
    host = websocket.headers.get("host", "")
    return (
        bool(host)
        and parts.netloc == host
        and parts.scheme == expected_scheme
        and parts.path in {"", "/"}
        and not parts.query
        and not parts.fragment
    )


def _websocket_user(websocket: WebSocket, db: Session) -> User | None:
    secure = websocket.url.scheme in {"wss", "https"} or settings.app_env.lower() not in {"development", "test"}
    access_token = websocket.cookies.get(ACCESS_NAMES[0] if secure else ACCESS_NAMES[1])
    if not access_token:
        return None
    try:
        claims = token_service().verify_access(access_token)
        version_checker(db).check(claims)
        session = db.get(AuthSession, claims.sid) if claims.sid else None
        if session is not None and session.revoked_at is not None:
            return None
        user = db.get(User, claims.sub)
        return user if user is not None and user.is_active else None
    except AuthError:
        return None


def _itinerary_or_404(db: Session, itinerary_id: str) -> Itinerary:
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "ITINERARY_NOT_FOUND", "message": "Itinerary not found."})
    return itinerary


def _fresh_itinerary_snapshot(db: Session, itinerary_id: str) -> dict | None:
    try:
        return PlannerService(db).get_itinerary(itinerary_id)
    except Exception:
        log.exception("could not create a collaboration snapshot for itinerary %s", itinerary_id)
        return None


async def _send_error(websocket: WebSocket, code: str, message: str, *, close: bool = False) -> None:
    try:
        await websocket.send_json({"type": "error", "code": code, "message": message})
    except Exception:
        close = True
    if close:
        try:
            await websocket.close(code=1008, reason=message[:120])
        except Exception:
            pass


async def _broadcast_review(db: Session, result: dict) -> None:
    proposal = result["proposal"]
    await collaboration_hub.broadcast(result["itinerary_id"], {
        "type": "proposal_reviewed",
        "proposal": proposal,
        "current_version": result["current_version"],
        "error": result.get("error"),
    })
    if proposal["status"] == "approved":
        snapshot = _fresh_itinerary_snapshot(db, result["itinerary_id"])
        await collaboration_hub.broadcast(result["itinerary_id"], {
            "type": "itinerary_updated",
            "itinerary_id": result["itinerary_id"],
            "current_version": result["current_version"],
            "itinerary": snapshot,
        })


@router.post("/api/itineraries/{itinerary_id}/collaboration-invite", status_code=201)
async def create_collaboration_invite(
    itinerary_id: str,
    user: User = Depends(require_user(P.ITINERARY_SHARE)),
    db: Session = Depends(get_db),
):
    try:
        token = create_invite(db, itinerary_id, user)
    except CollaborationError as error:
        raise _http_error(error) from error
    await collaboration_hub.close_room(itinerary_id, code=4001, event={
        "type": "error", "code": "INVITE_REVOKED",
        "message": "This collaboration invite has been rotated or revoked.",
    })
    return {"invite_url": f"/collaborate/{token}", "invite_active": True}


@router.delete("/api/itineraries/{itinerary_id}/collaboration-invite", status_code=204)
async def delete_collaboration_invite(
    itinerary_id: str,
    user: User = Depends(require_user(P.ITINERARY_SHARE)),
    db: Session = Depends(get_db),
):
    try:
        revoke_invite(db, itinerary_id, user)
    except CollaborationError as error:
        raise _http_error(error) from error
    await collaboration_hub.close_room(itinerary_id, code=4001, event={
        "type": "error", "code": "INVITE_REVOKED",
        "message": "This collaboration invite has been rotated or revoked.",
    })
    return Response(status_code=204)


@router.get("/api/itineraries/{itinerary_id}/collaboration-proposals")
def get_owner_collaboration_proposals(
    itinerary_id: str,
    user: User = Depends(require_user(P.ITINERARY_COLLABORATE)),
    db: Session = Depends(get_db),
):
    itinerary = _itinerary_or_404(db, itinerary_id)
    if itinerary.user_id != user.id or user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "Only the owner can review proposals."})
    return {
        "invite_active": itinerary.collaboration_token_hash is not None,
        "current_version": itinerary.current_version,
        "proposals": [proposal_summary(item) for item in list_proposals(db, itinerary.id)],
    }


@router.get("/api/collaborations/{token}", dependencies=[Depends(public("the unguessable collaboration invite is the credential"))])
def get_collaboration_invite(
    token: str,
    response: Response,
    user: User | None = Depends(_optional_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        itinerary, snapshot = load_invite(db, token)
    except CollaborationError as error:
        raise _http_error(error) from error
    return {
        "itinerary": snapshot,
        "current_version": itinerary.current_version,
        "proposals": [proposal_summary(item) for item in list_proposals(db, itinerary.id)],
        "can_submit": _can_collaborate(db, user),
    }


async def _owner_websocket(websocket: WebSocket, itinerary_id: str) -> None:
    if not _origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return
    with SessionLocal() as db:
        user = _websocket_user(websocket, db)
        itinerary = db.get(Itinerary, itinerary_id)
        if (itinerary is None or user is None or user.role != "traveler"
                or user.id != itinerary.user_id or not _can_collaborate(db, user)):
            await websocket.close(code=1008, reason="An itinerary owner account is required.")
            return
    await collaboration_hub.connect(itinerary_id, websocket)
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except WebSocketDisconnect:
                break
            except (json.JSONDecodeError, ValueError):
                await _send_error(websocket, "INVALID_MESSAGE", "Send a valid JSON command.")
                continue
            if not isinstance(message, dict):
                await _send_error(websocket, "INVALID_MESSAGE", "A command must be a JSON object.")
                continue
            if message.get("type") != "review_proposal":
                await _send_error(websocket, "UNSUPPORTED_COMMAND", "The owner socket accepts review_proposal commands.")
                continue
            with SessionLocal() as db:
                user = _websocket_user(websocket, db)
                itinerary = db.get(Itinerary, itinerary_id)
                if (itinerary is None or user is None or user.role != "traveler"
                        or user.id != itinerary.user_id or not _can_collaborate(db, user)):
                    await _send_error(websocket, "OWNER_ACCESS_REQUIRED", "Only the signed-in itinerary owner can review proposals.", close=True)
                    break
                proposal_id, decision = message.get("proposal_id"), message.get("decision")
                if not isinstance(proposal_id, str) or decision not in {"approve", "reject"}:
                    await _send_error(websocket, "INVALID_REVIEW_COMMAND", "Review commands need a proposal_id and approve or reject decision.")
                    continue
                try:
                    result = review_proposal(db, itinerary_id, user, proposal_id, decision)
                except CollaborationError as error:
                    await _send_error(websocket, error.code, error.message)
                    continue
                await _broadcast_review(db, result)
    finally:
        await collaboration_hub.disconnect(itinerary_id, websocket)


async def _invite_websocket(websocket: WebSocket) -> None:
    if not _origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return

    client_key = client_ip(websocket, settings.trusted_proxy_ips)
    if not _reserve_invite_auth_slot(client_key):
        await websocket.close(code=1013, reason="Too many pending collaboration connections.")
        return

    auth_slot_reserved = True
    # Keep the bearer token out of the handshake URL: Uvicorn's WebSocket
    # protocol logger includes that URL even when access logging is disabled.
    room_id: str | None = None
    try:
        await websocket.accept()
        try:
            auth_event = await asyncio.wait_for(websocket.receive(), timeout=10)
        except WebSocketDisconnect:
            return
        except asyncio.TimeoutError:
            await _send_error(websocket, "INVITE_AUTH_REQUIRED", "Authenticate this collaboration socket first.", close=True)
            return
        if auth_event.get("type") == "websocket.disconnect":
            return
        auth_message = auth_event.get("text")
        if not isinstance(auth_message, str) or len(auth_message.encode("utf-8")) > _MAX_INVITE_AUTH_FRAME_BYTES:
            await _send_error(websocket, "INVITE_AUTH_REQUIRED", "Send a small text authentication frame first.", close=True)
            return
        try:
            auth_payload = json.loads(auth_message)
        except (json.JSONDecodeError, ValueError):
            auth_payload = None
        token = auth_payload.get("token") if isinstance(auth_payload, dict) and auth_payload.get("type") == "authenticate" else None
        if not isinstance(token, str) or not token:
            await _send_error(websocket, "INVITE_AUTH_REQUIRED", "Authenticate this collaboration socket first.", close=True)
            return

        with SessionLocal() as db:
            try:
                itinerary = find_invite_itinerary(db, token, lock=True)
            except CollaborationError:
                await _send_error(websocket, "INVITE_REVOKED", "This collaboration invite is invalid or revoked.", close=True)
                return
            room_id = itinerary.id
            # Hold the itinerary row lock through socket registration so revoke/rotate
            # cannot close the room first and then leave an old-token socket behind.
            await collaboration_hub.connect(room_id, websocket, announce_presence=False, accepted=True)
            db.commit()
        _release_invite_auth_slot(client_key)
        auth_slot_reserved = False
        await websocket.send_json({"type": "authenticated"})
        await collaboration_hub.broadcast_presence(room_id)
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except WebSocketDisconnect:
                break
            except (json.JSONDecodeError, ValueError):
                await _send_error(websocket, "INVALID_MESSAGE", "Send a valid JSON command.")
                continue
            if not isinstance(message, dict):
                await _send_error(websocket, "INVALID_MESSAGE", "A command must be a JSON object.")
                continue
            command = message.get("type")
            with SessionLocal() as db:
                try:
                    itinerary = find_invite_itinerary(db, token)
                except CollaborationError:
                    await _send_error(websocket, "INVITE_REVOKED", "This collaboration invite is no longer active.", close=True)
                    break
                user = _websocket_user(websocket, db)
                if command == "submit_proposal":
                    if not _can_collaborate(db, user):
                        await _send_error(websocket, "TRAVELER_ACCOUNT_REQUIRED", "Sign in with a traveler account to propose changes.", close=True)
                        break
                    base_version, stops = message.get("base_version"), message.get("stops")
                    if (not isinstance(base_version, int) or isinstance(base_version, bool)
                            or not isinstance(stops, list)):
                        await _send_error(websocket, "INVALID_PROPOSAL_COMMAND", "Proposal commands need a base_version and ordered stops.")
                        continue
                    try:
                        proposal = submit_proposal(db, itinerary.id, user, base_version, stops, invite_token=token)
                    except CollaborationError as error:
                        await _send_error(websocket, error.code, error.message)
                        continue
                    await collaboration_hub.broadcast(room_id, {
                        "type": "proposal_created",
                        "proposal": proposal_summary(proposal),
                        "current_version": itinerary.current_version,
                    })
                elif command == "review_proposal":
                    if (user is None or user.role != "traveler" or user.id != itinerary.user_id
                            or not _can_collaborate(db, user)):
                        await _send_error(websocket, "OWNER_ACCESS_REQUIRED", "Only the signed-in itinerary owner can review proposals.", close=True)
                        break
                    proposal_id, decision = message.get("proposal_id"), message.get("decision")
                    if not isinstance(proposal_id, str) or decision not in {"approve", "reject"}:
                        await _send_error(websocket, "INVALID_REVIEW_COMMAND", "Review commands need a proposal_id and approve or reject decision.")
                        continue
                    try:
                        result = review_proposal(db, itinerary.id, user, proposal_id, decision, invite_token=token)
                    except CollaborationError as error:
                        await _send_error(websocket, error.code, error.message)
                        continue
                    await _broadcast_review(db, result)
                else:
                    await _send_error(websocket, "UNSUPPORTED_COMMAND", "Use submit_proposal or review_proposal.")
    finally:
        if auth_slot_reserved:
            _release_invite_auth_slot(client_key)
        if room_id is not None:
            await collaboration_hub.disconnect(room_id, websocket)


@router.websocket("/api/itineraries/{itinerary_id}/collaboration/ws")
async def owner_collaboration_socket(websocket: WebSocket, itinerary_id: str) -> None:
    await _owner_websocket(websocket, itinerary_id)


@router.websocket("/api/collaborations/ws")
async def invite_collaboration_socket(websocket: WebSocket) -> None:
    await _invite_websocket(websocket)
