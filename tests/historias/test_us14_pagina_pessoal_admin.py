"""US14 — Página pessoal do administrador."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserRole
from tests.factories import DEFAULT_PASSWORD, auth_headers, create_user

LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
REFRESH = "/api/v1/auth/refresh"
ME = "/api/v1/auth/me"


@pytest.mark.parametrize("email", ["admin@colli.com", "diego@collibooks.com"])
def test_pagina_pessoal_mostra_o_email_do_admin(
    client: TestClient, db_session: Session, email: str
) -> None:
    admin = create_user(db_session, email=email, role=UserRole.ADMIN)

    response = client.get(ME, headers=auth_headers(admin))

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert response.json()["role"] == "admin"


def test_sair_encerra_a_sessao_do_admin(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, email="admin@colli.com", role=UserRole.ADMIN)
    refresh = client.post(LOGIN, json={"email": admin.email, "password": DEFAULT_PASSWORD}).json()[
        "refresh_token"
    ]

    response = client.post(LOGOUT, json={"refresh_token": refresh})

    assert response.status_code == 204
    assert client.post(REFRESH, json={"refresh_token": refresh}).status_code == 401
