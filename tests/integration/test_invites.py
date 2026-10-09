"""US02: primeiro acesso pelo convite."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invite, User, UserStatus
from app.security.tokens import hash_token
from app.services.invites import issue_invite
from tests.factories import create_user
from tests.fakes import InMemoryEmailSender

VERIFY = "/api/v1/invites/verify"
ACCEPT = "/api/v1/invites/accept"
RESEND = "/api/v1/invites/resend"
NEW_PASSWORD = "minha-senha-nova"


@pytest.fixture()
def pending_user(db_session: Session) -> User:
    return create_user(
        db_session, email="convidado@escola.com", status=UserStatus.INVITE_PENDING, password=None
    )


@pytest.fixture()
def invite_code(db_session: Session, pending_user: User) -> str:
    code = issue_invite(db_session, pending_user).code
    db_session.flush()
    return code


def _expire(db_session: Session, code: str) -> None:
    invite = db_session.scalar(select(Invite).where(Invite.token_hash == hash_token(code)))
    invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()


# --- Verificar ----------------------------------------------------------------


def test_verificar_convite_valido_devolve_o_email(client: TestClient, invite_code: str) -> None:
    response = client.post(VERIFY, json={"token": invite_code})

    assert response.status_code == 200
    assert response.json() == {"email": "convidado@escola.com"}


def test_convite_inexistente_e_invalido(client: TestClient) -> None:
    response = client.post(VERIFY, json={"token": "inventado"})

    assert response.status_code == 404
    assert response.json()["code"] == "INVITE_INVALID"


def test_convite_expirado(client: TestClient, db_session: Session, invite_code: str) -> None:
    _expire(db_session, invite_code)

    response = client.post(VERIFY, json={"token": invite_code})

    assert response.status_code == 410
    assert response.json()["code"] == "INVITE_EXPIRED"


def test_convite_ja_usado(client: TestClient, invite_code: str) -> None:
    client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})

    response = client.post(VERIFY, json={"token": invite_code})

    assert response.status_code == 409
    assert response.json()["code"] == "INVITE_ALREADY_USED"


def test_convite_de_conta_desativada_e_invalido(
    client: TestClient, db_session: Session, pending_user: User, invite_code: str
) -> None:
    pending_user.status = UserStatus.INACTIVE
    db_session.flush()

    assert client.post(VERIFY, json={"token": invite_code}).json()["code"] == "INVITE_INVALID"


# --- Aceitar ------------------------------------------------------------------


def test_aceitar_define_senha_ativa_conta_e_autentica(
    client: TestClient, db_session: Session, pending_user: User, invite_code: str
) -> None:
    response = client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["status"] == "active"
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200

    db_session.refresh(pending_user)
    assert pending_user.status == UserStatus.ACTIVE
    invite = db_session.scalar(select(Invite).where(Invite.user_id == pending_user.id))
    assert invite.used_at is not None


def test_depois_de_aceitar_faz_login_com_a_senha_nova(client: TestClient, invite_code: str) -> None:
    client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})

    response = client.post(
        "/api/v1/auth/login", json={"email": "convidado@escola.com", "password": NEW_PASSWORD}
    )

    assert response.status_code == 200


def test_convite_nao_pode_ser_aceito_duas_vezes(client: TestClient, invite_code: str) -> None:
    client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})

    response = client.post(ACCEPT, json={"token": invite_code, "password": "outra-senha-999"})

    assert response.status_code == 409
    assert response.json()["code"] == "INVITE_ALREADY_USED"


def test_senha_curta_responde_weak_password_e_nao_consome_o_convite(
    client: TestClient, invite_code: str
) -> None:
    response = client.post(ACCEPT, json={"token": invite_code, "password": "1234567"})

    assert response.status_code == 422
    assert response.json()["code"] == "WEAK_PASSWORD"
    assert client.post(VERIFY, json={"token": invite_code}).status_code == 200


def test_aceitar_convite_expirado_responde_410(
    client: TestClient, db_session: Session, invite_code: str
) -> None:
    _expire(db_session, invite_code)

    response = client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})

    assert response.status_code == 410
    assert response.json()["code"] == "INVITE_EXPIRED"


# --- Reenviar -----------------------------------------------------------------


def test_reenviar_convite_expirado_manda_link_novo_por_email(
    client: TestClient, db_session: Session, invite_code: str, email_outbox: InMemoryEmailSender
) -> None:
    _expire(db_session, invite_code)

    response = client.post(RESEND, json={"token": invite_code})

    assert response.status_code == 202
    assert invite_code not in response.text
    [message] = email_outbox.outbox
    assert message.to == "convidado@escola.com"
    assert "collibooks://convite?token=" in message.body

    new_code = message.body.split("token=")[1].split()[0]
    assert client.post(VERIFY, json={"token": new_code}).status_code == 200
    assert client.post(VERIFY, json={"token": invite_code}).json()["code"] == "INVITE_INVALID"


def test_reenviar_convite_ainda_valido_nao_faz_nada(
    client: TestClient, invite_code: str, email_outbox: InMemoryEmailSender
) -> None:
    response = client.post(RESEND, json={"token": invite_code})

    assert response.status_code == 202
    assert email_outbox.outbox == []
    assert client.post(VERIFY, json={"token": invite_code}).status_code == 200


def test_reenviar_convite_usado_ou_inexistente_nao_faz_nada(
    client: TestClient, invite_code: str, email_outbox: InMemoryEmailSender
) -> None:
    client.post(ACCEPT, json={"token": invite_code, "password": NEW_PASSWORD})
    used = client.post(RESEND, json={"token": invite_code})
    unknown = client.post(RESEND, json={"token": "inventado"})

    assert used.status_code == unknown.status_code == 202
    assert used.json() == unknown.json()
    assert email_outbox.outbox == []
