"""US03 — Autenticação (entrar, sair e acesso a rotas restritas)."""

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits import RateLimitItemPerMinute
from pydantic import BaseModel, ValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DEV_JWT_SECRET, Settings, get_settings
from app.errors import AppError, ErrorCode, register_error_handlers
from app.models import RefreshToken, User, UserStatus
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.security.tokens import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_token,
)
from tests.factories import DEFAULT_PASSWORD, auth_headers, create_user

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def _login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


def _decode_error(token: str) -> AppError:
    with pytest.raises(AppError) as exc_info:
        decode_access_token(token)
    return exc_info.value


@pytest.fixture()
def rate_limit_on() -> Iterator[None]:
    limiter.reset()
    limiter.enabled = True
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


class _Body(BaseModel):
    email: str


@pytest.fixture()
def contract_client() -> TestClient:
    contract_app = FastAPI()
    register_error_handlers(contract_app)

    contract_limiter = Limiter(key_func=get_remote_address, enabled=True)
    contract_app.state.limiter = contract_limiter
    contract_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @contract_app.get("/negocio")
    def negocio() -> None:
        raise AppError(
            ErrorCode.INVITE_EXPIRED, "O convite expirou.", 410, details={"can_resend": True}
        )

    @contract_app.post("/validacao")
    def validacao(body: _Body) -> _Body:
        return body

    @contract_app.get("/limitado")
    @contract_limiter.limit("2/minute")
    def limitado(request: Request) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(contract_app)


def test_login_com_credenciais_validas_devolve_tokens(
    client: TestClient, teacher_user: User
) -> None:
    response = _login(client, teacher_user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["access_token"] and body["refresh_token"]
    assert body["user"] == {
        "id": teacher_user.id,
        "email": teacher_user.email,
        "full_name": None,
        "school": None,
        "role": "teacher",
        "status": "active",
    }


@pytest.mark.parametrize(
    "email", ["  PROFESSOR@Escola.com ", "PROFESSOR@ESCOLA.COM", "professor@escola.com"]
)
def test_login_ignora_maiusculas_e_espacos_no_email(
    client: TestClient, teacher_user: User, email: str
) -> None:
    assert _login(client, email).status_code == 200


def test_access_token_do_login_da_acesso_ao_me(client: TestClient, teacher_user: User) -> None:
    token = _login(client, teacher_user.email).json()["access_token"]

    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == teacher_user.email


def test_refresh_token_e_guardado_so_como_hash(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]

    stored = db_session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == teacher_user.id)
    ).all()

    assert [t.token_hash for t in stored] == [hash_token(raw)]


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("professor@escola.com", "senha-errada-123"),
        ("ninguem@escola.com", DEFAULT_PASSWORD),
    ],
    ids=["senha-errada", "email-inexistente"],
)
def test_login_invalido_nao_revela_o_motivo(
    client: TestClient, teacher_user: User, email: str, password: str
) -> None:
    response = _login(client, email, password)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    assert response.json()["message"] == "E-mail ou senha incorretos."


@pytest.mark.parametrize(
    ("status", "password"),
    [(UserStatus.INVITE_PENDING, None), (UserStatus.INACTIVE, DEFAULT_PASSWORD)],
    ids=["convite-pendente", "inativa"],
)
def test_login_de_conta_nao_ativa_e_bloqueado(
    client: TestClient, db_session: Session, status: UserStatus, password: str | None
) -> None:
    user = create_user(db_session, status=status, password=password)

    response = _login(client, user.email)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "nao-e-email", "password": DEFAULT_PASSWORD},
        {"email": "professor@escola.com", "password": ""},
        {"email": "professor@escola.com"},
        {"password": DEFAULT_PASSWORD},
    ],
    ids=["email-mal-formado", "senha-vazia", "sem-senha", "sem-email"],
)
def test_login_com_corpo_invalido_responde_422(client: TestClient, body: dict) -> None:
    response = client.post(LOGIN, json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_refresh_devolve_tokens_novos_e_invalida_o_anterior(
    client: TestClient, teacher_user: User
) -> None:
    first = _login(client, teacher_user.email).json()["refresh_token"]

    response = client.post(REFRESH, json={"refresh_token": first})

    assert response.status_code == 200
    second = response.json()["refresh_token"]
    assert second != first
    assert client.post(REFRESH, json={"refresh_token": second}).status_code == 200


def test_reuso_de_refresh_ja_trocado_derruba_todas_as_sessoes(
    client: TestClient, teacher_user: User
) -> None:
    stolen = _login(client, teacher_user.email).json()["refresh_token"]
    current = client.post(REFRESH, json={"refresh_token": stolen}).json()["refresh_token"]
    other_device = _login(client, teacher_user.email).json()["refresh_token"]

    reuse = client.post(REFRESH, json={"refresh_token": stolen})

    assert reuse.status_code == 401
    assert reuse.json()["code"] == "TOKEN_INVALID"
    for token in (current, other_device):
        assert client.post(REFRESH, json={"refresh_token": token}).status_code == 401


def _refresh_desconhecido(client: TestClient, db_session: Session, user: User) -> str:
    return "inventado"


def _refresh_expirado(client: TestClient, db_session: Session, user: User) -> str:
    raw = _login(client, user.email).json()["refresh_token"]
    token = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
    )
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()
    return raw


