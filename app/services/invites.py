"""Convites de primeiro acesso (US01 gera, US02 consome)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models import Invite, User, UserStatus
from app.security.passwords import hash_password, validate_password_strength
from app.security.tokens import generate_opaque_token, hash_token
from app.services.email import EmailKind, EmailMessage, EmailSender
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


def send_invite_email(
    sender: EmailSender, user: User, invite: IssuedInvite, *, renewed: bool = False
) -> None:
    """Manda o link de convite para o e-mail do professor.

    Assunto, remetente e corpo são do template do Brevo (`BREVO_TEMPLATE_INVITE`
    ou `BREVO_TEMPLATE_INVITE_RENEWAL`); aqui só vão os params do template.
    """
    sender.send(
        EmailMessage(
            to=user.email,
            kind=EmailKind.INVITE_RENEWAL if renewed else EmailKind.INVITE,
            params={
                "link": invite.link,
                "code": invite.code,
                "expires_at": f"{invite.expires_at:%d/%m/%Y %H:%M} (UTC)",
            },
        )
    )


def _find_invite(db: Session, raw: str, *, lock: bool = False) -> Invite | None:
    query = select(Invite).where(Invite.token_hash == hash_token(raw))
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def _check_usable(invite: Invite | None) -> Invite:
    """Erros distintos para inválido, expirado e já usado (US02)."""
    if invite is None or invite.user.status == UserStatus.INACTIVE:
        raise AppError(ErrorCode.INVITE_INVALID, "Convite inválido.", status.HTTP_404_NOT_FOUND)
    if invite.used_at is not None or invite.user.status != UserStatus.INVITE_PENDING:
        raise AppError(
            ErrorCode.INVITE_ALREADY_USED,
            "Este convite já foi usado. Faça login com sua senha.",
            status.HTTP_409_CONFLICT,
        )
    if invite.expires_at <= datetime.now(UTC):
        raise AppError(
            ErrorCode.INVITE_EXPIRED,
            "O convite expirou. Solicite um novo link.",
            status.HTTP_410_GONE,
        )
    return invite


def verify_invite(db: Session, raw: str) -> User:
    """Confere o convite sem consumi-lo. Devolve o dono, para o app exibir o e-mail."""
    return _check_usable(_find_invite(db, raw)).user


def accept_invite(
    db: Session, raw: str, *, full_name: str, school: str | None, password: str
) -> User:
    """Completa o cadastro (nome, escola e senha), ativa a conta e consome o convite.

    Faz commit.
    """
    invite = _check_usable(_find_invite(db, raw, lock=True))
    validate_password_strength(password)

    user = invite.user
    user.full_name = full_name
    user.school = school
    user.password_hash = hash_password(password)
    user.status = UserStatus.ACTIVE
    invite.used_at = datetime.now(UTC)
    db.commit()
    return user


def resend_invite(db: Session, sender: EmailSender, raw: str) -> None:
    """Reenvia um convite **expirado** para o e-mail cadastrado. Faz commit.

    Qualquer outro caso é ignorado em silêncio. O link novo nunca volta na
    resposta: quem tivesse um link vazado e expirado ganharia um link válido.
    """
    invite = _find_invite(db, raw, lock=True)
    if (
        invite is None
        or invite.used_at is not None
        or invite.expires_at > datetime.now(UTC)
        or invite.user.status != UserStatus.INVITE_PENDING
    ):
        return

    user = invite.user
    new_invite = issue_invite(db, user)
    db.commit()
    send_invite_email(sender, user, new_invite, renewed=True)
