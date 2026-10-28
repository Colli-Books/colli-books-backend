"""Obras: catálogo do professor (US07–US09) e gestão pela editora (US15–US17).

`is_saved` não é coluna: é o cruzamento de cada obra com a Minha Seleção do
usuário logado. As funções de leitura devolvem `(books, saved_ids)` para a
view marcar o flag sem consulta por obra (sem N+1).
"""

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, ErrorCode
from app.models import Book, EducationLevel, Theme, User, saved_books
from app.services.media import delete_cover, save_cover
from app.views.books import BookCreateForm, BookSort, BookUpdateForm

_LOAD_FULL = (
    selectinload(Book.themes),
    selectinload(Book.education_level),
)


def _search_predicate(term: str):
    """US07: trecho do título/autor, ignorando caixa e acentos.

    Usa `immutable_unaccent` — a mesma função dos índices trigram da migration
    0001, que assim podem atender a consulta.
    """
    pattern = f"%{_escape_like(term)}%"

    def unaccented(col):
        return func.immutable_unaccent(func.lower(col))

    return unaccented(Book.title).ilike(pattern) | unaccented(Book.author).ilike(pattern)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_books(
    db: Session,
    user: User,
    *,
    q: str | None,
    theme_id: int | None,
    education_level_id: int | None,
    sort: BookSort,
) -> tuple[list[Book], set[int]]:
    """Catálogo com busca e filtros (US07/US08). Lista integral — o app filtra
    localmente a partir do retorno."""
    stmt = select(Book).options(*_LOAD_FULL)

    if q and q.strip():
        stmt = stmt.where(_search_predicate(q.strip()))
    if theme_id is not None:
        stmt = stmt.where(Book.themes.any(Theme.id == theme_id))
    if education_level_id is not None:
        stmt = stmt.where(Book.education_level_id == education_level_id)

    books = list(db.scalars(stmt).unique())
    books = _sort_books(books, user, sort)
    return books, saved_book_ids(db, user.id, [b.id for b in books])


def _sort_books(books: list[Book], user: User, sort: BookSort) -> list[Book]:
    if sort == "title":
        return sorted(books, key=lambda b: b.title.lower())
    if sort == "year":
        return sorted(books, key=lambda b: (b.year or 0, b.title.lower()), reverse=True)

    theme_ids = {t.id for t in user.themes}
    level_ids = {lv.id for lv in user.education_levels}
    if not theme_ids and not level_ids:
        return sorted(books, key=lambda b: b.title.lower())

    def score(book: Book) -> int:
        points = 2 * len(theme_ids & {t.id for t in book.themes})
        if book.education_level_id in level_ids:
            points += 1
        return points

    return sorted(books, key=lambda b: (-score(b), b.title.lower()))


def get_book(db: Session, user: User, book_id: int) -> tuple[Book, bool]:
    """Detalhe da obra (US09), já com o flag `is_saved` do usuário."""
    book = db.scalar(select(Book).where(Book.id == book_id).options(*_LOAD_FULL))
    if book is None:
        raise AppError(ErrorCode.NOT_FOUND, "Obra não encontrada.", status.HTTP_404_NOT_FOUND)
    return book, book.id in saved_book_ids(db, user.id, [book.id])


def saved_book_ids(db: Session, user_id: int, book_ids: list[int]) -> set[int]:
    """Ids das obras salvas pelo usuário — uma única consulta por listagem."""
    if not book_ids:
        return set()
    rows = db.scalars(
        select(saved_books.c.book_id).where(
            saved_books.c.user_id == user_id,
            saved_books.c.book_id.in_(book_ids),
        )
    )
    return set(rows)


