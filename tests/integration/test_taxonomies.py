"""US16: listagem aberta a logados; cadastro e renomeação só do admin."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import (
    auth_headers,
    create_book,
    create_education_level,
    create_theme,
)

THEMES = "/api/v1/themes"
LEVELS = "/api/v1/education-levels"


# --- Temas -----------------------------------------------------------------


def test_lista_de_temas_exige_login(client: TestClient) -> None:
    assert client.get(THEMES).status_code == 401


def test_lista_de_temas_em_ordem_alfabetica(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    create_theme(db_session, "Inclusão")
    create_theme(db_session, "aventura")
    create_theme(db_session, "Bullying")

    response = client.get(THEMES, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["aventura", "Bullying", "Inclusão"]


def test_criar_tema(client: TestClient, admin_user: User) -> None:
    response = client.post(
        THEMES,
        json={"name": "Empatia", "description": "Obras sobre empatia"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Empatia"
    assert body["description"] == "Obras sobre empatia"


def test_tema_duplicado_ignora_caixa_e_espacos(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_theme(db_session, "Empatia")

    response = client.post(THEMES, json={"name": "  EMPATIA "}, headers=auth_headers(admin_user))

    assert response.status_code == 409
    assert response.json()["code"] == "THEME_ALREADY_EXISTS"


def test_professor_nao_cria_nem_renomeia_tema(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    theme = create_theme(db_session, "Empatia")
    headers = auth_headers(teacher_user)

    assert client.post(THEMES, json={"name": "Outro"}, headers=headers).status_code == 403
    assert (
        client.patch(f"{THEMES}/{theme.id}", json={"name": "X"}, headers=headers).status_code == 403
    )


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
    assert response.json()["name"] == "Empatia e Respeito"
    db_session.refresh(book)
    assert [t.name for t in book.themes] == ["Empatia e Respeito"]


def test_renomear_para_nome_ja_usado_responde_409(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_theme(db_session, "Empatia")
    theme = create_theme(db_session, "Amizade")

    response = client.patch(
        f"{THEMES}/{theme.id}", json={"name": "empatia"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "THEME_ALREADY_EXISTS"


def test_tema_inexistente_responde_404(client: TestClient, admin_user: User) -> None:
    response = client.patch(
        f"{THEMES}/999999", json={"name": "X"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 404


def test_nome_vazio_responde_422(client: TestClient, admin_user: User) -> None:
    response = client.post(THEMES, json={"name": "   "}, headers=auth_headers(admin_user))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


# --- Escolaridades ----------------------------------------------------------


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


def test_criar_e_renomear_escolaridade(client: TestClient, admin_user: User) -> None:
    created = client.post(
        LEVELS, json={"name": "Ensino Médio", "sort_order": 4}, headers=auth_headers(admin_user)
    )
    assert created.status_code == 201
    level_id = created.json()["id"]

    renamed = client.patch(
        f"{LEVELS}/{level_id}", json={"sort_order": 9}, headers=auth_headers(admin_user)
    )
    assert renamed.status_code == 200
    assert renamed.json() == {"id": level_id, "name": "Ensino Médio", "sort_order": 9}


def test_escolaridade_duplicada_responde_409(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_education_level(db_session, "Ensino Médio")

    response = client.post(LEVELS, json={"name": "ENSINO MÉDIO"}, headers=auth_headers(admin_user))

    assert response.status_code == 409
    assert response.json()["code"] == "EDUCATION_LEVEL_ALREADY_EXISTS"
