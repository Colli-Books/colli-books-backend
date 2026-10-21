"""US01: cadastro de professor pela editora."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invite, User, UserStatus
from app.security.tokens import hash_token
from tests.factories import auth_headers, create_user

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


def test_novo_convite_substitui_o_anterior(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    first = _create(client, admin_user).json()

    response = client.post(f"{TEACHERS}/{first['id']}/invite", headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json()["invite_code"] != first["invite_code"]
    hashes = db_session.scalars(select(Invite.token_hash).where(Invite.user_id == first["id"]))
    assert list(hashes) == [hash_token(response.json()["invite_code"])]


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
