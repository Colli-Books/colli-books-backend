"""US05 — Autenticação do administrador."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import SeedAdminError, seed_admin
from app.models import User, UserRole, UserStatus
from app.security.passwords import verify_password
from tests.factories import DEFAULT_PASSWORD, auth_headers, create_user

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


@pytest.mark.parametrize("email", ["admin@colli.com", "ADMIN@Colli.com"])
def test_admin_faz_login_pela_mesma_rota(client: TestClient, admin_user: User, email: str) -> None:
    response = client.post(LOGIN, json={"email": email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


@pytest.mark.parametrize(
    ("email", "password"),
    [("admin@colli.com", "senha-errada-123"), ("outro-admin@colli.com", DEFAULT_PASSWORD)],
    ids=["senha-errada", "email-inexistente"],
)
def test_login_invalido_do_admin_nao_revela_o_motivo(
    client: TestClient, admin_user: User, email: str, password: str
) -> None:
    response = client.post(LOGIN, json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["message"] == "E-mail ou senha incorretos."


@pytest.mark.parametrize(("field", "expected"), [("full_name", "Editora Colli"), ("role", "admin")])
def test_me_do_admin_mostra_nome_e_papel_para_o_cabecalho(
    client: TestClient, db_session: Session, field: str, expected: str
) -> None:
    admin = create_user(
        db_session, email="editora@colli.com", role=UserRole.ADMIN, full_name="Editora Colli"
    )

    response = client.get(ME, headers=auth_headers(admin))

    assert response.status_code == 200
    assert response.json()[field] == expected


@pytest.mark.parametrize(
    ("requester", "status_code"),
    [("teacher_user", 403), ("admin_user", 200)],
    ids=["professor", "admin"],
)
def test_rota_de_admin_so_aceita_admin(
    request: pytest.FixtureRequest,
    protected_client: TestClient,
    requester: str,
    status_code: int,
) -> None:
    user = request.getfixturevalue(requester)

    response = protected_client.get("/admin", headers=auth_headers(user))

    assert response.status_code == status_code
    if status_code == 403:
        assert response.json()["code"] == "FORBIDDEN"


def test_rota_de_admin_sem_login_responde_401(protected_client: TestClient) -> None:
    response = protected_client.get("/admin")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_papel_vem_do_banco_e_nao_do_token(
    protected_client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session, role=UserRole.ADMIN)
    old_headers = auth_headers(user)
    user.role = UserRole.TEACHER
    db_session.flush()

    response = protected_client.get("/admin", headers=old_headers)

    assert response.status_code == 403


@pytest.mark.parametrize("email", ["admin@colli.com", "Admin@Colli.com"])
def test_seed_cria_admin_ativo(db_session: Session, email: str) -> None:
    created = seed_admin(db_session, email, "senha-segura-123", "Editora Colli")

    admin = db_session.scalar(select(User).where(User.email == "admin@colli.com"))
    assert created is True
    assert admin.role == UserRole.ADMIN
    assert admin.status == UserStatus.ACTIVE
    assert admin.full_name == "Editora Colli"
    assert verify_password("senha-segura-123", admin.password_hash)


def test_seed_rodado_duas_vezes_nao_duplica_nem_troca_a_senha(db_session: Session) -> None:
    seed_admin(db_session, "admin@colli.com", "senha-segura-123")

    created = seed_admin(db_session, "admin@colli.com", "outra-senha-456")

    admin = db_session.scalar(select(User).where(User.email == "admin@colli.com"))
    assert created is False
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert verify_password("senha-segura-123", admin.password_hash)


def test_seed_recusa_email_de_professor(db_session: Session) -> None:
    create_user(db_session, email="prof@escola.com")

    with pytest.raises(SeedAdminError):
        seed_admin(db_session, "prof@escola.com", "senha-segura-123")


@pytest.mark.parametrize("password", ["", "curta", "1234567"])
def test_seed_recusa_senha_fraca(db_session: Session, password: str) -> None:
    with pytest.raises(SeedAdminError, match="8 caracteres"):
        seed_admin(db_session, "admin@colli.com", password)
