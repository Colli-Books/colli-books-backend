"""US13 — Página de início do administrador (visão geral e professores)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserStatus
from tests.factories import auth_headers, create_book, create_user

TEACHERS = "/api/v1/admin/teachers"
OVERVIEW = "/api/v1/admin/overview"


@pytest.fixture()
def professores(db_session: Session) -> dict[str, User]:
    return {
        "active": create_user(db_session, email="ativo@escola.com", full_name="Ana"),
        "invite_pending": create_user(db_session, status=UserStatus.INVITE_PENDING, password=None),
        "inactive": create_user(db_session, email="inativo@escola.com", status=UserStatus.INACTIVE),
    }


def test_lista_professores_sem_filtro(
    client: TestClient, admin_user: User, professores: dict[str, User]
) -> None:
    response = client.get(TEACHERS, headers=auth_headers(admin_user))

    assert response.status_code == 200
    items = response.json()
    ids = {t["id"] for t in items}
    assert admin_user.id not in ids
    assert {professores["active"].id, professores["invite_pending"].id} <= ids
    assert all(set(t) == {"id", "email", "full_name", "school", "role", "status"} for t in items)


@pytest.mark.parametrize("status", ["active", "invite_pending", "inactive"])
def test_filtro_por_status(
    client: TestClient, admin_user: User, professores: dict[str, User], status: str
) -> None:
    response = client.get(TEACHERS, params={"status": status}, headers=auth_headers(admin_user))

    assert [t["id"] for t in response.json()] == [professores[status].id]


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("jose", "José da Silva"),
        pytest.param(
            "JOSÉ",
            "José da Silva",
            marks=pytest.mark.xfail(
                strict=True,
                reason="bug: o termo da busca não passa por unaccent, só a coluna",
            ),
        ),
        ("silva", "José da Silva"),
        ("INES@escola", "Inês Rocha"),
        ("ines", "Inês Rocha"),
    ],
)
def test_busca_por_nome_e_email_ignorando_acentos(
    client: TestClient, db_session: Session, admin_user: User, q: str, expected: str
) -> None:
    create_user(db_session, full_name="José da Silva")
    create_user(db_session, email="ines@escola.com", full_name="Inês Rocha")
    create_user(db_session, full_name="Carlos Nadaver")

    response = client.get(TEACHERS, params={"q": q}, headers=auth_headers(admin_user))

    assert [t["full_name"] for t in response.json()] == [expected]


def test_status_invalido_responde_422(client: TestClient, admin_user: User) -> None:
    response = client.get(
        TEACHERS, params={"status": "inventado"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 422


@pytest.mark.parametrize("path", [TEACHERS, OVERVIEW])
@pytest.mark.parametrize(
    ("requester", "status_code"), [(None, 401), ("teacher_user", 403)], ids=["anonimo", "professor"]
)
def test_painel_exige_admin(
    request: pytest.FixtureRequest,
    client: TestClient,
    path: str,
    requester: str | None,
    status_code: int,
) -> None:
    headers = auth_headers(request.getfixturevalue(requester)) if requester else {}

    assert client.get(path, headers=headers).status_code == status_code


@pytest.mark.parametrize(
    ("books", "active", "pending", "expected"),
    [
        (0, 0, 0, {"books_count": 0, "teachers_count": 0, "pending_invites_count": 0}),
        (2, 1, 2, {"books_count": 2, "teachers_count": 3, "pending_invites_count": 2}),
        (1, 3, 0, {"books_count": 1, "teachers_count": 3, "pending_invites_count": 0}),
    ],
)
def test_overview_conta_obras_professores_e_convites(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    books: int,
    active: int,
    pending: int,
    expected: dict[str, int],
) -> None:
    for _ in range(books):
        create_book(db_session)
    for _ in range(active):
        create_user(db_session)
    for _ in range(pending):
        create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)

    response = client.get(OVERVIEW, headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json() == expected
