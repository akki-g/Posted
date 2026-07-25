from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OAuthCredential
from app.providers.schwab.oauth import OAuthTokenSet
from app.security.vault import TokenVault


@dataclass(frozen=True, slots=True)
class StoredTokenSet:
    access_token: str
    refresh_token: str | None
    token_type: str
    scope: str | None
    expires_at: datetime


class SchwabCredentialStore:
    def __init__(self, *, session: AsyncSession, vault: TokenVault) -> None:
        self._session = session
        self._vault = vault

    async def save(self, *, connection_id: UUID, tokens: OAuthTokenSet) -> None:
        credential = await self._session.scalar(
            select(OAuthCredential).where(OAuthCredential.connection_id == connection_id)
        )
        if credential is None:
            credential = OAuthCredential(
                connection_id=connection_id,
                access_token_encrypted="",
                expires_at=tokens.expires_at,
            )
            self._session.add(credential)
        credential.access_token_encrypted = self._vault.encrypt(tokens.access_token)
        # Schwab may omit refresh_token on a refresh response. Preserve the
        # currently stored refresh token instead of accidentally disconnecting.
        if tokens.refresh_token:
            credential.refresh_token_encrypted = self._vault.encrypt(tokens.refresh_token)
        credential.token_type = tokens.token_type
        credential.scope = tokens.scope
        credential.expires_at = tokens.expires_at

    async def load(self, *, connection_id: UUID) -> StoredTokenSet | None:
        credential = await self._session.scalar(
            select(OAuthCredential).where(OAuthCredential.connection_id == connection_id)
        )
        if credential is None:
            return None
        return StoredTokenSet(
            access_token=self._vault.decrypt(credential.access_token_encrypted),
            refresh_token=(
                self._vault.decrypt(credential.refresh_token_encrypted)
                if credential.refresh_token_encrypted
                else None
            ),
            token_type=credential.token_type,
            scope=credential.scope,
            expires_at=credential.expires_at,
        )
