"""Minimal SignalWire SMS client kept at the provider boundary.

SignalWire exposes a Twilio-compatible "Compatibility API" (LaML). Outbound
messages are a form-encoded POST to the account's Messages endpoint using HTTP
Basic auth (project id + API token).
"""

import httpx

from app.config import Settings


class SignalWireConfigurationError(RuntimeError):
    """Raised when SMS delivery is attempted before SignalWire is configured."""


def _messages_url(settings: Settings) -> str:
    return (
        f"https://{settings.signalwire_space_url}"
        f"/api/laml/2010-04-01/Accounts/{settings.signalwire_project_id}/Messages.json"
    )


async def send_sms(*, settings: Settings, to: str, text: str) -> str:
    """Send one plain-text SMS and return SignalWire's message SID.

    Never log the API token or complete message content here: messages may
    contain personal financial information.
    """
    if not settings.signalwire_configured:
        raise SignalWireConfigurationError("SignalWire SMS is not configured.")

    assert settings.signalwire_project_id is not None  # narrowed by signalwire_configured
    assert settings.signalwire_api_token is not None
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _messages_url(settings),
            auth=(
                settings.signalwire_project_id,
                settings.signalwire_api_token.get_secret_value(),
            ),
            data={"From": settings.signalwire_from_number, "To": to, "Body": text[:1600]},
        )
    response.raise_for_status()
    payload = response.json()
    return str(payload["sid"])
