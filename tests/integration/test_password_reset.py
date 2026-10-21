"""US04 (professor) e US06 (admin): redefinição de senha."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PasswordResetToken, User, UserRole, UserStatus
from app.security.tokens import hash_token
from tests.factories import DEFAULT_PASSWORD, create_user
from tests.fakes import InMemoryEmailSender

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
LOGIN = "/api/v1/auth/login"
NEW_PASSWORD = "minha-senha-nova"


@pytest.fixture(params=[UserRole.TEACHER, UserRole.ADMIN], ids=["US04-professor", "US06-admin"])
def user(request: pytest.FixtureRequest, db_session: Session) -> User:
    return create_user(db_session, email="conta@colli.com", role=request.param)


def _request_token(client: TestClient, outbox: InMemoryEmailSender, email: str) -> str:
    client.post(FORGOT, json={"email": email})
    return outbox.outbox[-1].body.split("token=")[1].split()[0]


def _login(client: TestClient, password: str):
    return client.post(LOGIN, json={"email": "conta@colli.com", "password": password})


def test_pedido_envia_link_de_redefinicao(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    response = client.post(FORGOT, json={"email": "CONTA@colli.com"})

    assert response.status_code == 202
    [message] = email_outbox.outbox
    assert message.to == "conta@colli.com"
    assert "collibooks://redefinir-senha?token=" in message.body


def test_resposta_e_identica_para_email_existente_e_inexistente(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    existing = client.post(FORGOT, json={"email": "conta@colli.com"})
    missing = client.post(FORGOT, json={"email": "ninguem@colli.com"})

    assert existing.status_code == missing.status_code == 202
    assert existing.json() == missing.json()
    assert len(email_outbox.outbox) == 1


@pytest.mark.parametrize(
    ("status", "password"),
    [(UserStatus.INVITE_PENDING, None), (UserStatus.INACTIVE, DEFAULT_PASSWORD)],
)
def test_conta_nao_ativa_e_ignorada_em_silencio(
    client: TestClient,
    db_session: Session,
    email_outbox: InMemoryEmailSender,
    status: UserStatus,
    password: str | None,
) -> None:
    create_user(db_session, email="conta@colli.com", status=status, password=password)

    response = client.post(FORGOT, json={"email": "conta@colli.com"})

    assert response.status_code == 202
    assert email_outbox.outbox == []


def test_redefinir_troca_a_senha(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    token = _request_token(client, email_outbox, user.email)

    response = client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    assert _login(client, NEW_PASSWORD).status_code == 200
    assert _login(client, DEFAULT_PASSWORD).status_code == 401


def test_redefinir_encerra_todas_as_sessoes(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    refresh = _login(client, DEFAULT_PASSWORD).json()["refresh_token"]
    token = _request_token(client, email_outbox, user.email)

    client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 401


def test_token_so_vale_uma_vez(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    token = _request_token(client, email_outbox, user.email)
    client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})

    response = client.post(RESET, json={"token": token, "new_password": "outra-senha-999"})

    assert response.status_code == 400
    assert response.json()["code"] == "RESET_TOKEN_INVALID"


def test_token_expirado_e_recusado(
    client: TestClient, db_session: Session, user: User, email_outbox: InMemoryEmailSender
) -> None:
    token = _request_token(client, email_outbox, user.email)
    stored = db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()

    response = client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["code"] == "RESET_TOKEN_INVALID"


def test_novo_pedido_invalida_o_link_anterior(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    old = _request_token(client, email_outbox, user.email)
    new = _request_token(client, email_outbox, user.email)

    assert client.post(RESET, json={"token": old, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post(RESET, json={"token": new, "new_password": NEW_PASSWORD}).status_code == 204


def test_token_inventado_e_recusado(client: TestClient) -> None:
    response = client.post(RESET, json={"token": "inventado", "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["code"] == "RESET_TOKEN_INVALID"


def test_senha_fraca_nao_consome_o_token(
    client: TestClient, user: User, email_outbox: InMemoryEmailSender
) -> None:
    token = _request_token(client, email_outbox, user.email)

    weak = client.post(RESET, json={"token": token, "new_password": "curta"})

    assert weak.status_code == 422
    assert weak.json()["code"] == "WEAK_PASSWORD"
    assert (
        client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD}).status_code == 204
    )
