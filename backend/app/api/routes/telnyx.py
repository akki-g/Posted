"""Inbound Telnyx SMS webhook.

Telnyx posts inbound messages as JSON `message.received` events and signs
each request with an Ed25519 signature. See `app.services.telnyx_signature`
for the verified construction.
"""

import json

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status

from app.api.deps import get_app_settings
from app.config import Settings
from app.services.sms import process_inbound_sms
from app.services.telnyx_signature import InvalidTelnyxSignatureError, verify_telnyx_request

router = APIRouter(prefix="/webhooks/telnyx", tags=["telnyx"])
logger = structlog.get_logger()


def _unsigned_webhooks_allowed(settings: Settings) -> bool:
    return settings.telnyx_allow_unsigned_webhooks and settings.app_env == "development"


async def _process_message(request: Request, *, from_number: str, body: str) -> None:
    async with request.app.state.session_factory() as session:
        await process_inbound_sms(
            session,
            from_number=from_number,
            body=body,
            settings=get_app_settings(request),
        )


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    settings = get_app_settings(request)

    raw_body = await request.body()
    try:
        event = json.loads(raw_body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed Telnyx webhook body.",
        ) from exc

    if not _unsigned_webhooks_allowed(settings):
        try:
            verify_telnyx_request(
                public_key=settings.telnyx_public_key or "",
                headers=request.headers,
                raw_body=raw_body,
            )
        except InvalidTelnyxSignatureError as exc:
            logger.warning("telnyx_signature_rejected", reason=str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telnyx signature.",
            ) from exc

    data = event.get("data") if isinstance(event, dict) else None
    if not isinstance(data, dict) or data.get("event_type") != "message.received":
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    payload = data.get("payload") or {}
    from_number = (payload.get("from") or {}).get("phone_number")
    body = payload.get("text")
    if not from_number or not body:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    background_tasks.add_task(_process_message, request, from_number=from_number, body=body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
