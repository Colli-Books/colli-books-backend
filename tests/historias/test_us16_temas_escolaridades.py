"""US16 — Cadastro de temas e escolaridades."""

from collections.abc import Callable
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

THEMES = "/api/v1/themes"
LEVELS = "/api/v1/education-levels"


class Recurso(NamedTuple):
    path: str
    factory: Callable[..., object]
    duplicate_code: str


RECURSOS = [
    pytest.param(Recurso(THEMES, create_theme, "THEME_ALREADY_EXISTS"), id="temas"),
    pytest.param(
        Recurso(LEVELS, create_education_level, "EDUCATION_LEVEL_ALREADY_EXISTS"),
        id="escolaridades",
    ),
]


@pytest.mark.parametrize("recurso", RECURSOS)
def test_listagem_exige_login(client: TestClient, recurso: Recurso) -> None:
    assert client.get(recurso.path).status_code == 401


def test_lista_de_temas_em_ordem_alfabetica(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    for name in ("Inclusão", "aventura", "Bullying"):
        create_theme(db_session, name)

    response = client.get(THEMES, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["aventura", "Bullying", "Inclusão"]


def test_escolaridades_em_ordem_pedagogica(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    create_education_level(db_session, "Ensino Médio", sort_order=3)
    create_education_level(db_session, "Educação Infantil", sort_order=1)
    create_education_level(db_session, "Fundamental I", sort_order=2)

    response = client.get(LEVELS, headers=auth_headers(teacher_user))

    assert [lv["name"] for lv in response.json()] == [
        "Educação Infantil",
        "Fundamental I",
        "Ensino Médio",
    ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"name": "Empatia", "description": "Obras sobre empatia"},
            {"name": "Empatia", "description": "Obras sobre empatia"},
        ),
        ({"name": "  Amizade  "}, {"name": "Amizade", "description": None}),
        ({"name": "Respeito", "description": "   "}, {"name": "Respeito", "description": None}),
    ],
    ids=["com-descricao", "sem-descricao", "descricao-em-branco"],
)
def test_criar_tema(client: TestClient, admin_user: User, payload: dict, expected: dict) -> None:
    response = client.post(THEMES, json=payload, headers=auth_headers(admin_user))

    assert response.status_code == 201
    body = response.json()
    assert {k: body[k] for k in expected} == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"name": "Ensino Médio", "sort_order": 4}, {"name": "Ensino Médio", "sort_order": 4}),
        ({"name": "Fundamental II", "sort_order": 3}, {"name": "Fundamental II", "sort_order": 3}),
    ],
)
def test_criar_escolaridade(
    client: TestClient, admin_user: User, payload: dict, expected: dict
) -> None:
    response = client.post(LEVELS, json=payload, headers=auth_headers(admin_user))

    assert response.status_code == 201
    body = response.json()
    assert {k: body[k] for k in expected} == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"sort_order": 9}, {"name": "Ensino Médio", "sort_order": 9}),
        ({"name": "Médio"}, {"name": "Médio", "sort_order": 4}),
        ({"name": "Médio", "sort_order": 1}, {"name": "Médio", "sort_order": 1}),
    ],
    ids=["so-ordem", "so-nome", "nome-e-ordem"],
)
def test_editar_escolaridade(
    client: TestClient, db_session: Session, admin_user: User, payload: dict, expected: dict
) -> None:
    level = create_education_level(db_session, "Ensino Médio", sort_order=4)

    response = client.patch(f"{LEVELS}/{level.id}", json=payload, headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json() == {"id": level.id, **expected}


@pytest.mark.parametrize("recurso", RECURSOS)
@pytest.mark.parametrize("duplicate", ["Empatia", "  EMPATIA ", "empatia"])
def test_nome_duplicado_no_cadastro_responde_409(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    recurso: Recurso,
    duplicate: str,
) -> None:
    recurso.factory(db_session, "Empatia")

    response = client.post(recurso.path, json={"name": duplicate}, headers=auth_headers(admin_user))

    assert response.status_code == 409
    assert response.json()["code"] == recurso.duplicate_code


@pytest.mark.parametrize("recurso", RECURSOS)
def test_renomear_para_nome_ja_usado_responde_409(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    recurso: Recurso,
) -> None:
    recurso.factory(db_session, "Empatia")
    item = recurso.factory(db_session, "Amizade")

    response = client.patch(
        f"{recurso.path}/{item.id}", json={"name": "empatia"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 409
    assert response.json()["code"] == recurso.duplicate_code


@pytest.mark.parametrize("recurso", RECURSOS)
@pytest.mark.parametrize("method", ["post", "patch"])
def test_professor_nao_cria_nem_renomeia(
    client: TestClient,
    db_session: Session,
    teacher_user: User,
    recurso: Recurso,
    method: str,
) -> None:
    item = recurso.factory(db_session, "Empatia")
    url = recurso.path if method == "post" else f"{recurso.path}/{item.id}"

    response = client.request(
        method, url, json={"name": "Outro"}, headers=auth_headers(teacher_user)
    )

    assert response.status_code == 403


@pytest.mark.parametrize("recurso", RECURSOS)
def test_renomear_inexistente_responde_404(
    client: TestClient, admin_user: User, recurso: Recurso
) -> None:
    response = client.patch(
        f"{recurso.path}/999999", json={"name": "X"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 404


@pytest.mark.parametrize("recurso", RECURSOS)
@pytest.mark.parametrize("name", ["", "   ", "x" * 121])
def test_nome_invalido_responde_422(
    client: TestClient,
    admin_user: User,
    recurso: Recurso,
    name: str,
) -> None:
    response = client.post(recurso.path, json={"name": name}, headers=auth_headers(admin_user))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_renomear_tema_preserva_vinculo_com_obras(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    theme = create_theme(db_session, "Empatia")
    book = create_book(db_session, themes=[theme])

    response = client.patch(
        f"{THEMES}/{theme.id}",
        json={"name": "Empatia e Respeito"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    db_session.refresh(book)
    assert [t.name for t in book.themes] == ["Empatia e Respeito"]


def test_renomear_escolaridade_preserva_vinculo_com_obras(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    level = create_education_level(db_session, "Infantil")
    book = create_book(db_session, education_level=level)

    response = client.patch(
        f"{LEVELS}/{level.id}", json={"name": "Educação Infantil"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 200
    db_session.refresh(book)
    assert book.education_level.name == "Educação Infantil"


@pytest.mark.parametrize("recurso", RECURSOS)
def test_cadastrado_pelo_admin_aparece_para_o_professor(
    client: TestClient,
    admin_user: User,
    teacher_user: User,
    recurso: Recurso,
) -> None:
    client.post(recurso.path, json={"name": "Novo Item"}, headers=auth_headers(admin_user))

    response = client.get(recurso.path, headers=auth_headers(teacher_user))

    assert "Novo Item" in [item["name"] for item in response.json()]
