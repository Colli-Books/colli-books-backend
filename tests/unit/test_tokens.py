from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.security.tokens import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_token,
)


def _decode_error(token: str) -> AppError:
    with pytest.raises(AppError) as exc_info:
        decode_access_token(token)
    return exc_info.value


def test_access_token_ida_e_volta() -> None:
    token, expires_in = create_access_token(42, "teacher")

    claims = decode_access_token(token)

    assert claims.user_id == 42
    assert claims.role == "teacher"
    assert expires_in == get_settings().access_token_ttl_minutes * 60


def test_access_token_expirado_tem_codigo_proprio() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=1)
    token, _ = create_access_token(42, "teacher", now=long_ago)

    error = _decode_error(token)

    assert error.code == ErrorCode.TOKEN_EXPIRED
    assert error.status_code == 401
    assert error.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize("token", ["", "nao-e-um-jwt", "a.b.c"])
def test_token_malformado_e_invalido(token: str) -> None:
    assert _decode_error(token).code == ErrorCode.TOKEN_INVALID


def test_token_assinado_com_outro_segredo_e_invalido() -> None:
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "exp": now + timedelta(minutes=5)},
        "segredo-de-um-atacante-com-32-chars!!",
        algorithm="HS256",
    )
    assert _decode_error(forged).code == ErrorCode.TOKEN_INVALID


def test_token_sem_assinatura_e_invalido() -> None:
    unsigned = jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "exp": 9999999999},
        key=None,
        algorithm="none",
    )
    assert _decode_error(unsigned).code == ErrorCode.TOKEN_INVALID


def test_token_de_outro_tipo_e_invalido() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "1", "type": "refresh", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert _decode_error(token).code == ErrorCode.TOKEN_INVALID


def test_tokens_opacos_sao_unicos_e_seguros_para_url() -> None:
    tokens = {generate_opaque_token() for _ in range(100)}
    assert len(tokens) == 100
    for token in tokens:
        assert len(token) >= 43  # 32 bytes em base64url
        assert all(c.isalnum() or c in "-_" for c in token)


def test_hash_de_token_e_deterministico_e_nao_revela_o_token() -> None:
    raw = generate_opaque_token()
    assert hash_token(raw) == hash_token(raw)
    assert hash_token(raw) != raw
    assert len(hash_token(raw)) == 64
    assert hash_token(raw) != hash_token(generate_opaque_token())
