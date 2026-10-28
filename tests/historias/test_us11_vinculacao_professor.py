"""US11 — Vinculação do professor a temas e escolaridades."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

INTERESTS = "/api/v1/me/interests"
BOOKS = "/api/v1/books"


def test_definir_interesses_substitui_o_conjunto_anterior(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    inclusao = create_theme(db_session, "Inclusão")
    aventura = create_theme(db_session, "Aventura")
    infantil = create_education_level(db_session, "Infantil")
    headers = auth_headers(teacher_user)

    response = client.put(
        INTERESTS,
        json={"theme_ids": [inclusao.id], "education_level_ids": [infantil.id]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["themes"] == [{"id": inclusao.id, "name": "Inclusão"}]
    assert response.json()["education_levels"][0]["name"] == "Infantil"

    response = client.put(
        INTERESTS,
        json={"theme_ids": [aventura.id], "education_level_ids": []},
        headers=headers,
    )
    assert [t["name"] for t in response.json()["themes"]] == ["Aventura"]
    assert response.json()["education_levels"] == []


@pytest.mark.parametrize("field", ["theme_ids", "education_level_ids"])
def test_interesses_persistem_no_banco(
    client: TestClient, db_session: Session, teacher_user: User, field: str
) -> None:
    theme = create_theme(db_session, "Inclusão")
    level = create_education_level(db_session, "Infantil")
    ids = {"theme_ids": theme.id, "education_level_ids": level.id}

    client.put(INTERESTS, json={field: [ids[field]]}, headers=auth_headers(teacher_user))

    db_session.refresh(teacher_user)
    linked = teacher_user.themes if field == "theme_ids" else teacher_user.education_levels
    assert [item.id for item in linked] == [ids[field]]


@pytest.mark.parametrize("field", ["theme_ids", "education_level_ids"])
def test_interesses_com_id_inexistente_respondem_422(
    client: TestClient, teacher_user: User, field: str
) -> None:
    response = client.put(INTERESTS, json={field: [999999]}, headers=auth_headers(teacher_user))

    assert response.status_code == 422
    assert "999999" in response.json()["details"][0]["msg"]


def test_interesses_exigem_login(client: TestClient) -> None:
    assert client.put(INTERESTS, json={"theme_ids": []}).status_code == 401


@pytest.mark.parametrize(
    ("vinculo", "sort", "expected"),
    [
        ("tema", "relevance", ["ZZZ Minha", "AAA Alheia"]),
        ("escolaridade", "relevance", ["ZZZ Minha", "AAA Alheia"]),
        ("tema", "title", ["AAA Alheia", "ZZZ Minha"]),
        ("escolaridade", "title", ["AAA Alheia", "ZZZ Minha"]),
    ],
)
def test_busca_prioriza_as_obras_dos_interesses_do_professor(
    client: TestClient,
    db_session: Session,
    teacher_user: User,
    vinculo: str,
    sort: str,
    expected: list[str],
) -> None:
    if vinculo == "tema":
        meu, outro = create_theme(db_session, "Inclusão"), create_theme(db_session, "Aventura")
        teacher_user.themes = [meu]
        create_book(db_session, title="AAA Alheia", themes=[outro])
        create_book(db_session, title="ZZZ Minha", themes=[meu])
    else:
        meu = create_education_level(db_session, "Infantil")
        outro = create_education_level(db_session, "Médio")
        teacher_user.education_levels = [meu]
        create_book(db_session, title="AAA Alheia", education_level=outro)
        create_book(db_session, title="ZZZ Minha", education_level=meu)
    db_session.flush()

    response = client.get(BOOKS, params={"sort": sort}, headers=auth_headers(teacher_user))

    assert [b["title"] for b in response.json()] == expected


def test_relevance_e_a_ordenacao_padrao(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    meu = create_theme(db_session, "Inclusão")
    teacher_user.themes = [meu]
    db_session.flush()
    create_book(db_session, title="AAA Alheia")
    create_book(db_session, title="ZZZ Minha", themes=[meu])

    response = client.get(BOOKS, headers=auth_headers(teacher_user))

    assert [b["title"] for b in response.json()] == ["ZZZ Minha", "AAA Alheia"]
