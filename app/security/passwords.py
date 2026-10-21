"""Hash e verificação de senhas (US02, US03, US04).

Usa Argon2 via `pwdlib`. O `passlib`, citado nas notas técnicas das issues, está
sem manutenção e quebra com versões recentes do `bcrypt` e do Python.
"""

from functools import lru_cache

from fastapi import status
from pwdlib import PasswordHash

from app.config import get_settings
from app.errors import AppError, ErrorCode

_hasher = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("senha-ficticia-para-equalizar-tempo")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Confere a senha contra o hash.

    Quando não há hash (usuário inexistente ou convite pendente), ainda assim
    roda uma verificação contra um hash fictício. Assim o tempo de resposta do
    login não revela se o e-mail existe (US03: "sem revelar se o e-mail existe").
    """
    if hashed is None:
        _hasher.verify(plain, _dummy_hash())
        return False
    return _hasher.verify(plain, hashed)


def validate_password_strength(plain: str) -> None:
    """Regra de senha da US02 (mín. 8 caracteres), reaproveitada na US04."""
    settings = get_settings()
    if len(plain) < settings.password_min_length:
        raise AppError(
            ErrorCode.WEAK_PASSWORD,
            f"A senha precisa ter pelo menos {settings.password_min_length} caracteres.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if len(plain) > settings.password_max_length:
        raise AppError(
            ErrorCode.WEAK_PASSWORD,
            f"A senha pode ter no máximo {settings.password_max_length} caracteres.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
