"""Importa todos os models para que o `Base.metadata` fique completo.

O Alembic lê o metadata por este módulo; um model não importado aqui
simplesmente não existe para as migrations.
"""

from app.models.catalog import Book, EducationLevel, InstitutionalPage, Theme
from app.models.links import (
    book_themes,
    saved_books,
    teacher_education_levels,
    teacher_themes,
)
from app.models.user import (
    Invite,
    PasswordResetToken,
    RefreshToken,
    User,
    UserRole,
    UserStatus,
)

__all__ = [
    "Book",
    "EducationLevel",
    "InstitutionalPage",
    "Invite",
    "PasswordResetToken",
    "RefreshToken",
    "Theme",
    "User",
    "UserRole",
    "UserStatus",
    "book_themes",
    "saved_books",
    "teacher_education_levels",
    "teacher_themes",
]