def _refresh_de_conta_desativada(client: TestClient, db_session: Session, user: User) -> str:
    raw = _login(client, user.email).json()["refresh_token"]
    user.status = UserStatus.INACTIVE
    db_session.flush()
    return raw


@pytest.mark.parametrize(
    "cenario",
    [
        pytest.param(_refresh_desconhecido, id="desconhecido"),
        pytest.param(_refresh_expirado, id="expirado"),
        pytest.param(_refresh_de_conta_desativada, id="conta-desativada"),
    ],
)
def test_refresh_invalido_responde_401(
    client: TestClient,
    db_session: Session,
    teacher_user: User,
    cenario: Callable[[TestClient, Session, User], str],
) -> None:
    raw = cenario(client, db_session, teacher_user)

    response = client.post(REFRESH, json={"refresh_token": raw})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_logout_revoga_o_refresh_token(client: TestClient, teacher_user: User) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]

    response = client.post(LOGOUT, json={"refresh_token": raw})

    assert response.status_code == 204
    assert client.post(REFRESH, json={"refresh_token": raw}).status_code == 401


@pytest.mark.parametrize("repetido", [True, False], ids=["token-ja-revogado", "token-inventado"])
def test_logout_e_idempotente(client: TestClient, teacher_user: User, repetido: bool) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]
    client.post(LOGOUT, json={"refresh_token": raw})

    token = raw if repetido else "inventado"

    assert client.post(LOGOUT, json={"refresh_token": token}).status_code == 204


def test_logout_nao_afeta_outras_sessoes(client: TestClient, teacher_user: User) -> None:
    phone = _login(client, teacher_user.email).json()["refresh_token"]
    tablet = _login(client, teacher_user.email).json()["refresh_token"]

    client.post(LOGOUT, json={"refresh_token": phone})

    assert client.post(REFRESH, json={"refresh_token": tablet}).status_code == 200


def _sem_token(user: User) -> dict[str, str]:
    return {}


def _token_lixo(user: User) -> dict[str, str]:
    return {"Authorization": "Bearer lixo"}


def _token_expirado(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, "teacher", now=datetime.now(UTC) - timedelta(hours=1))
    return {"Authorization": f"Bearer {token}"}


def _token_de_usuario_inexistente(user: User) -> dict[str, str]:
    token, _ = create_access_token(999_999, "teacher")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        pytest.param(_sem_token, "UNAUTHENTICATED", id="sem-token"),
        pytest.param(_token_lixo, "TOKEN_INVALID", id="token-invalido"),
        pytest.param(_token_expirado, "TOKEN_EXPIRED", id="token-expirado"),
        pytest.param(_token_de_usuario_inexistente, "UNAUTHENTICATED", id="usuario-inexistente"),
    ],
)
def test_rota_restrita_sem_sessao_valida_responde_401(
    protected_client: TestClient,
    teacher_user: User,
    headers: Callable[[User], dict[str, str]],
    code: str,
) -> None:
    response = protected_client.get("/me", headers=headers(teacher_user))

    assert response.status_code == 401
    assert response.json()["code"] == code
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("path", [ME, "/api/v1/books", "/api/v1/themes", "/api/v1/me/saved-books"])
def test_rotas_da_api_exigem_login(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_usuario_ativo_acessa_rota_autenticada(
    protected_client: TestClient, teacher_user: User
) -> None:
    response = protected_client.get("/me", headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert response.json() == {"id": teacher_user.id}


@pytest.mark.parametrize(
    ("status", "password"),
    [(UserStatus.INACTIVE, DEFAULT_PASSWORD), (UserStatus.INVITE_PENDING, None)],
    ids=["inativa", "convite-pendente"],
)
def test_conta_nao_ativa_perde_o_acesso_mesmo_com_token_valido(
    protected_client: TestClient, db_session: Session, status: UserStatus, password: str | None
) -> None:
    user = create_user(db_session, status=status, password=password)

    response = protected_client.get("/me", headers=auth_headers(user))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.usefixtures("rate_limit_on")
def test_login_tem_limite_de_tentativas(client: TestClient) -> None:
    statuses = [_login(client, "ninguem@escola.com").status_code for _ in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    assert _login(client, "ninguem@escola.com").json()["code"] == "RATE_LIMITED"


@pytest.mark.parametrize(("user_id", "role"), [(42, "teacher"), (7, "admin")])
def test_access_token_ida_e_volta(user_id: int, role: str) -> None:
    token, expires_in = create_access_token(user_id, role)

    claims = decode_access_token(token)

    assert claims.user_id == user_id
    assert claims.role == role
    assert expires_in == get_settings().access_token_ttl_minutes * 60


def test_access_token_expirado_tem_codigo_proprio() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=1)
    token, _ = create_access_token(42, "teacher", now=long_ago)

    error = _decode_error(token)

    assert error.code == ErrorCode.TOKEN_EXPIRED
    assert error.status_code == 401
    assert error.headers == {"WWW-Authenticate": "Bearer"}


def _assinado_com_outro_segredo() -> str:
    return jwt.encode(
        {
            "sub": "1",
            "role": "admin",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "segredo-de-um-atacante-com-32-chars!!",
        algorithm="HS256",
    )


def _sem_assinatura() -> str:
    return jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "exp": 9999999999},
        key=None,
        algorithm="none",
    )


def _de_outro_tipo() -> str:
    settings = get_settings()
    return jwt.encode(
        {"sub": "1", "type": "refresh", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: "", id="vazio"),
        pytest.param(lambda: "nao-e-um-jwt", id="nao-e-jwt"),
        pytest.param(lambda: "a.b.c", id="tres-partes-lixo"),
        pytest.param(_assinado_com_outro_segredo, id="outro-segredo"),
        pytest.param(_sem_assinatura, id="sem-assinatura"),
        pytest.param(_de_outro_tipo, id="outro-tipo"),
    ],
)
def test_token_invalido_e_recusado(token: Callable[[], str]) -> None:
    assert _decode_error(token()).code == ErrorCode.TOKEN_INVALID


