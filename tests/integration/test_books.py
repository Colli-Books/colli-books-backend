"""US07–US09 (busca e detalhe) e US15–US17 (cadastro e edição multipart)."""

import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from tests.factories import (
    auth_headers,
    create_book,
    create_education_level,
    create_theme,
)

BOOKS = "/api/v1/books"

# Assinaturas válidas seguidas de enchimento — o serviço valida os bytes mágicos.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _create(client: TestClient, admin: User, **fields):
    files = fields.pop("files", None)
    return client.post(BOOKS, data=fields, files=files, headers=auth_headers(admin))


def test_lista_de_obras_exige_login(client: TestClient) -> None:
    assert client.get(BOOKS).status_code == 401


def test_lista_devolve_cartao_com_is_saved(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    theme = create_theme(db_session, "Inclusão")
    level = create_education_level(db_session, "Educação Infantil")
    book = create_book(
        db_session, title="O Segredo de Aurora", year=2026, themes=[theme], education_level=level
    )
    client.put(f"/api/v1/me/saved-books/{book.id}", headers=auth_headers(teacher_user))

    response = client.get(BOOKS, headers=auth_headers(teacher_user))

    assert response.status_code == 200
    [item] = response.json()
    assert item["title"] == "O Segredo de Aurora"
    assert item["themes"] == [{"id": theme.id, "name": "Inclusão"}]
    assert item["education_level"] == {"id": level.id, "name": "Educação Infantil"}
    assert item["is_saved"] is True
    # O cartão não carrega os campos do detalhe.
    assert "synopsis" not in item


def test_busca_por_titulo_e_autor_ignorando_acentos(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    create_book(db_session, title="O Mistério da Floresta", author="Isa Colli")
    create_book(db_session, title="Outra Obra", author="Outra Pessoa")
    headers = auth_headers(teacher_user)

    assert [
        b["title"] for b in client.get(BOOKS, params={"q": "misterio"}, headers=headers).json()
    ] == ["O Mistério da Floresta"]
    assert [
        b["title"] for b in client.get(BOOKS, params={"q": "COLLI"}, headers=headers).json()
    ] == ["O Mistério da Floresta"]


def test_busca_sem_resultado_devolve_lista_vazia(client: TestClient, teacher_user: User) -> None:
    response = client.get(BOOKS, params={"q": "inexistente"}, headers=auth_headers(teacher_user))
    assert response.status_code == 200
    assert response.json() == []


def test_filtros_por_tema_e_escolaridade(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    inclusao = create_theme(db_session, "Inclusão")
    aventura = create_theme(db_session, "Aventura")
    infantil = create_education_level(db_session, "Infantil")
    create_book(db_session, title="Com Tema e Nível", themes=[inclusao], education_level=infantil)
    create_book(db_session, title="Só Outro Tema", themes=[aventura])
    headers = auth_headers(teacher_user)

    assert [
        b["title"]
        for b in client.get(BOOKS, params={"theme_id": inclusao.id}, headers=headers).json()
    ] == ["Com Tema e Nível"]
    assert [
        b["title"]
        for b in client.get(
            BOOKS, params={"education_level_id": infantil.id}, headers=headers
        ).json()
    ] == ["Com Tema e Nível"]


def test_ordenacao_relevance_prioriza_interesses_do_professor(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    meu_tema = create_theme(db_session, "Inclusão")
    outro_tema = create_theme(db_session, "Aventura")
    teacher_user.themes = [meu_tema]
    db_session.flush()
    create_book(db_session, title="AAA Alheia", themes=[outro_tema])
    create_book(db_session, title="ZZZ Minha", themes=[meu_tema])
    headers = auth_headers(teacher_user)

    titles = [b["title"] for b in client.get(BOOKS, headers=headers).json()]
    assert titles == ["ZZZ Minha", "AAA Alheia"]

    titles = [
        b["title"] for b in client.get(BOOKS, params={"sort": "title"}, headers=headers).json()
    ]
    assert titles == ["AAA Alheia", "ZZZ Minha"]


def test_detalhe_completo_e_404(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    book = create_book(
        db_session,
        title="Aurora",
        synopsis="Sinopse",
        isbn="123",
        page_count=38,
        edition="1ª",
        year=2026,
        store_url="https://loja.exemplo.com",
    )

    response = client.get(f"{BOOKS}/{book.id}", headers=auth_headers(teacher_user))

    assert response.status_code == 200
    body = response.json()
    assert body["synopsis"] == "Sinopse"
    assert body["isbn"] == "123"
    assert body["page_count"] == 38
    assert body["store_url"] == "https://loja.exemplo.com"
    assert body["is_saved"] is False
    assert "created_at" in body and "updated_at" in body

    assert client.get(f"{BOOKS}/999999", headers=auth_headers(teacher_user)).status_code == 404


# --- Cadastro (multipart) ----------------------------------------------------


def test_cadastro_completo_com_capa(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    tema = create_theme(db_session, "Inclusão")
    nivel = create_education_level(db_session, "Infantil")

    response = _create(
        client,
        admin_user,
        title="O Segredo de Aurora",
        author="Andréa Avelar",
        synopsis="Sinopse",
        isbn="978-65-6079-046-9",
        page_count="38",
        year="2026",
        edition="1ª",
        store_url="https://loja.exemplo.com",
        book_url="https://site.exemplo.com/lp",
        education_level_id=str(nivel.id),
        theme_ids=[str(tema.id)],
        files={"cover": ("capa.png", PNG, "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "O Segredo de Aurora"
    assert body["page_count"] == 38
    assert body["year"] == 2026
    assert body["education_level"]["name"] == "Infantil"
    assert body["themes"][0]["name"] == "Inclusão"
    assert body["cover_url"].startswith("/media/covers/")
    assert body["is_saved"] is False

    # O arquivo foi gravado na pasta servida em /media e é baixável de lá.
    media_file = Path(os.environ["MEDIA_DIR"]) / "covers" / Path(body["cover_url"]).name
    assert media_file.read_bytes() == PNG
    assert client.get(body["cover_url"]).status_code == 200


def test_cadastro_minimo_so_titulo_e_autor(client: TestClient, admin_user: User) -> None:
    response = _create(client, admin_user, title="Só o Básico", author="Alguém")

    assert response.status_code == 201
    body = response.json()
    assert body["synopsis"] is None
    assert body["cover_url"] is None
    assert body["education_level"] is None
    assert body["themes"] == []


def test_cadastro_sem_titulo_responde_422(client: TestClient, admin_user: User) -> None:
    response = _create(client, admin_user, title="   ", author="Alguém")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_cadastro_exige_admin(client: TestClient, teacher_user: User) -> None:
    response = client.post(
        BOOKS,
        data={"title": "X", "author": "Y"},
        headers=auth_headers(teacher_user),
    )
    assert response.status_code == 403


def test_isbn_duplicado_responde_409(client: TestClient, admin_user: User) -> None:
    _create(client, admin_user, title="Livro 1", author="A", isbn="123")

    response = _create(client, admin_user, title="Livro 2", author="B", isbn="123")

    assert response.status_code == 409
    assert response.json()["code"] == "ISBN_ALREADY_REGISTERED"


def test_tema_ou_escolaridade_inexistente_responde_422_com_campo(
    client: TestClient, admin_user: User
) -> None:
    response = _create(
        client, admin_user, title="X", author="Y", theme_ids=["999"], education_level_id="888"
    )

    assert response.status_code == 422
    fields = {item["loc"][-1] for item in response.json()["details"]}
    assert fields == {"education_level_id", "theme_ids"}


def test_capa_com_tipo_ou_conteudo_errado_responde_422(
    client: TestClient, admin_user: User
) -> None:
    gif = _create(
        client,
        admin_user,
        title="X",
        author="Y",
        files={"cover": ("capa.gif", b"GIF89a" + b"\x00" * 64, "image/gif")},
    )
    assert gif.status_code == 422
    assert gif.json()["code"] == "IMAGE_INVALID"

    fake_png = _create(
        client,
        admin_user,
        title="X",
        author="Y",
        files={"cover": ("capa.png", b"isso nao e png", "image/png")},
    )
    assert fake_png.status_code == 422
    assert fake_png.json()["code"] == "IMAGE_INVALID"


def test_capa_acima_do_limite_responde_422(
    client: TestClient, admin_user: User, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "cover_max_bytes", 32)

    response = _create(
        client,
        admin_user,
        title="X",
        author="Y",
        files={"cover": ("capa.png", PNG, "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_TOO_LARGE"


def test_url_sem_http_responde_422(client: TestClient, admin_user: User) -> None:
    response = _create(client, admin_user, title="X", author="Y", store_url="ftp://x")

    assert response.status_code == 422


# --- Edição (multipart) ------------------------------------------------------


def test_edicao_parcial_altera_so_o_enviado(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    book = create_book(db_session, title="Antigo", author="A", synopsis="texto", year=2020)

    response = client.patch(
        f"{BOOKS}/{book.id}", data={"title": "Novo"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Novo"
    assert body["synopsis"] == "texto"
    assert body["year"] == 2020


def test_edicao_campo_vazio_limpa_e_theme_ids_vazio_remove_vinculos(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    tema = create_theme(db_session, "Inclusão")
    book = create_book(db_session, title="X", author="A", synopsis="texto", themes=[tema])

    response = client.patch(
        f"{BOOKS}/{book.id}",
        data={"synopsis": "", "theme_ids": ""},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    assert response.json()["synopsis"] is None
    assert response.json()["themes"] == []


def test_edicao_substitui_capa_e_apaga_a_antiga(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    created = _create(
        client, admin_user, title="X", author="Y", files={"cover": ("a.png", PNG, "image/png")}
    ).json()
    old_path = Path(os.environ["MEDIA_DIR"]) / "covers" / Path(created["cover_url"]).name

    response = client.patch(
        f"{BOOKS}/{created['id']}",
        files={"cover": ("b.jpg", JPEG, "image/jpeg")},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    assert response.json()["cover_url"].endswith(".jpg")
    assert not old_path.exists()


def test_edicao_de_inexistente_responde_404(client: TestClient, admin_user: User) -> None:
    response = client.patch(
        f"{BOOKS}/999999", data={"title": "X"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 404


def test_edicao_isbn_ja_usado_responde_409(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    create_book(db_session, isbn="111")
    book = create_book(db_session, isbn="222")

    response = client.patch(
        f"{BOOKS}/{book.id}", data={"isbn": "111"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ISBN_ALREADY_REGISTERED"
