from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrokerageCredential
from app.security.vault import TokenVault


@dataclass(frozen=True, slots=True)
class StoredCredential:
    access_token: str
    refresh_token: str | None
    token_type: str
    scope: str | None
    expires_at: datetime | None


class BrokerageCredentialStore:
    def __init__(self, *, session: AsyncSession, vault: TokenVault) -> None:
        self._session = session
        self._vault = vault

    async def save(
        self,
        *,
        connection_id: UUID,
        access_token: str,
        refresh_token: str | None = None,
        token_type: str = "Bearer",
        scope: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        credential = await self._session.scalar(
            select(BrokerageCredential).where(
                BrokerageCredential.connection_id == connection_id
            )
        )
        if credential is None:
            credential = BrokerageCredential(
                connection_id=connection_id, access_token_encrypted=""
            )
            self._session.add(credential)
        credential.access_token_encrypted = self._vault.encrypt(access_token)
        # A refresh response may omit refresh_token; preserve the stored one
        # instead of accidentally disconnecting the account.
        if refresh_token:
            credential.refresh_token_encrypted = self._vault.encrypt(refresh_token)
        credential.token_type = token_type
        credential.scope = scope
        credential.expires_at = expires_at

    async def load(self, *, connection_id: UUID) -> StoredCredential | None:
        credential = await self._session.scalar(
            select(BrokerageCredential).where(
                BrokerageCredential.connection_id == connection_id
            )
        )
        if credential is None:
            return None
        return StoredCredential(
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
