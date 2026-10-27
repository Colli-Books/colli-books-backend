"""US16: cadastro e renomeação de temas e escolaridades pela editora.

A unicidade ignorando caixa (ex.: "empatia" e "Empatia") é garantida pelo
índice funcional `lower(name)` no banco; aqui ela é conferida antes, para dar
uma mensagem amigável, e a `IntegrityError` restante cobre a corrida.
"""

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models import EducationLevel, Theme


def list_themes(db: Session) -> list[Theme]:
    return list(db.scalars(select(Theme).order_by(func.lower(Theme.name))))


def create_theme(db: Session, name: str, description: str | None) -> Theme:
    if _theme_by_name(db, name) is not None:
        raise _theme_exists()
    theme = Theme(name=name, description=description)
    db.add(theme)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _theme_exists() from exc
    return theme


def update_theme(db: Session, theme_id: int, *, name: str | None, description: str | None) -> Theme:
    theme = db.get(Theme, theme_id)
    if theme is None:
        raise AppError(ErrorCode.NOT_FOUND, "Tema não encontrado.", status.HTTP_404_NOT_FOUND)
    if name is not None:
        existing = _theme_by_name(db, name)
        if existing is not None and existing.id != theme.id:
            raise _theme_exists()
        theme.name = name
    if description is not None:
        theme.description = description
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _theme_exists() from exc
    return theme


def _theme_by_name(db: Session, name: str) -> Theme | None:
    return db.scalar(select(Theme).where(func.lower(Theme.name) == name.strip().lower()))


def _theme_exists() -> AppError:
    return AppError(
        ErrorCode.THEME_ALREADY_EXISTS,
        "Já existe um tema com este nome.",
        status.HTTP_409_CONFLICT,
    )


def list_education_levels(db: Session) -> list[EducationLevel]:
    return list(
        db.scalars(
            select(EducationLevel).order_by(
                EducationLevel.sort_order, func.lower(EducationLevel.name)
            )
        )
    )


def create_education_level(db: Session, name: str, sort_order: int) -> EducationLevel:
    if _level_by_name(db, name) is not None:
        raise _level_exists()
    level = EducationLevel(name=name, sort_order=sort_order)
    db.add(level)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _level_exists() from exc
    return level


def update_education_level(
    db: Session, level_id: int, *, name: str | None, sort_order: int | None
) -> EducationLevel:
    level = db.get(EducationLevel, level_id)
    if level is None:
        raise AppError(
            ErrorCode.NOT_FOUND, "Escolaridade não encontrada.", status.HTTP_404_NOT_FOUND
        )
    if name is not None:
        existing = _level_by_name(db, name)
        if existing is not None and existing.id != level.id:
            raise _level_exists()
        level.name = name
    if sort_order is not None:
        level.sort_order = sort_order
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _level_exists() from exc
    return level


def _level_by_name(db: Session, name: str) -> EducationLevel | None:
    return db.scalar(
        select(EducationLevel).where(func.lower(EducationLevel.name) == name.strip().lower())
    )


def _level_exists() -> AppError:
    return AppError(
        ErrorCode.EDUCATION_LEVEL_ALREADY_EXISTS,
        "Já existe uma escolaridade com este nome.",
        status.HTTP_409_CONFLICT,
    )
