"""Minimal Telnyx SMS client kept at the provider boundary.

Telnyx's Messaging API v2 is a plain JSON REST API: outbound messages are a
POST to /v2/messages with a bearer-token Authorization header.
"""

import httpx

from app.config import Settings

MESSAGES_URL = "https://api.telnyx.com/v2/messages"


class TelnyxConfigurationError(RuntimeError):
    """Raised when SMS delivery is attempted before Telnyx is configured."""


async def send_sms(*, settings: Settings, to: str, text: str) -> str:
    """Send one plain-text SMS and return Telnyx's message id.

    Never log the API key or complete message content here: messages may
    contain personal financial information.
    """
    if not settings.telnyx_configured:
        raise TelnyxConfigurationError("Telnyx SMS is not configured.")

    assert settings.telnyx_api_key is not None  # narrowed by telnyx_configured
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            MESSAGES_URL,
            headers={"Authorization": f"Bearer {settings.telnyx_api_key.get_secret_value()}"},
            json={"from": settings.telnyx_from_number, "to": to, "text": text[:1600]},
        )
    response.raise_for_status()
    payload = response.json()
    return str(payload["data"]["id"])
