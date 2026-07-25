"""Inbound SignalWire SMS webhook.

SignalWire posts inbound messages as application/x-www-form-urlencoded (the
Twilio-compatible LaML shape) and signs the request with an HMAC-SHA1 header,
`X-SignalWire-Signature`. The signed string is the exact request URL followed
by each POST parameter sorted by key and concatenated as key+value.
"""

import base64
import hashlib
import hmac

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status

from app.api.deps import get_app_settings
from app.config import Settings
from app.services.sms import process_inbound_sms

router = APIRouter(prefix="/webhooks/signalwire", tags=["signalwire"])
logger = structlog.get_logger()


def _expected_signature(*, url: str, params: dict[str, str], token: str) -> str:
    data = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def verify_signalwire_signature(
    *, url: str, params: dict[str, str], signature: str | None, settings: Settings
) -> None:
    """Verify the Twilio-compatible `X-SignalWire-Signature` HMAC-SHA1 header."""
    if settings.signalwire_allow_unsigned_webhooks and settings.app_env == "development":
        return
    if not settings.signalwire_api_token or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing SignalWire signature."
        )
    expected = _expected_signature(
        url=url, params=params, token=settings.signalwire_api_token.get_secret_value()
    )
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SignalWire signature."
        )


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
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    # SignalWire signs the public URL it delivered to; behind a tunnel that is
    # not request.url, so prefer the configured public webhook URL when set.
    url = settings.signalwire_webhook_url or str(request.url)
    signature = request.headers.get("x-signalwire-signature")
    try:
        verify_signalwire_signature(
            url=url,
            params=params,
            signature=signature,
            settings=settings,
        )
    except HTTPException:
        # PII-safe rejection diagnostic (kept intentionally): on a rejected signature,
        # report which signing string/algorithm/encoding (if any) the configured
        # api_token can reproduce, so a production 401 is diagnosable without a debug
        # session. If nothing matches, either SignalWire is signing with a different
        # secret than the REST api_token, or SIGNALWIRE_WEBHOOK_URL does not exactly
        # match the public URL SignalWire signed. Never logs headers, message bodies,
        # or the raw signature.
        token = (
            settings.signalwire_api_token.get_secret_value()
            if settings.signalwire_api_token
            else ""
        )
        sorted_join = "".join(k + params[k] for k in sorted(params))
        order_join = "".join(k + params[k] for k in params)
        candidates = {
            "configured_sorted": url + sorted_join,
            "configured_slash_sorted": url + "/" + sorted_join,
            "request_sorted": str(request.url) + sorted_join,
            "configured_order": url + order_join,
            "url_only": url,
        }
        matches = []
        for name, data in candidates.items():
            for algo in ("sha1", "sha256"):
                digest = hmac.new(token.encode(), data.encode("utf-8"), algo).digest()
                if base64.b64encode(digest).decode() == signature:
                    matches.append(f"{name}/{algo}/base64")
                if digest.hex() == signature:
                    matches.append(f"{name}/{algo}/hex")
        logger.warning(
            "signalwire_signature_rejected",
            matched_variants=matches or "NONE",
            param_keys=sorted(params),
            configured_url=url,
        )
        raise

    from_number = params.get("From")
    body = params.get("Body")
    # Status callbacks and other events lack a message body; ignore them.
    if not from_number or not body:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    background_tasks.add_task(_process_message, request, from_number=from_number, body=body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
