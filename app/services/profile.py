"""Perfil do usuário logado (US10–US12): dados, senha, interesses e Minha Seleção.

O usuário sempre vem do access token (o controller já o resolveu); nada aqui
recebe id de usuário de fora.
"""

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, ErrorCode
from app.models import Book, EducationLevel, Theme, User, saved_books
from app.security.passwords import hash_password, validate_password_strength, verify_password
from app.services.auth import revoke_all_sessions
from app.views.profile import ProfileUpdateRequest


def update_profile(db: Session, user: User, form: ProfileUpdateRequest) -> User:
    """US10: atualiza nome/escola. `model_fields_set` = o que veio no PATCH. Faz commit."""
    if "full_name" in form.model_fields_set:
        user.full_name = form.full_name
    if "school" in form.model_fields_set:
        user.school = form.school
    db.commit()
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Troca a senha exigindo a atual e encerrando as sessões abertas.

    Todos os refresh tokens são revogados: o app volta ao login na próxima
    renovação (o access token atual, curto, segue válido até expirar). Faz commit.
    """
    if not verify_password(current_password, user.password_hash):
        raise AppError(
            ErrorCode.CURRENT_PASSWORD_INVALID,
            "A senha atual está incorreta.",
            status.HTTP_400_BAD_REQUEST,
        )
    validate_password_strength(new_password)
    user.password_hash = hash_password(new_password)
    revoke_all_sessions(db, user.id)
    db.commit()


def update_interests(
    db: Session, user: User, theme_ids: list[int], education_level_ids: list[int]
) -> User:
    """US11: substitui os vínculos do professor. Ids desconhecidos → `422`. Faz commit."""
    user.themes = _existing_or_error(db, Theme, theme_ids, "theme_ids")
    user.education_levels = _existing_or_error(
        db, EducationLevel, education_level_ids, "education_level_ids"
    )
    db.commit()
    return user


def _existing_or_error(db: Session, model, ids: list[int], field: str):
    """Resolve ids de tema/escolaridade; os inexistentes voltam em `details`."""
    unique_ids = set(ids)
    if not unique_ids:
        return []
    found = list(db.scalars(select(model).where(model.id.in_(unique_ids))))
    missing = unique_ids - {row.id for row in found}
    if missing:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Há itens inexistentes na lista enviada.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=[{"loc": ["body", field], "msg": f"Ids inexistentes: {sorted(missing)}"}],
        )
    return found


def list_saved_books(db: Session, user: User) -> list[Book]:
    """US12: a Minha Seleção, da obra salva mais recente para a mais antiga."""
    stmt = (
        select(Book)
        .join(saved_books, saved_books.c.book_id == Book.id)
        .where(saved_books.c.user_id == user.id)
        .options(selectinload(Book.themes), selectinload(Book.education_level))
        .order_by(saved_books.c.created_at.desc(), saved_books.c.book_id.desc())
    )
    return list(db.scalars(stmt).unique())


def save_book(db: Session, user: User, book_id: int) -> None:
    """Salva a obra na seleção. Idempotente: salvar de novo não duplica. Faz commit."""
    _book_or_404(db, book_id)
    try:
        db.execute(saved_books.insert().values(user_id=user.id, book_id=book_id))
        db.commit()
    except IntegrityError:
        db.rollback()


def unsave_book(db: Session, user: User, book_id: int) -> None:
    """Remove a obra da seleção. Idempotente. `404` se a obra não existe. Faz commit."""
    _book_or_404(db, book_id)
    db.execute(
        delete(saved_books).where(
            saved_books.c.user_id == user.id,
            saved_books.c.book_id == book_id,
        )
    )
    db.commit()


def _book_or_404(db: Session, book_id: int) -> None:
    if db.get(Book, book_id) is None:
        raise AppError(ErrorCode.NOT_FOUND, "Obra não encontrada.", status.HTTP_404_NOT_FOUND)
