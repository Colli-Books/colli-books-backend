"""US04 (professor) e US06 (admin): "Esqueci minha senha"."""

from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models import PasswordResetToken, User, UserStatus
from app.security.passwords import hash_password, validate_password_strength
from app.security.tokens import generate_opaque_token, hash_token
from app.services.auth import normalize_email, revoke_all_sessions
from app.services.email import EmailMessage, EmailSender
from app.services.links import build_app_link

RESET_PATH = "redefinir-senha"


def request_password_reset(db: Session, sender: EmailSender, email: str) -> None:
    """Envia o link de redefinição se a conta estiver ativa. Faz commit.

    E-mail inexistente, convite pendente e conta inativa são ignorados em
    silêncio: a resposta da API é sempre a mesma, para não revelar contas.
    """
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.status != UserStatus.ACTIVE:
        return

    # Só o link mais recente vale.
    db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
    )
    raw = generate_opaque_token()
    ttl_minutes = get_settings().password_reset_ttl_minutes
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()

    sender.send(
        EmailMessage(
            to=user.email,
            subject="Colli Books: redefinição de senha",
            body=(
                "Recebemos um pedido para redefinir sua senha.\n\n"
                f"Abra no celular: {build_app_link(RESET_PATH, raw)}\n"
                f"Ou cole este código no app: {raw}\n\n"
                f"O link vale por {ttl_minutes} minutos. "
                "Se você não pediu, ignore este e-mail: sua senha continua a mesma."
            ),
        )
    )


def reset_password(db: Session, raw: str, new_password: str) -> None:
    """Troca a senha, consome o token e encerra todas as sessões. Faz commit."""
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(raw))
        .with_for_update()
    )
    if (
        token is None
        or token.used_at is not None
        or token.expires_at <= datetime.now(UTC)
        or token.user.status != UserStatus.ACTIVE
    ):
        raise AppError(
            ErrorCode.RESET_TOKEN_INVALID,
            "Link de redefinição inválido ou expirado. Solicite um novo.",
            status.HTTP_400_BAD_REQUEST,
        )
    validate_password_strength(new_password)

    token.user.password_hash = hash_password(new_password)
    token.used_at = datetime.now(UTC)
    revoke_all_sessions(db, token.user_id)
    db.commit()