def test_tokens_opacos_sao_unicos_e_seguros_para_url() -> None:
    tokens = {generate_opaque_token() for _ in range(100)}

    assert len(tokens) == 100
    for token in tokens:
        assert len(token) >= 43
        assert all(c.isalnum() or c in "-_" for c in token)


def test_hash_de_token_e_deterministico_e_nao_revela_o_token() -> None:
    raw = generate_opaque_token()

    assert hash_token(raw) == hash_token(raw)
    assert hash_token(raw) != raw
    assert len(hash_token(raw)) == 64
    assert hash_token(raw) != hash_token(generate_opaque_token())


def test_desenvolvimento_aceita_segredo_padrao() -> None:
    assert Settings(app_env="development").jwt_secret == DEV_JWT_SECRET


@pytest.mark.parametrize("secret", [DEV_JWT_SECRET, "curto-demais"])
def test_producao_recusa_segredo_inseguro(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret=secret)


def test_producao_aceita_segredo_forte() -> None:
    settings = Settings(app_env="production", jwt_secret="x" * 48)

    assert settings.app_env == "production"


def test_erro_de_negocio_segue_o_contrato(contract_client: TestClient) -> None:
    response = contract_client.get("/negocio")

    assert response.status_code == 410
    assert response.json() == {
        "code": "INVITE_EXPIRED",
        "message": "O convite expirou.",
        "details": {"can_resend": True},
    }


@pytest.mark.parametrize(
    ("method", "path", "status_code", "code"),
    [
        ("post", "/validacao", 422, "VALIDATION_ERROR"),
        ("get", "/nao-existe", 404, "NOT_FOUND"),
        ("delete", "/negocio", 405, "METHOD_NOT_ALLOWED"),
    ],
)
def test_erros_do_framework_seguem_o_contrato(
    contract_client: TestClient, method: str, path: str, status_code: int, code: str
) -> None:
    response = contract_client.request(method, path, json={})

    assert response.status_code == status_code
    body = response.json()
    assert body["code"] == code
    assert set(body) == {"code", "message", "details"}


def test_erro_de_validacao_aponta_o_campo(contract_client: TestClient) -> None:
    response = contract_client.post("/validacao", json={})

    assert response.json()["details"][0]["loc"] == ["body", "email"]


def test_rate_limit_segue_o_contrato(contract_client: TestClient) -> None:
    for _ in range(2):
        assert contract_client.get("/limitado").status_code == 200

    response = contract_client.get("/limitado")

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


def _request_with_limit(item, keys: list[str]) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "state": {}}
    request = Request(scope)
    request.state.view_rate_limit = (item, keys)
    return request


def test_429_tem_envelope_do_contrato_e_retry_after() -> None:
    item = RateLimitItemPerMinute(5)
    limiter.limiter.hit(item, "teste-retry-after")

    response = asyncio.run(
        rate_limit_exceeded_handler(
            _request_with_limit(item, ["teste-retry-after"]),
            Mock(detail="5 per 1 minute"),
        )
    )

    assert response.status_code == 429
    assert '"code":"RATE_LIMITED"' in response.body.decode()
    assert 1 <= int(response.headers["Retry-After"]) <= 61


def test_429_sem_limite_identificado_nao_envia_retry_after() -> None:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "state": {}}

    response = asyncio.run(
        rate_limit_exceeded_handler(Request(scope), Mock(detail="5 per 1 minute"))
    )

    assert response.status_code == 429
    assert "Retry-After" not in response.headers
