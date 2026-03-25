from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import settings
from .logging_utils import setup_logging
from .rtms_client_manager import RtmsClientManager
from .store import InMemoryStateStore
from .webhook_security import compute_plain_token_hmac, compute_zoom_signature

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

store = InMemoryStateStore()
rtms_manager = RtmsClientManager(
    store=store,
    recordings_root=settings.recordings_dir,
    sample_rate=settings.audio_sample_rate,
    channels=settings.audio_channels,
    sample_width_bytes=settings.audio_sample_width_bytes,
    zoom_client_id=settings.zoom_client_id,
    zoom_client_secret=settings.zoom_client_secret,
)

app = FastAPI(title=settings.app_name)


def _extract_rtms_payload(body: dict[str, Any]) -> tuple[str, str, str] | None:
    payload = body.get("payload") or {}
    obj = payload.get("object") or payload
    meeting_uuid = obj.get("meeting_uuid") or obj.get("meetingUuid")
    stream_id = obj.get("rtms_stream_id") or obj.get("rtmsStreamId")
    server_urls = obj.get("server_urls") or obj.get("serverUrls")
    if not (meeting_uuid and stream_id and server_urls):
        return None
    return str(meeting_uuid), str(stream_id), str(server_urls)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
def state() -> dict[str, Any]:
    return store.snapshot()


@app.post(settings.webhook_path)
async def webhook(request: Request) -> JSONResponse:
    body = await request.json()
    event = body.get("event", "")

    if event == "endpoint.url_validation":
        plain_token = (body.get("payload") or {}).get("plainToken")
        if not plain_token:
            raise HTTPException(status_code=400, detail="Missing plainToken")
        encrypted = compute_plain_token_hmac(settings.zoom_webhook_secret_token, plain_token)
        logger.info("endpoint validation handled")
        return JSONResponse(content={"plainToken": plain_token, "encryptedToken": encrypted})

    signature = request.headers.get("x-zm-signature")
    timestamp = request.headers.get("x-zm-request-timestamp")
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing Zoom signature headers")

    expected_signature = compute_zoom_signature(settings.zoom_webhook_secret_token, timestamp, body)
    if not hmac_compare(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info("webhook received", extra={"event": event})

    if event == "meeting.rtms_started":
        extracted = _extract_rtms_payload(body)
        if extracted:
            meeting_uuid, stream_id, server_urls = extracted
            store.update_meeting_rtms(meeting_uuid, stream_id, server_urls)
            rtms_manager.handle_rtms_started(meeting_uuid, stream_id, server_urls)
        else:
            logger.warning("meeting.rtms_started missing fields")

    elif event == "meeting.rtms_stopped":
        extracted = _extract_rtms_payload(body)
        if extracted:
            meeting_uuid, _, _ = extracted
            rtms_manager.handle_rtms_stopped(meeting_uuid)

    return JSONResponse(content={"ok": True})


def hmac_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
