"""US15 — Cadastro e edição de obras."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from tests.factories import auth_headers, create_book, create_education_level, create_theme

BOOKS = "/api/v1/books"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _create(client: TestClient, admin: User, **fields):
    files = fields.pop("files", None)
    return client.post(BOOKS, data=fields, files=files, headers=auth_headers(admin))


def _media_path(cover_url: str) -> Path:
    return Path(os.environ["MEDIA_DIR"]) / "covers" / Path(cover_url).name


def test_cadastro_completo(client: TestClient, db_session: Session, admin_user: User) -> None:
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
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "O Segredo de Aurora"
    assert body["page_count"] == 38
    assert body["year"] == 2026
    assert body["store_url"] == "https://loja.exemplo.com"
    assert body["education_level"]["name"] == "Infantil"
    assert body["themes"][0]["name"] == "Inclusão"
    assert body["is_saved"] is False


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "extension"),
    [("capa.png", PNG, "image/png", ".png"), ("capa.jpg", JPEG, "image/jpeg", ".jpg")],
    ids=["png", "jpeg"],
)
def test_cadastro_com_capa_grava_e_serve_o_arquivo(
    client: TestClient,
    admin_user: User,
    filename: str,
    content: bytes,
    content_type: str,
    extension: str,
) -> None:
    response = _create(
        client,
        admin_user,
        title="X",
        author="Y",
        files={"cover": (filename, content, content_type)},
    )

    assert response.status_code == 201
    cover_url = response.json()["cover_url"]
    assert cover_url.startswith("/media/covers/")
    assert cover_url.endswith(extension)
    assert _media_path(cover_url).read_bytes() == content
    assert client.get(cover_url).status_code == 200


def test_cadastro_minimo_so_titulo_e_autor(client: TestClient, admin_user: User) -> None:
    response = _create(client, admin_user, title="Só o Básico", author="Alguém")

    assert response.status_code == 201
    body = response.json()
    assert body["synopsis"] is None
    assert body["cover_url"] is None
    assert body["education_level"] is None
    assert body["themes"] == []


@pytest.mark.parametrize(
    ("fields", "invalid"),
    [
        ({"title": "   ", "author": "Alguém"}, "title"),
        ({"author": "Alguém"}, "title"),
        ({"title": "X", "author": ""}, "author"),
        ({"title": "X"}, "author"),
        ({"title": "X", "author": "Y", "store_url": "ftp://x"}, "store_url"),
        ({"title": "X", "author": "Y", "book_url": "nao-e-url"}, "book_url"),
        ({"title": "X", "author": "Y", "page_count": "0"}, "page_count"),
        ({"title": "X", "author": "Y", "page_count": "abc"}, "page_count"),
        ({"title": "X", "author": "Y", "year": "999"}, "year"),
        ({"title": "X", "author": "Y", "isbn": "1" * 21}, "isbn"),
    ],
    ids=[
        "titulo-em-branco",
        "sem-titulo",
        "autor-vazio",
        "sem-autor",
        "store-url-sem-http",
        "book-url-invalida",
        "paginas-zero",
        "paginas-nao-numericas",
        "ano-com-3-digitos",
        "isbn-longo",
    ],
)
def test_campo_invalido_responde_422_apontando_o_campo(
    client: TestClient, admin_user: User, fields: dict, invalid: str
) -> None:
    response = _create(client, admin_user, **fields)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert invalid in {item["loc"][-1] for item in response.json()["details"]}


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize(
    ("requester", "status_code"), [(None, 401), ("teacher_user", 403)], ids=["anonimo", "professor"]
)
def test_cadastro_e_edicao_exigem_admin(
    request: pytest.FixtureRequest,
    client: TestClient,
    db_session: Session,
    method: str,
    requester: str | None,
    status_code: int,
) -> None:
    book = create_book(db_session)
    headers = auth_headers(request.getfixturevalue(requester)) if requester else {}
    path = BOOKS if method == "post" else f"{BOOKS}/{book.id}"

    response = client.request(method, path, data={"title": "X", "author": "Y"}, headers=headers)

    assert response.status_code == status_code


@pytest.mark.parametrize("isbn", ["123", "978-65-6079-046-9"])
def test_isbn_duplicado_no_cadastro_responde_409(
    client: TestClient, admin_user: User, isbn: str
) -> None:
    _create(client, admin_user, title="Livro 1", author="A", isbn=isbn)

    response = _create(client, admin_user, title="Livro 2", author="B", isbn=isbn)

    assert response.status_code == 409
    assert response.json()["code"] == "ISBN_ALREADY_REGISTERED"


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("capa.gif", b"GIF89a" + b"\x00" * 64, "image/gif"),
        ("capa.png", b"isso nao e png", "image/png"),
    ],
    ids=["tipo-nao-aceito", "png-falso"],
)
def test_capa_com_tipo_ou_conteudo_errado_responde_422(
    client: TestClient, admin_user: User, filename: str, content: bytes, content_type: str
) -> None:
    response = _create(
        client,
        admin_user,
        title="X",
        author="Y",
        files={"cover": (filename, content, content_type)},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_INVALID"


def test_capa_acima_do_limite_responde_422(
    client: TestClient, admin_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "cover_max_bytes", 32)

    response = _create(
        client, admin_user, title="X", author="Y", files={"cover": ("capa.png", PNG, "image/png")}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_TOO_LARGE"


@pytest.mark.parametrize(
    ("data", "field", "expected"),
    [
        ({"title": "Novo"}, "title", "Novo"),
        ({"author": "Outra Autora"}, "author", "Outra Autora"),
        ({"synopsis": "nova sinopse"}, "synopsis", "nova sinopse"),
        ({"year": "2021"}, "year", 2021),
        ({"page_count": "40"}, "page_count", 40),
    ],
    ids=["titulo", "autor", "sinopse", "ano", "paginas"],
)
def test_edicao_parcial_altera_so_o_enviado(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    data: dict,
    field: str,
    expected: object,
) -> None:
    original = {
        "title": "Antigo",
        "author": "A",
        "synopsis": "texto",
        "year": 2020,
        "page_count": 10,
    }
    book = create_book(db_session, **original)

    response = client.patch(f"{BOOKS}/{book.id}", data=data, headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body[field] == expected
    for name, value in original.items():
        if name != field:
            assert body[name] == value


@pytest.mark.parametrize("field", ["synopsis", "edition", "isbn", "store_url"])
def test_edicao_com_campo_vazio_limpa_o_valor(
    client: TestClient, db_session: Session, admin_user: User, field: str
) -> None:
    book = create_book(
        db_session,
        synopsis="texto",
        edition="1ª",
        isbn="123",
        store_url="https://loja.exemplo.com",
    )

    response = client.patch(
        f"{BOOKS}/{book.id}", data={field: ""}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 200
    assert response.json()[field] is None


def test_edicao_reflete_na_busca(client: TestClient, db_session: Session, admin_user: User) -> None:
    book = create_book(db_session, title="Antigo")

    client.patch(
        f"{BOOKS}/{book.id}", data={"title": "Título Novo"}, headers=auth_headers(admin_user)
    )

    response = client.get(BOOKS, params={"q": "titulo novo"}, headers=auth_headers(admin_user))
    assert [b["id"] for b in response.json()] == [book.id]


def test_edicao_substitui_capa_e_apaga_a_antiga(client: TestClient, admin_user: User) -> None:
    created = _create(
        client, admin_user, title="X", author="Y", files={"cover": ("a.png", PNG, "image/png")}
    ).json()
    old_path = _media_path(created["cover_url"])

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
