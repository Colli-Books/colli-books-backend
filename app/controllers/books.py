"""Obras: catálogo do professor (US07–US09) e gestão pela editora (US15–US17).

A leitura é aberta a qualquer usuário logado; cadastro e edição são só do admin
e usam `multipart/form-data` porque a capa vai junto do formulário (decisão de
contrato, seção 9 do "Contratos API.md").
"""

from typing import Annotated

from fastapi import APIRouter, Form, Query, status

from app.security.dependencies import AdminUser, CurrentUser, DbSession
from app.services import books as books_service
from app.views.books import BookCreateForm, BookDetail, BookSort, BookSummary, BookUpdateForm
from app.views.errors import ErrorResponse

router = APIRouter(prefix="/books", tags=["Obras"])

_AUTH = {status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}
_ADMIN_ERRORS = {
    **_AUTH,
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
}


@router.get(
    "",
    summary="Buscar obras",
    description=(
        "Catálogo completo com busca por título/autor (`q`, ignorando acentos e "
        "caixa — US07) e filtros por tema e escolaridade (US08). A lista volta "
        "integralmente — sem paginação — e cada item já traz `is_saved`, o flag "
        "da Minha Seleção do usuário logado. `sort` aceita `relevance` "
        "(padrão: obras dos temas/escolaridades do professor primeiro, US11), "
        "`title` e `year`."
    ),
    response_model=list[BookSummary],
    responses=_AUTH,
)
def list_books(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=255)] = None,
    theme_id: Annotated[int | None, Query(gt=0)] = None,
    education_level_id: Annotated[int | None, Query(gt=0)] = None,
    sort: BookSort = "relevance",
) -> list[BookSummary]:
    books, saved_ids = books_service.search_books(
        db, user, q=q, theme_id=theme_id, education_level_id=education_level_id, sort=sort
    )
    return [BookSummary.from_book(b, is_saved=b.id in saved_ids) for b in books]


@router.get(
    "/{book_id}",
    summary="Detalhe da obra",
    description=(
        "Todos os dados da tela de detalhe (US09), incluindo os links externos "
        "(`store_url`, `book_url`, `pedagogical_material_url`) e `is_saved`."
    ),
    response_model=BookDetail,
    responses={**_AUTH, status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_book(book_id: int, user: CurrentUser, db: DbSession) -> BookDetail:
    book, is_saved = books_service.get_book(db, user, book_id)
    return BookDetail.from_book(book, is_saved)


@router.post(
    "",
    summary="Cadastrar obra",
    description=(
        "Cria a obra (US15/US17). O corpo é `multipart/form-data`: campos de "
        "texto, `theme_ids` repetido (`theme_ids=6&theme_ids=8`) e a capa "
        "opcional no campo `cover` (PNG/JPEG, até 5 MB — `422 IMAGE_INVALID` "
        "ou `IMAGE_TOO_LARGE`). ISBN duplicado responde `409 "
        "ISBN_ALREADY_REGISTERED`; ids de tema/escolaridade inexistentes, "
        "`422` com o campo apontado em `details`."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=BookDetail,
    responses=_ADMIN_ERRORS,
)
def create_book(
    form: Annotated[BookCreateForm, Form()],
    _: AdminUser,
    db: DbSession,
) -> BookDetail:
    return BookDetail.from_book(books_service.create_book(db, form), is_saved=False)


@router.patch(
    "/{book_id}",
    summary="Editar obra",
    description=(
        "Edição parcial (US15/US17), também em `multipart/form-data`. Regras do "
        "PATCH multipart: campo **ausente** = não alterar; campo de texto ou "
        "numérico enviado **vazio** (`campo=`) = limpar; `theme_ids=` (vazio) "
        "remove todos os temas; `cover` ausente mantém a capa, arquivo novo a "
        "substitui. As alterações refletem imediatamente na busca."
    ),
    response_model=BookDetail,
    responses={**_ADMIN_ERRORS, status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def update_book(
    book_id: int,
    form: Annotated[BookUpdateForm, Form()],
    admin: AdminUser,
    db: DbSession,
) -> BookDetail:
    book = books_service.update_book(db, book_id, form)
    return BookDetail.from_book(
        book, is_saved=book.id in books_service.saved_book_ids(db, admin.id, [book.id])
    )
