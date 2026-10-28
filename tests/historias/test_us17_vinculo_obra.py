"""US17 — Vínculo entre obra, temas e escolaridades."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

BOOKS = "/api/v1/books"


def _titles(client: TestClient, user: User, **params) -> list[str]:
    response = client.get(BOOKS, params=params, headers=auth_headers(user))
    return [b["title"] for b in response.json()]


@pytest.mark.parametrize("theme_index", [0, 1, 2])
def test_obra_com_varios_temas_aparece_na_busca_de_cada_um(
    client: TestClient, db_session: Session, admin_user: User, theme_index: int
) -> None:
    temas = [create_theme(db_session, n) for n in ("Inclusão", "Aventura", "Amizade")]
    nivel = create_education_level(db_session, "Infantil")

    response = client.post(
        BOOKS,
        data={
            "title": "Multitemas",
            "author": "A",
            "theme_ids": [str(t.id) for t in temas],
            "education_level_id": str(nivel.id),
        },
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 201
    assert _titles(client, admin_user, theme_id=temas[theme_index].id) == ["Multitemas"]
    assert _titles(client, admin_user, education_level_id=nivel.id) == ["Multitemas"]


@pytest.mark.parametrize("removed", [0, 1])
def test_remover_um_tema_tira_a_obra_so_daquele_tema(
    client: TestClient, db_session: Session, admin_user: User, removed: int
) -> None:
    temas = [create_theme(db_session, "Inclusão"), create_theme(db_session, "Aventura")]
    book = create_book(db_session, title="Obra", themes=temas)
    kept = temas[1 - removed]

    response = client.patch(
        f"{BOOKS}/{book.id}", data={"theme_ids": [str(kept.id)]}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 200
    assert [t["id"] for t in response.json()["themes"]] == [kept.id]
    assert _titles(client, admin_user, theme_id=temas[removed].id) == []
    assert _titles(client, admin_user, theme_id=kept.id) == ["Obra"]


@pytest.mark.parametrize(
    ("data", "field", "expected"),
    [
        ({"theme_ids": ""}, "themes", []),
        ({"education_level_id": ""}, "education_level", None),
    ],
    ids=["temas", "escolaridade"],
)
def test_obra_pode_ficar_sem_vinculo_e_continua_cadastrada(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    data: dict,
    field: str,
    expected: object,
) -> None:
    tema = create_theme(db_session, "Inclusão")
    nivel = create_education_level(db_session, "Infantil")
    book = create_book(db_session, title="Obra", themes=[tema], education_level=nivel)

    response = client.patch(f"{BOOKS}/{book.id}", data=data, headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json()[field] == expected
    assert client.get(f"{BOOKS}/{book.id}", headers=auth_headers(admin_user)).status_code == 200


@pytest.mark.parametrize("param", ["theme_id", "education_level_id"])
def test_obra_sem_vinculo_nao_aparece_nos_filtros(
    client: TestClient, db_session: Session, admin_user: User, param: str
) -> None:
    tema = create_theme(db_session, "Inclusão")
    nivel = create_education_level(db_session, "Infantil")
    create_book(db_session, title="Sem Vínculo")
    ids = {"theme_id": tema.id, "education_level_id": nivel.id}

    assert _titles(client, admin_user, **{param: ids[param]}) == []
    assert _titles(client, admin_user) == ["Sem Vínculo"]


@pytest.mark.parametrize(
    ("data", "fields"),
    [
        ({"theme_ids": ["999"]}, {"theme_ids"}),
        ({"education_level_id": "888"}, {"education_level_id"}),
        ({"theme_ids": ["999"], "education_level_id": "888"}, {"theme_ids", "education_level_id"}),
    ],
    ids=["tema", "escolaridade", "ambos"],
)
@pytest.mark.parametrize("method", ["post", "patch"])
def test_vinculo_inexistente_responde_422_apontando_cada_campo(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    data: dict,
    fields: set[str],
    method: str,
) -> None:
    path = BOOKS if method == "post" else f"{BOOKS}/{create_book(db_session).id}"

    response = client.request(
        method, path, data={"title": "X", "author": "Y", **data}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 422
    assert {item["loc"][-1] for item in response.json()["details"]} == fields
