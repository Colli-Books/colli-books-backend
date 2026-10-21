"""Regras de sessão da US03: login, rotação de refresh token e logout.

Os refresh tokens são opacos e guardados só como hash (`hash_token`). Cada uso em
`/auth/refresh` revoga o token apresentado e emite outro (rotação). Se um token
já revogado aparecer de novo, alguém o copiou: todas as sessões do usuário são
encerradas (detecção de roubo).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models import RefreshToken, User, UserStatus
from app.security.passwords import verify_password
from app.security.tokens import create_access_token, generate_opaque_token, hash_token


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    """Confere e-mail e senha.

    Usuário inexistente, senha errada, convite pendente e conta inativa dão
    todos o mesmo erro, para não revelar se o e-mail está cadastrado.
    """
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or user.status != UserStatus.ACTIVE:
        raise AppError(
            ErrorCode.INVALID_CREDENTIALS,
            "E-mail ou senha incorretos.",
            status.HTTP_401_UNAUTHORIZED,
        )
    return user


def start_session(db: Session, user: User) -> SessionTokens:
    """Emite access token + refresh token novos. Faz commit."""
    settings = get_settings()
    raw_refresh = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.commit()
    access_token, expires_in = create_access_token(user.id, user.role.value)
    return SessionTokens(access_token, raw_refresh, expires_in, user)


def rotate_refresh_token(db: Session, raw_refresh: str) -> SessionTokens:
    """Troca um refresh token válido por uma sessão nova. Faz commit."""
    # FOR UPDATE: duas renovações simultâneas com o mesmo token não podem ambas vencer.
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_refresh))
        .with_for_update()
    )
    if token is None:
        raise _invalid_refresh()

    if token.revoked_at is not None:
        # Reuso de token já rotacionado: trata como roubo e derruba todas as sessões.
        revoke_all_sessions(db, token.user_id)
        db.commit()
        raise _invalid_refresh()

    user = token.user
    if token.expires_at <= datetime.now(UTC) or user.status != UserStatus.ACTIVE:
        raise _invalid_refresh()

    token.revoked_at = datetime.now(UTC)
    return start_session(db, user)


def end_session(db: Session, raw_refresh: str) -> None:
    """Logout: revoga o refresh token informado. Idempotente. Faz commit."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(raw_refresh),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    """Revoga todos os refresh tokens ativos do usuário. Não faz commit."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def _invalid_refresh() -> AppError:
    # Um único código para qualquer falha de refresh: o app volta para o login.
    return AppError(
        ErrorCode.TOKEN_INVALID,
        "Sessão inválida. Faça login novamente.",
        status.HTTP_401_UNAUTHORIZED,
    )
