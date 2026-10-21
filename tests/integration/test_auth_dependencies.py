"""Dependencies `CurrentUser` e `AdminUser` contra o banco real."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import register_error_handlers
from app.models import User, UserRole, UserStatus
from app.security.dependencies import AdminUser, CurrentUser
from app.security.tokens import create_access_token
from tests.factories import auth_headers, create_user


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """App mínima com uma rota autenticada e uma de admin."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/me")
    def me(user: CurrentUser) -> dict[str, int]:
        return {"id": user.id}

    @app.get("/admin")
    def admin(user: AdminUser) -> dict[str, int]:
        return {"id": user.id}

    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_sem_token_responde_401_unauthenticated(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_responde_401(client: TestClient) -> None:
    response = client.get("/me", headers={"Authorization": "Bearer lixo"})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_token_expirado_responde_401_token_expired(client: TestClient, teacher_user: User) -> None:
    token, _ = create_access_token(
        teacher_user.id, "teacher", now=datetime.now(UTC) - timedelta(hours=1)
    )

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


def test_usuario_ativo_acessa_rota_autenticada(client: TestClient, teacher_user: User) -> None:
    response = client.get("/me", headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert response.json() == {"id": teacher_user.id}


def test_token_de_usuario_inexistente_responde_401(client: TestClient) -> None:
    token, _ = create_access_token(999_999, "teacher")

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    ("status", "password"),
    [(UserStatus.INACTIVE, "senha-segura-123"), (UserStatus.INVITE_PENDING, None)],
)
def test_conta_nao_ativa_perde_o_acesso_mesmo_com_token_valido(
    client: TestClient, db_session: Session, status: UserStatus, password: str | None
) -> None:
    user = create_user(db_session, status=status, password=password)

    response = client.get("/me", headers=auth_headers(user))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_professor_nao_acessa_rota_de_admin(client: TestClient, teacher_user: User) -> None:
    response = client.get("/admin", headers=auth_headers(teacher_user))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_admin_acessa_rota_de_admin(client: TestClient, admin_user: User) -> None:
    response = client.get("/admin", headers=auth_headers(admin_user))

    assert response.status_code == 200


def test_papel_vem_do_banco_e_nao_do_token(client: TestClient, db_session: Session) -> None:
    # Admin rebaixado a professor: o token antigo ainda diz "admin", mas não vale mais.
    user = create_user(db_session, role=UserRole.ADMIN)
    old_headers = auth_headers(user)
    user.role = UserRole.TEACHER
    db_session.flush()

    response = client.get("/admin", headers=old_headers)

    assert response.status_code == 403
