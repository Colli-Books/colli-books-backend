"""Tokens da aplicação.

Há dois tipos:

* **Access token (JWT)**: curto, assinado, sem estado no servidor. Vai no header
  `Authorization: Bearer` de cada requisição do app.
* **Tokens opacos**: valores aleatórios entregues ao usuário (refresh token,
  convite, redefinição de senha). O banco guarda só o hash SHA-256, então um
  vazamento do banco não permite usar nenhum deles.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import status

from app.config import get_settings
from app.errors import AppError, ErrorCode

ACCESS_TOKEN_TYPE = "access"
_BEARER_HEADERS = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    role: str
    expires_at: datetime


def create_access_token(user_id: int, role: str, *, now: datetime | None = None) -> tuple[str, int]:
    """Gera um access token. Retorna o token e a validade em segundos."""
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued_at,
        "exp": issued_at + ttl,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        # Código próprio para o app saber que deve tentar o refresh.
        raise AppError(
            ErrorCode.TOKEN_EXPIRED,
            "Sessão expirada.",
            status.HTTP_401_UNAUTHORIZED,
            headers=_BEARER_HEADERS,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise _invalid_token() from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise _invalid_token()
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise _invalid_token() from exc

    return AccessTokenClaims(
        user_id=user_id,
        role=str(payload.get("role", "")),
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )


def _invalid_token() -> AppError:
    return AppError(
        ErrorCode.TOKEN_INVALID,
        "Token inválido.",
        status.HTTP_401_UNAUTHORIZED,
        headers=_BEARER_HEADERS,
    )


def generate_opaque_token() -> str:
    """Token aleatório, seguro para URL (256 bits de entropia)."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """Hash usado para guardar e buscar tokens opacos no banco.

    SHA-256 sem salt é suficiente aqui: o token já tem 256 bits de entropia,
    então não há como adivinhá-lo por dicionário. E precisa ser determinístico
    para permitir a busca por `token_hash`.
    """
    return hashlib.sha256(raw.encode()).hexdigest()