def create_book(db: Session, form: BookCreateForm) -> Book:
    """Cadastra a obra; a capa, se enviada, já foi validada. Faz commit."""
    level_id, themes = _resolve_refs(db, form.education_level_id, form.theme_ids)
    _check_isbn_free(db, form.isbn, exclude_id=None)

    book = Book(
        title=form.title,
        author=form.author,
        synopsis=form.synopsis,
        isbn=form.isbn,
        page_count=form.page_count,
        edition=form.edition,
        year=form.year,
        store_url=form.store_url,
        book_url=form.book_url,
        pedagogical_material_url=form.pedagogical_material_url,
        education_level_id=level_id,
        themes=themes,
    )

    cover_url = save_cover(form.cover) if form.cover else None
    try:
        book.cover_url = cover_url
        db.add(book)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if cover_url:
            delete_cover(cover_url)
        raise AppError(
            ErrorCode.ISBN_ALREADY_REGISTERED,
            "Já existe uma obra com este ISBN.",
            status.HTTP_409_CONFLICT,
        ) from exc
    except Exception:
        db.rollback()
        if cover_url:
            delete_cover(cover_url)
        raise
    db.refresh(book)
    return book


def update_book(db: Session, book_id: int, form: BookUpdateForm) -> Book:
    """PATCH parcial: `form.model_fields_set` diz o que o cliente enviou. Faz commit."""
    book = db.scalar(select(Book).where(Book.id == book_id).options(*_LOAD_FULL))
    if book is None:
        raise AppError(ErrorCode.NOT_FOUND, "Obra não encontrada.", status.HTTP_404_NOT_FOUND)

    sent = form.model_fields_set
    for field in (
        "title",
        "author",
        "synopsis",
        "isbn",
        "page_count",
        "edition",
        "year",
        "store_url",
        "book_url",
        "pedagogical_material_url",
    ):
        if field in sent:
            setattr(book, field, getattr(form, field))

    wants_level = "education_level_id" in sent
    wants_themes = "theme_ids" in sent
    if wants_level or wants_themes:
        level_id, themes = _resolve_refs(
            db,
            form.education_level_id if wants_level else None,
            form.theme_ids or [] if wants_themes else [],
            check_level=wants_level,
            check_themes=wants_themes,
        )
        if wants_level:
            book.education_level_id = level_id
        if wants_themes:
            book.themes = themes
    if "isbn" in sent:
        _check_isbn_free(db, book.isbn, exclude_id=book.id)

    old_cover = None
    if form.cover is not None:
        new_cover = save_cover(form.cover)
        old_cover, book.cover_url = book.cover_url, new_cover
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if old_cover is not None:
            delete_cover(book.cover_url)
        raise AppError(
            ErrorCode.ISBN_ALREADY_REGISTERED,
            "Já existe uma obra com este ISBN.",
            status.HTTP_409_CONFLICT,
        ) from exc
    except Exception:
        db.rollback()
        if old_cover is not None:
            delete_cover(book.cover_url)
        raise
    db.refresh(book)
    delete_cover(old_cover)
    return book


def _resolve_refs(
    db: Session,
    education_level_id: int | None,
    theme_ids: list[int],
    *,
    check_level: bool = True,
    check_themes: bool = True,
) -> tuple[int | None, list[Theme]]:
    """Resolve escolaridade e temas, reunindo todos os erros numa `422` só."""
    details: list[dict] = []
    themes: list[Theme] = []

    if check_level and education_level_id is not None:
        if db.get(EducationLevel, education_level_id) is None:
            details.append(
                {
                    "loc": ["body", "education_level_id"],
                    "msg": "Escolaridade inexistente.",
                }
            )
    if check_themes and theme_ids:
        unique_ids = set(theme_ids)
        themes = list(db.scalars(select(Theme).where(Theme.id.in_(unique_ids))))
        missing = unique_ids - {t.id for t in themes}
        if missing:
            details.append(
                {
                    "loc": ["body", "theme_ids"],
                    "msg": f"Ids inexistentes: {sorted(missing)}",
                }
            )
    if details:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Há itens inexistentes no cadastro.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )
    return education_level_id, themes


def _check_isbn_free(db: Session, isbn: str | None, exclude_id: int | None) -> None:
    """US15: o ISBN é único quando presente — dois livros não dividem o mesmo."""
    if isbn is None:
        return
    stmt = select(Book.id).where(Book.isbn == isbn)
    if exclude_id is not None:
        stmt = stmt.where(Book.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise AppError(
            ErrorCode.ISBN_ALREADY_REGISTERED,
            "Já existe uma obra com este ISBN.",
            status.HTTP_409_CONFLICT,
        )
