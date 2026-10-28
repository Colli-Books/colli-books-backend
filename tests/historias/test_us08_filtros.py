"""US08 — Filtro por tema e escolaridade."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

BOOKS = "/api/v1/books"


@pytest.fixture()
def acervo(db_session: Session) -> dict[str, int]:
    inclusao = create_theme(db_session, "Inclusão")
    aventura = create_theme(db_session, "Aventura")
    infantil = create_education_level(db_session, "Infantil")
    medio = create_education_level(db_session, "Médio")
    create_book(db_session, title="Inclusão Infantil", themes=[inclusao], education_level=infantil)
    create_book(db_session, title="Aventura Médio", themes=[aventura], education_level=medio)
    create_book(
        db_session,
        title="Dois Temas Infantil",
        themes=[inclusao, aventura],
        education_level=infantil,
    )
    create_book(db_session, title="Sem Vínculo")
    return {
        "inclusao": inclusao.id,
        "aventura": aventura.id,
        "infantil": infantil.id,
        "medio": medio.id,
    }


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"theme_id": "inclusao"}, ["Dois Temas Infantil", "Inclusão Infantil"]),
        ({"theme_id": "aventura"}, ["Aventura Médio", "Dois Temas Infantil"]),
        ({"education_level_id": "infantil"}, ["Dois Temas Infantil", "Inclusão Infantil"]),
        ({"education_level_id": "medio"}, ["Aventura Médio"]),
        ({"theme_id": "aventura", "education_level_id": "infantil"}, ["Dois Temas Infantil"]),
        ({"theme_id": "inclusao", "education_level_id": "medio"}, []),
        (
            {},
            ["Aventura Médio", "Dois Temas Infantil", "Inclusão Infantil", "Sem Vínculo"],
        ),
    ],
    ids=[
        "tema-inclusao",
        "tema-aventura",
        "escolaridade-infantil",
        "escolaridade-medio",
        "tema-e-escolaridade",
        "combinacao-sem-obras",
        "sem-filtros",
    ],
)
def test_filtros_por_tema_e_escolaridade(
    client: TestClient,
    teacher_user: User,
    acervo: dict[str, int],
    filters: dict[str, str],
    expected: list[str],
) -> None:
    params = {key: acervo[value] for key, value in filters.items()}

    response = client.get(
        BOOKS, params={**params, "sort": "title"}, headers=auth_headers(teacher_user)
    )

    assert response.status_code == 200
    assert [b["title"] for b in response.json()] == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"q": "infantil", "theme_id": "aventura"}, ["Dois Temas Infantil"]),
        (
            {"q": "infantil", "education_level_id": "infantil"},
            ["Dois Temas Infantil", "Inclusão Infantil"],
        ),
        ({"q": "medio", "theme_id": "inclusao"}, []),
    ],
)
def test_filtros_se_aplicam_sobre_o_resultado_da_busca(
    client: TestClient,
    teacher_user: User,
    acervo: dict[str, int],
    params: dict[str, str],
    expected: list[str],
) -> None:
    query = {k: (acervo[v] if k != "q" else v) for k, v in params.items()}

    response = client.get(
        BOOKS, params={**query, "sort": "title"}, headers=auth_headers(teacher_user)
    )

    assert [b["title"] for b in response.json()] == expected


@pytest.mark.parametrize("param", ["theme_id", "education_level_id"])
@pytest.mark.parametrize("value", [0, -1])
def test_filtro_com_id_nao_positivo_responde_422(
    client: TestClient, teacher_user: User, param: str, value: int
) -> None:
    response = client.get(BOOKS, params={param: value}, headers=auth_headers(teacher_user))

    assert response.status_code == 422


@pytest.mark.parametrize("param", ["theme_id", "education_level_id"])
def test_filtro_com_id_inexistente_devolve_lista_vazia(
    client: TestClient, teacher_user: User, acervo: dict[str, int], param: str
) -> None:
    response = client.get(BOOKS, params={param: 999_999}, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert response.json() == []
