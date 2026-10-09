"""Convites de primeiro acesso (US01 gera, US02 consome)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Invite, User
from app.security.tokens import generate_opaque_token, hash_token
from app.services.links import build_app_link

INVITE_PATH = "convite"


@dataclass(frozen=True)
class IssuedInvite:
    """Convite recém-criado. `code` é o token em claro: só existe nesta resposta."""

    code: str
    link: str
    expires_at: datetime


def issue_invite(db: Session, user: User) -> IssuedInvite:
    """Cria um convite novo e apaga os pendentes anteriores. Não faz commit.

    Apagar (em vez de expirar) faz um link antigo responder `INVITE_INVALID`, e
    assim ele não pode ser usado para pedir reenvio.
    """
    db.execute(delete(Invite).where(Invite.user_id == user.id, Invite.used_at.is_(None)))

    raw = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().invite_ttl_hours)
    db.add(Invite(user_id=user.id, token_hash=hash_token(raw), expires_at=expires_at))
    return IssuedInvite(code=raw, link=build_app_link(INVITE_PATH, raw), expires_at=expires_at)
