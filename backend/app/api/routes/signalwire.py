"""Inbound SignalWire SMS webhook.

SignalWire posts inbound messages as application/x-www-form-urlencoded (the
Twilio-compatible LaML shape) and signs the request the same way Twilio signs
LaML requests. See `app.services.signalwire_signature` for the verified
construction and the diagnostic sweep used while pinning down the exact
scheme in production.
"""

from urllib.parse import parse_qsl

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status

from app.api.deps import get_app_settings
from app.config import Settings
from app.services.signalwire_signature import (
    InvalidSignalWireSignatureError,
    verify_signalwire_request,
)
from app.services.sms import process_inbound_sms

router = APIRouter(prefix="/webhooks/signalwire", tags=["signalwire"])
logger = structlog.get_logger()


def _unsigned_webhooks_allowed(settings: Settings) -> bool:
    return settings.signalwire_allow_unsigned_webhooks and settings.app_env == "development"


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
        raw_body_text = raw_body.decode("utf-8")
        form_fields = tuple(
            parse_qsl(
                raw_body_text,
                keep_blank_values=True,
                encoding="utf-8",
                errors="strict",
            )
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed SignalWire webhook body.",
        ) from exc

    if not _unsigned_webhooks_allowed(settings):
        # SignalWire signs the public URL it delivered to; behind a reverse
        # proxy request.url is not that URL, so prefer the configured one.
        configured_url = settings.signalwire_webhook_url or str(request.url)
        token = (
            settings.signalwire_api_token.get_secret_value()
            if settings.signalwire_api_token
            else ""
        )
        try:
            verify_signalwire_request(
                token=token,
                configured_url=configured_url,
                request_url=str(request.url),
                form_fields=form_fields,
                headers=request.headers,
                configured_project_id=settings.signalwire_project_id,
                raw_body=raw_body,
                enable_diagnostics=settings.signalwire_signature_diagnostics,
            )
        except InvalidSignalWireSignatureError as exc:
            details = exc.details
            logger.warning(
                "signalwire_signature_rejected",
                header_names=details.header_names,
                header_lengths=dict(details.header_lengths),
                matched_variants=(
                    [
                        {
                            "header": match.header_name,
                            "candidate": match.candidate_name,
                            "algorithm": match.algorithm,
                            "encoding": match.encoding,
                        }
                        for match in details.matched_variants
                    ]
                    or "NONE"
                ),
                account_sid_matches_project=details.account_sid_matches_project,
                configured_url_matches_request_url=details.configured_url_matches_request_url,
                duplicate_parameter_keys=details.duplicate_parameter_keys,
                parameter_keys=details.parameter_keys,
                configured_url=configured_url,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid SignalWire signature.",
            ) from exc

    params = dict(form_fields)
    from_number = params.get("From")
    body = params.get("Body")
    # Status callbacks and other events lack a message body; ignore them.
    if not from_number or not body:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    background_tasks.add_task(_process_message, request, from_number=from_number, body=body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
