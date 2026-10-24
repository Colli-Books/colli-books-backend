"""Gestão de professores e painel do admin (US13)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserStatus
from tests.factories import auth_headers, create_book, create_user

TEACHERS = "/api/v1/admin/teachers"
OVERVIEW = "/api/v1/admin/overview"


# --- GET /admin/teachers ------------------------------------------------------


def test_lista_professores_sem_filtro(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    ativo = create_user(db_session, email="ativo@escola.com", full_name="Ana")
    pendente = create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)
    create_user(db_session, email="inativo@escola.com", status=UserStatus.INACTIVE)

    response = client.get(TEACHERS, headers=auth_headers(admin_user))

    assert response.status_code == 200
    items = response.json()
    ids = {t["id"] for t in items}
    # O próprio admin não aparece na listagem de professores.
    assert admin_user.id not in ids
    assert {ativo.id, pendente.id} <= ids
    assert all(set(t) == {"id", "email", "full_name", "school", "role", "status"} for t in items)


def test_filtro_por_status(client: TestClient, db_session: Session, admin_user: User) -> None:
    create_user(db_session, full_name="Ativa")
    pendente = create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)

    response = client.get(
        TEACHERS, params={"status": "invite_pending"}, headers=auth_headers(admin_user)
    )

    assert [t["id"] for t in response.json()] == [pendente.id]


def test_busca_por_nome_e_email_ignorando_acentos(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_user(db_session, full_name="José da Silva")
    create_user(db_session, email="ines@escola.com", full_name="Inês Rocha")
    create_user(db_session, full_name="Carlos Nadaver")
    headers = auth_headers(admin_user)

    assert [
        t["full_name"] for t in client.get(TEACHERS, params={"q": "jose"}, headers=headers).json()
    ] == ["José da Silva"]
    assert [
        t["full_name"]
        for t in client.get(TEACHERS, params={"q": "INES@escola"}, headers=headers).json()
    ] == ["Inês Rocha"]


def test_status_invalido_responde_422(client: TestClient, admin_user: User) -> None:
    response = client.get(
        TEACHERS, params={"status": "inventado"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 422


def test_listagem_e_overview_exigem_admin(client: TestClient, teacher_user: User) -> None:
    headers = auth_headers(teacher_user)
    assert client.get(TEACHERS, headers=headers).status_code == 403
    assert client.get(OVERVIEW, headers=headers).status_code == 403
    assert client.get(TEACHERS).status_code == 401


# --- GET /admin/overview ------------------------------------------------------


def test_overview_conta_obras_professores_e_convites(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_book(db_session)
    create_book(db_session)
    create_user(db_session, email="a@e.com")
    create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)
    create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)

    response = client.get(OVERVIEW, headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json() == {
        "books_count": 2,
        "teachers_count": 3,
        "pending_invites_count": 2,
    }
