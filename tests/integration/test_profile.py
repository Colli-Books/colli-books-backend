"""US10–US12: perfil, troca de senha, interesses e Minha Seleção."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken, User
from tests.factories import (
    DEFAULT_PASSWORD,
    auth_headers,
    create_book,
    create_education_level,
    create_theme,
    create_user,
)

ME = "/api/v1/me"


# --- Perfil (US10) -----------------------------------------------------------


def test_editar_perfil_atualiza_nome_e_escola(client: TestClient, teacher_user: User) -> None:
    response = client.patch(
        ME,
        json={"full_name": "Maria Souza", "school": "E.E. Machado de Assis"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Maria Souza"
    assert body["school"] == "E.E. Machado de Assis"
    assert body["email"] == teacher_user.email


def test_editar_perfil_campo_ausente_nao_altera_e_escola_vazia_limpa(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    teacher_user.full_name = "Maria"
    teacher_user.school = "Escola X"
    db_session.flush()
    headers = auth_headers(teacher_user)

    body = client.patch(ME, json={"school": "Escola Y"}, headers=headers).json()
    assert body["full_name"] == "Maria"  # ausente: mantido

    body = client.patch(ME, json={"school": ""}, headers=headers).json()
    assert body["school"] is None  # vazia: limpa


def test_perfil_nao_aceita_email(client: TestClient, teacher_user: User) -> None:
    """O e-mail é a identidade da conta: não é editável por PATCH /me."""
    response = client.patch(
        ME, json={"email": "outro@escola.com"}, headers=auth_headers(teacher_user)
    )

    assert response.status_code == 200
    assert response.json()["email"] == teacher_user.email


def test_nome_vazio_responde_422(client: TestClient, teacher_user: User) -> None:
    response = client.patch(ME, json={"full_name": "  "}, headers=auth_headers(teacher_user))
    assert response.status_code == 422


# --- Troca de senha -----------------------------------------------------------


def test_trocar_senha_exige_senha_atual(client: TestClient, teacher_user: User) -> None:
    response = client.put(
        f"{ME}/password",
        json={"current_password": "errada-qualquer", "new_password": "nova-senha-123"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CURRENT_PASSWORD_INVALID"


def test_trocar_senha_valida_forca(client: TestClient, teacher_user: User) -> None:
    response = client.put(
        f"{ME}/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "curta"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "WEAK_PASSWORD"


def test_trocar_senha_encerra_as_outras_sessoes(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    # Uma segunda sessão aberta (ex.: outro aparelho).
    other = client.post(
        "/api/v1/auth/login",
        json={"email": teacher_user.email, "password": DEFAULT_PASSWORD},
    ).json()

    response = client.put(
        f"{ME}/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "nova-senha-456"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 204
    # Todos os refresh tokens do usuário foram revogados.
    ativos = db_session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == teacher_user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert list(ativos) == []
    # O refresh da outra sessão já não vale; o login com a senha nova funciona.
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": teacher_user.email, "password": "nova-senha-456"},
        ).status_code
        == 200
    )


# --- Interesses (US11) --------------------------------------------------------


def test_definir_interesses_substitui_e_lista(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    inclusao = create_theme(db_session, "Inclusão")
    aventura = create_theme(db_session, "Aventura")
    infantil = create_education_level(db_session, "Infantil")
    headers = auth_headers(teacher_user)

    response = client.put(
        f"{ME}/interests",
        json={"theme_ids": [inclusao.id], "education_level_ids": [infantil.id]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["themes"] == [{"id": inclusao.id, "name": "Inclusão"}]
    assert response.json()["education_levels"][0]["name"] == "Infantil"

    # Substituição integral: o conjunto novo substitui o anterior.
    response = client.put(
        f"{ME}/interests",
        json={"theme_ids": [aventura.id], "education_level_ids": []},
        headers=headers,
    )
    assert [t["name"] for t in response.json()["themes"]] == ["Aventura"]
    assert response.json()["education_levels"] == []


def test_interesses_com_id_inexistente_responde_422(client: TestClient, teacher_user: User) -> None:
    response = client.put(
        f"{ME}/interests",
        json={"theme_ids": [999999]},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 422
    assert "999999" in response.json()["details"][0]["msg"]


# --- Minha Seleção (US12) ------------------------------------------------------


def test_minha_selecao_fluxo_completo_e_idempotente(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    book = create_book(db_session, title="Aurora")
    outro = create_book(db_session, title="Outro")
    headers = auth_headers(teacher_user)
    url = f"{ME}/saved-books/{book.id}"

    assert client.get(f"{ME}/saved-books", headers=headers).json() == []

    assert client.put(url, headers=headers).status_code == 204
    assert client.put(url, headers=headers).status_code == 204  # idempotente

    [item] = client.get(f"{ME}/saved-books", headers=headers).json()
    assert item["id"] == book.id
    assert item["is_saved"] is True

    # O flag aparece no catálogo e no detalhe.
    catalogo = {b["id"]: b["is_saved"] for b in client.get(BOOKS_PATH, headers=headers).json()}
    assert catalogo == {book.id: True, outro.id: False}
    assert client.get(f"{BOOKS_PATH}/{book.id}", headers=headers).json()["is_saved"] is True

    assert client.delete(url, headers=headers).status_code == 204
    assert client.delete(url, headers=headers).status_code == 204  # idempotente
    assert client.get(f"{ME}/saved-books", headers=headers).json() == []


def test_selecao_e_do_dono_do_token(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    """A seleção é por usuário: um professor não enxerga a do outro."""
    book = create_book(db_session)
    outro_professor = create_user(db_session)
    client.put(f"{ME}/saved-books/{book.id}", headers=auth_headers(outro_professor))

    assert client.get(f"{ME}/saved-books", headers=auth_headers(teacher_user)).json() == []


def test_salvar_ou_remover_obra_inexistente_responde_404(
    client: TestClient, teacher_user: User
) -> None:
    headers = auth_headers(teacher_user)
    assert client.put(f"{ME}/saved-books/999999", headers=headers).status_code == 404
    assert client.delete(f"{ME}/saved-books/999999", headers=headers).status_code == 404


BOOKS_PATH = "/api/v1/books"


def test_selecao_ordenada_da_mais_recente_para_antiga(
    client: TestClient, db_session: Session, teacher_user: User
) -> None:
    primeiro = create_book(db_session, title="Primeiro salvo")
    segundo = create_book(db_session, title="Segundo salvo")
    headers = auth_headers(teacher_user)
    client.put(f"{ME}/saved-books/{primeiro.id}", headers=headers)
    client.put(f"{ME}/saved-books/{segundo.id}", headers=headers)

    titles = [b["title"] for b in client.get(f"{ME}/saved-books", headers=headers).json()]
    assert titles == ["Segundo salvo", "Primeiro salvo"]
