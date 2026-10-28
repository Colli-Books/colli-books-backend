"""US12 — Seleção e salvamento de obras (Minha Seleção)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Book, User
from tests.factories import auth_headers, create_book, create_user

SAVED = "/api/v1/me/saved-books"
BOOKS = "/api/v1/books"


@pytest.fixture()
def book(db_session: Session) -> Book:
    return create_book(db_session, title="Aurora")


def test_selecao_comeca_vazia(client: TestClient, teacher_user: User) -> None:
    assert client.get(SAVED, headers=auth_headers(teacher_user)).json() == []


@pytest.mark.parametrize("vezes", [1, 2, 3])
def test_salvar_obra_e_idempotente(
    client: TestClient, teacher_user: User, book: Book, vezes: int
) -> None:
    headers = auth_headers(teacher_user)

    statuses = [client.put(f"{SAVED}/{book.id}", headers=headers).status_code for _ in range(vezes)]

    assert statuses == [204] * vezes
    [item] = client.get(SAVED, headers=headers).json()
    assert item["id"] == book.id
    assert item["is_saved"] is True


@pytest.mark.parametrize("vezes", [1, 2])
def test_remover_obra_e_idempotente(
    client: TestClient, teacher_user: User, book: Book, vezes: int
) -> None:
    headers = auth_headers(teacher_user)
    client.put(f"{SAVED}/{book.id}", headers=headers)

    statuses = [
        client.delete(f"{SAVED}/{book.id}", headers=headers).status_code for _ in range(vezes)
    ]

    assert statuses == [204] * vezes
    assert client.get(SAVED, headers=headers).json() == []


@pytest.mark.parametrize("onde", ["catalogo", "detalhe"])
def test_estado_salvo_aparece_no_catalogo_e_no_detalhe(
    client: TestClient, db_session: Session, teacher_user: User, book: Book, onde: str
) -> None:
    outro = create_book(db_session, title="Outro")
    headers = auth_headers(teacher_user)
    client.put(f"{SAVED}/{book.id}", headers=headers)

    if onde == "catalogo":
        flags = {b["id"]: b["is_saved"] for b in client.get(BOOKS, headers=headers).json()}
        assert flags == {book.id: True, outro.id: False}
    else:
        assert client.get(f"{BOOKS}/{book.id}", headers=headers).json()["is_saved"] is True
        assert client.get(f"{BOOKS}/{outro.id}", headers=headers).json()["is_saved"] is False


def test_selecao_e_do_dono_do_token(
    client: TestClient, db_session: Session, teacher_user: User, book: Book
) -> None:
    """A seleção é por usuário: um professor não enxerga a do outro."""
    outro_professor = create_user(db_session)
    client.put(f"{SAVED}/{book.id}", headers=auth_headers(outro_professor))

    assert client.get(SAVED, headers=auth_headers(teacher_user)).json() == []


@pytest.mark.parametrize("method", ["put", "delete"])
def test_salvar_ou_remover_obra_inexistente_responde_404(
    client: TestClient, teacher_user: User, method: str
) -> None:
    response = client.request(method, f"{SAVED}/999999", headers=auth_headers(teacher_user))

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"), [("get", SAVED), ("put", f"{SAVED}/1"), ("delete", f"{SAVED}/1")]
)
def test_selecao_exige_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def test_selecao_ordenada_da_mais_recente_para_antiga(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    primeiro = create_book(db_session, title="Primeiro salvo")
    segundo = create_book(db_session, title="Segundo salvo")
    headers = auth_headers(teacher_user)
    client.put(f"{SAVED}/{primeiro.id}", headers=headers)
    client.put(f"{SAVED}/{segundo.id}", headers=headers)

    titles = [b["title"] for b in client.get(SAVED, headers=headers).json()]
    assert titles == ["Segundo salvo", "Primeiro salvo"]
