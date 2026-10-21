"""US03 (login, refresh, logout) e US05 (/me, acesso do admin)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken, User, UserRole, UserStatus
from app.rate_limit import limiter
from app.security.tokens import hash_token
from tests.factories import DEFAULT_PASSWORD, auth_headers, create_user

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def _login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


# --- Login --------------------------------------------------------------------


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
        "role": "teacher",
        "status": "active",
    }


def test_login_ignora_maiusculas_no_email(client: TestClient, teacher_user: User) -> None:
    response = _login(client, "  PROFESSOR@Escola.com ")

    assert response.status_code == 200


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


def test_login_de_convite_pendente_e_bloqueado(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)

    response = _login(client, user.email)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_de_conta_inativa_e_bloqueado_mesmo_com_senha_certa(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session, status=UserStatus.INACTIVE)

    response = _login(client, user.email)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_com_email_mal_formado_responde_422(client: TestClient) -> None:
    response = _login(client, "nao-e-email")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


# --- Refresh ------------------------------------------------------------------


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
    assert client.post(REFRESH, json={"refresh_token": current}).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": other_device}).status_code == 401


def test_refresh_desconhecido_responde_401(client: TestClient) -> None:
    response = client.post(REFRESH, json={"refresh_token": "inventado"})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_refresh_expirado_responde_401(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]
    token = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
    )
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()

    response = client.post(REFRESH, json={"refresh_token": raw})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_refresh_de_conta_desativada_responde_401(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]
    teacher_user.status = UserStatus.INACTIVE
    db_session.flush()

    response = client.post(REFRESH, json={"refresh_token": raw})

    assert response.status_code == 401


# --- Logout -------------------------------------------------------------------


def test_logout_revoga_o_refresh_token(client: TestClient, teacher_user: User) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]

    response = client.post(LOGOUT, json={"refresh_token": raw})

    assert response.status_code == 204
    assert client.post(REFRESH, json={"refresh_token": raw}).status_code == 401


def test_logout_e_idempotente(client: TestClient, teacher_user: User) -> None:
    raw = _login(client, teacher_user.email).json()["refresh_token"]
    client.post(LOGOUT, json={"refresh_token": raw})

    assert client.post(LOGOUT, json={"refresh_token": raw}).status_code == 204
    assert client.post(LOGOUT, json={"refresh_token": "inventado"}).status_code == 204


def test_logout_nao_afeta_outras_sessoes(client: TestClient, teacher_user: User) -> None:
    phone = _login(client, teacher_user.email).json()["refresh_token"]
    tablet = _login(client, teacher_user.email).json()["refresh_token"]

    client.post(LOGOUT, json={"refresh_token": phone})

    assert client.post(REFRESH, json={"refresh_token": tablet}).status_code == 200


# --- /me (US05) ---------------------------------------------------------------


def test_me_sem_token_responde_401(client: TestClient) -> None:
    response = client.get(ME)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_me_do_admin_mostra_nome_e_papel(client: TestClient, db_session: Session) -> None:
    admin = create_user(
        db_session, email="editora@colli.com", role=UserRole.ADMIN, full_name="Editora Colli"
    )

    response = client.get(ME, headers=auth_headers(admin))

    assert response.status_code == 200
    assert response.json()["full_name"] == "Editora Colli"
    assert response.json()["role"] == "admin"


def test_admin_faz_login_pela_mesma_rota(client: TestClient, admin_user: User) -> None:
    response = _login(client, admin_user.email)

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


# --- Rate limit ---------------------------------------------------------------


@pytest.fixture()
def rate_limit_on() -> Iterator[None]:
    limiter.reset()
    limiter.enabled = True
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


@pytest.mark.usefixtures("rate_limit_on")
def test_login_tem_limite_de_tentativas(client: TestClient) -> None:
    statuses = [_login(client, "ninguem@escola.com").status_code for _ in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    assert _login(client, "ninguem@escola.com").json()["code"] == "RATE_LIMITED"
