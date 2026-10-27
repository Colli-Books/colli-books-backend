"""US01: cadastro de professor pela editora."""

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Invite, User, UserStatus
from app.security.tokens import hash_token
from app.services.email import (
    BackgroundEmailSender,
    EmailKind,
    EmailMessage,
    EmailSender,
    get_email_sender,
)
from tests.factories import auth_headers, create_user
from tests.fakes import InMemoryEmailSender

TEACHERS = "/api/v1/admin/teachers"


def _create(client: TestClient, admin: User, email: str = "novo@escola.com"):
    return client.post(TEACHERS, json={"email": email}, headers=auth_headers(admin))


def test_admin_cadastra_professor_com_convite_pendente(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    response = _create(client, admin_user, "Novo@Escola.com")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "novo@escola.com"
    assert body["status"] == "invite_pending"

    link = urlparse(body["invite_link"])
    assert (link.scheme, link.netloc) == ("collibooks", "convite")
    assert parse_qs(link.query)["token"] == [body["invite_code"]]

    expires_at = datetime.fromisoformat(body["invite_expires_at"])
    assert expires_at.tzinfo is not None
    assert timedelta(hours=71) < expires_at - datetime.now(UTC) <= timedelta(hours=72)

    user = db_session.get(User, body["id"])
    assert user.password_hash is None
    invite = db_session.scalar(select(Invite).where(Invite.user_id == user.id))
    assert invite.token_hash == hash_token(body["invite_code"])


def test_cadastro_manda_o_convite_para_o_email_do_professor(
    client: TestClient, admin_user: User, email_outbox: InMemoryEmailSender
) -> None:
    body = _create(client, admin_user, "Novo@Escola.com").json()

    [message] = email_outbox.outbox
    assert message.to == "novo@escola.com"
    assert message.kind == EmailKind.INVITE
    assert message.params["link"] == body["invite_link"]
    assert message.params["code"] == body["invite_code"]
    assert message.params["expires_at"]


def test_email_duplicado_nao_manda_email(
    client: TestClient, admin_user: User, email_outbox: InMemoryEmailSender
) -> None:
    _create(client, admin_user, "dup@escola.com")
    email_outbox.outbox.clear()

    _create(client, admin_user, "dup@escola.com")

    assert email_outbox.outbox == []


class _FailingSender:
    """Provê `send` que sempre falha, como um provedor fora do ar."""

    def send(self, message: EmailMessage) -> None:
        raise RuntimeError("provedor fora do ar")


def test_falha_no_envio_do_email_nao_quebra_a_resposta(
    client: TestClient, admin_user: User, caplog: pytest.LogCaptureFixture
) -> None:
    """O envio é em background: um provedor fora do ar não muda o contrato (201)."""

    def _failing(background_tasks: BackgroundTasks) -> EmailSender:
        return BackgroundEmailSender(background_tasks, _FailingSender())

    app.dependency_overrides[get_email_sender] = _failing

    with caplog.at_level(logging.ERROR, logger="app.services.email"):
        response = _create(client, admin_user, "falha@escola.com")

    assert response.status_code == 201
    assert response.json()["invite_link"]
    assert "Falha ao enviar e-mail para falha@escola.com (tipo=invite)" in caplog.text


def test_email_duplicado_responde_409(client: TestClient, admin_user: User) -> None:
    _create(client, admin_user, "dup@escola.com")

    response = _create(client, admin_user, "DUP@escola.com")

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_REGISTERED"


def test_email_invalido_responde_422(client: TestClient, admin_user: User) -> None:
    assert _create(client, admin_user, "nao-e-email").status_code == 422


def test_sem_token_responde_401(client: TestClient) -> None:
    response = client.post(TEACHERS, json={"email": "novo@escola.com"})

    assert response.status_code == 401


def test_professor_nao_cadastra_professor(client: TestClient, teacher_user: User) -> None:
    response = _create(client, teacher_user)

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_convidado_nao_consegue_fazer_login(client: TestClient, admin_user: User) -> None:
    _create(client, admin_user, "convidado@escola.com")

    response = client.post(
        "/api/v1/auth/login", json={"email": "convidado@escola.com", "password": "qualquer-123"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


# --- Gerar novo convite -------------------------------------------------------


def test_novo_convite_substitui_o_anterior_e_vai_por_email(
    client: TestClient, db_session: Session, admin_user: User, email_outbox: InMemoryEmailSender
) -> None:
    first = _create(client, admin_user).json()
    email_outbox.outbox.clear()

    response = client.post(f"{TEACHERS}/{first['id']}/invite", headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json()["invite_code"] != first["invite_code"]
    hashes = db_session.scalars(select(Invite.token_hash).where(Invite.user_id == first["id"]))
    assert list(hashes) == [hash_token(response.json()["invite_code"])]
    [message] = email_outbox.outbox
    assert message.to == first["email"]
    assert message.kind == EmailKind.INVITE_RENEWAL
    assert message.params["link"] == response.json()["invite_link"]


def test_novo_convite_para_professor_ativo_responde_409(
    client: TestClient, admin_user: User, teacher_user: User
) -> None:
    response = client.post(f"{TEACHERS}/{teacher_user.id}/invite", headers=auth_headers(admin_user))

    assert response.status_code == 409
    assert response.json()["code"] == "ACCOUNT_ALREADY_ACTIVE"


def test_novo_convite_para_inexistente_ou_admin_responde_404(
    client: TestClient, admin_user: User
) -> None:
    for user_id in (999_999, admin_user.id):
        response = client.post(f"{TEACHERS}/{user_id}/invite", headers=auth_headers(admin_user))
        assert response.status_code == 404


def test_professor_nao_gera_convite(client: TestClient, db_session: Session) -> None:
    pending = create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)
    teacher = create_user(db_session)

    response = client.post(f"{TEACHERS}/{pending.id}/invite", headers=auth_headers(teacher))

    assert response.status_code == 403
