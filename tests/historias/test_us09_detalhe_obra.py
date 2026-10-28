"""US09 — Detalhe da obra."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Book, User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

BOOKS = "/api/v1/books"

DETALHE = {
    "title": "Aurora",
    "author": "Andréa Avelar",
    "synopsis": "Sinopse",
    "isbn": "123",
    "page_count": 38,
    "edition": "1ª",
    "year": 2026,
    "store_url": "https://loja.exemplo.com",
    "cover_url": "https://site.exemplo.com/capa.png",
}


@pytest.fixture()
def book(db_session: Session) -> Book:
    theme = create_theme(db_session, "Inclusão")
    level = create_education_level(db_session, "Educação Infantil")
    return create_book(db_session, themes=[theme], education_level=level, **DETALHE)


@pytest.mark.parametrize(("field", "expected"), list(DETALHE.items()), ids=list(DETALHE))
def test_detalhe_traz_os_dados_da_obra(
    client: TestClient, teacher_user: User, book: Book, field: str, expected: object
) -> None:
    response = client.get(f"{BOOKS}/{book.id}", headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert response.json()[field] == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [("themes", ["Inclusão"]), ("education_level", "Educação Infantil")],
)
def test_detalhe_traz_temas_e_escolaridade_vinculados(
    client: TestClient, teacher_user: User, book: Book, field: str, expected: object
) -> None:
    body = client.get(f"{BOOKS}/{book.id}", headers=auth_headers(teacher_user)).json()

    value = body[field]
    names = [item["name"] for item in value] if isinstance(value, list) else value["name"]
    assert names == expected


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_detalhe_traz_datas_de_cadastro_e_atualizacao(
    client: TestClient, teacher_user: User, book: Book, field: str
) -> None:
    body = client.get(f"{BOOKS}/{book.id}", headers=auth_headers(teacher_user)).json()

    assert body[field]
    assert body["is_saved"] is False


def test_detalhe_exige_login(client: TestClient, book: Book) -> None:
    assert client.get(f"{BOOKS}/{book.id}").status_code == 401


@pytest.mark.parametrize(("book_id", "status_code"), [(999_999, 404), ("abc", 422)])
def test_detalhe_de_obra_inexistente_ou_id_invalido(
    client: TestClient, teacher_user: User, book_id: object, status_code: int
) -> None:
    response = client.get(f"{BOOKS}/{book_id}", headers=auth_headers(teacher_user))

    assert response.status_code == status_code
