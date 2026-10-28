"""US07 — Busca de obras por nome."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

BOOKS = "/api/v1/books"

TERMO_ACENTUADO = pytest.mark.xfail(
    strict=True, reason="bug: o termo da busca não passa por unaccent, só a coluna"
)


def _titles(client: TestClient, user: User, **params) -> list[str]:
    response = client.get(BOOKS, params=params, headers=auth_headers(user))
    assert response.status_code == 200
    return [b["title"] for b in response.json()]


def test_lista_de_obras_exige_login(client: TestClient) -> None:
    assert client.get(BOOKS).status_code == 401


@pytest.mark.parametrize("saved", [True, False], ids=["salva", "nao-salva"])
def test_lista_devolve_cartao_da_obra(
    client: TestClient, db_session: Session, teacher_user: User, saved: bool
) -> None:
    theme = create_theme(db_session, "Inclusão")
    level = create_education_level(db_session, "Educação Infantil")
    book = create_book(
        db_session, title="O Segredo de Aurora", year=2026, themes=[theme], education_level=level
    )
    if saved:
        client.put(f"/api/v1/me/saved-books/{book.id}", headers=auth_headers(teacher_user))

    response = client.get(BOOKS, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    [item] = response.json()
    assert item["title"] == "O Segredo de Aurora"
    assert item["themes"] == [{"id": theme.id, "name": "Inclusão"}]
    assert item["education_level"] == {"id": level.id, "name": "Educação Infantil"}
    assert item["is_saved"] is saved
    assert "synopsis" not in item


@pytest.mark.parametrize(
    "q",
    [
        "misterio",
        "MISTERIO",
        pytest.param("MISTÉRIO", marks=TERMO_ACENTUADO),
        pytest.param("Mistério", marks=TERMO_ACENTUADO),
        "floresta",
        "o mist",
        "colli",
        "ISA COLLI",
    ],
)
def test_busca_por_trecho_do_titulo_ou_autor_ignorando_acentos_e_caixa(
    client: TestClient, db_session: Session, teacher_user: User, q: str
) -> None:
    create_book(db_session, title="O Mistério da Floresta", author="Isa Colli")
    create_book(db_session, title="Outra Obra", author="Outra Pessoa")

    assert _titles(client, teacher_user, q=q) == ["O Mistério da Floresta"]


@pytest.mark.parametrize("q", ["inexistente", "zzz", "floresta encantada"])
def test_busca_sem_resultado_devolve_lista_vazia(
    client: TestClient, db_session: Session, teacher_user: User, q: str
) -> None:
    create_book(db_session, title="O Mistério da Floresta", author="Isa Colli")

    assert _titles(client, teacher_user, q=q) == []


def test_busca_sem_termo_devolve_o_acervo_todo(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    create_book(db_session, title="A")
    create_book(db_session, title="B")

    assert sorted(_titles(client, teacher_user)) == ["A", "B"]


@pytest.mark.parametrize(
    ("params", "field"),
    [({"q": "x" * 256}, "q"), ({"sort": "inventado"}, "sort")],
)
def test_parametros_invalidos_da_busca_respondem_422(
    client: TestClient, teacher_user: User, params: dict, field: str
) -> None:
    response = client.get(BOOKS, params=params, headers=auth_headers(teacher_user))

    assert response.status_code == 422
    assert response.json()["details"][0]["loc"][-1] == field
