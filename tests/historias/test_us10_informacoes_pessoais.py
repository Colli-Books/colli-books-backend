"""US10 — Informações pessoais do professor."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken, User
from tests.factories import DEFAULT_PASSWORD, auth_headers

ME = "/api/v1/me"
AUTH_ME = "/api/v1/auth/me"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"


@pytest.fixture()
def perfil_preenchido(db_session: Session, teacher_user: User) -> User:
    teacher_user.full_name = "Maria"
    teacher_user.school = "Escola X"
    db_session.flush()
    return teacher_user


@pytest.mark.parametrize(
    ("payload", "full_name", "school"),
    [
        ({"full_name": "Maria Souza", "school": "E.E. Machado"}, "Maria Souza", "E.E. Machado"),
        ({"full_name": "  Ana  "}, "Ana", "Escola X"),
        ({"school": "Escola Y"}, "Maria", "Escola Y"),
        ({"school": ""}, "Maria", None),
        ({"school": "   "}, "Maria", None),
        ({}, "Maria", "Escola X"),
    ],
    ids=["nome-e-escola", "so-nome", "so-escola", "escola-vazia", "escola-em-branco", "nada"],
)
def test_editar_perfil_altera_so_o_enviado(
    client: TestClient,
    perfil_preenchido: User,
    payload: dict,
    full_name: str,
    school: str | None,
) -> None:
    headers = auth_headers(perfil_preenchido)

    response = client.patch(ME, json=payload, headers=headers)

    assert response.status_code == 200
    assert (response.json()["full_name"], response.json()["school"]) == (full_name, school)
    me = client.get(AUTH_ME, headers=headers).json()
    assert (me["full_name"], me["school"]) == (full_name, school)


@pytest.mark.parametrize("email", ["outro@escola.com", "professor@escola.com.br"])
def test_email_e_somente_leitura(client: TestClient, teacher_user: User, email: str) -> None:
    """O e-mail é a identidade da conta: não é editável por PATCH /me."""
    response = client.patch(ME, json={"email": email}, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert response.json()["email"] == teacher_user.email


def test_sem_nome_o_perfil_identifica_pelo_email(client: TestClient, teacher_user: User) -> None:
    body = client.get(AUTH_ME, headers=auth_headers(teacher_user)).json()

    assert body["full_name"] is None
    assert body["email"] == "professor@escola.com"


@pytest.mark.parametrize("full_name", ["", "   ", "x" * 256])
def test_nome_invalido_responde_422(client: TestClient, teacher_user: User, full_name: str) -> None:
    response = client.patch(ME, json={"full_name": full_name}, headers=auth_headers(teacher_user))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_editar_perfil_exige_login(client: TestClient) -> None:
    assert client.patch(ME, json={"full_name": "X"}).status_code == 401


@pytest.mark.parametrize(
    ("current", "new", "status_code", "code"),
    [
        ("errada-qualquer", "nova-senha-123", 400, "CURRENT_PASSWORD_INVALID"),
        (DEFAULT_PASSWORD, "curta", 422, "WEAK_PASSWORD"),
        (DEFAULT_PASSWORD, "a" * 129, 422, "WEAK_PASSWORD"),
    ],
    ids=["senha-atual-errada", "nova-curta", "nova-longa"],
)
def test_trocar_senha_recusa_dados_invalidos(
    client: TestClient,
    teacher_user: User,
    current: str,
    new: str,
    status_code: int,
    code: str,
) -> None:
    response = client.put(
        f"{ME}/password",
        json={"current_password": current, "new_password": new},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_trocar_senha_encerra_as_outras_sessoes(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    other = client.post(
        LOGIN, json={"email": teacher_user.email, "password": DEFAULT_PASSWORD}
    ).json()

    response = client.put(
        f"{ME}/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-456"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 204
    ativos = db_session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == teacher_user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert list(ativos) == []
    assert client.post(REFRESH, json={"refresh_token": other["refresh_token"]}).status_code == 401


@pytest.mark.parametrize(
    ("password", "status_code"), [("nova-senha-456", 200), (DEFAULT_PASSWORD, 401)]
)
def test_depois_de_trocar_so_a_senha_nova_entra(
    client: TestClient, teacher_user: User, password: str, status_code: int
) -> None:
    client.put(
        f"{ME}/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-456"},
        headers=auth_headers(teacher_user),
    )

    response = client.post(LOGIN, json={"email": teacher_user.email, "password": password})

    assert response.status_code == status_code
