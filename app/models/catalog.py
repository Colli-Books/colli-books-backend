"""Acervo: obras, temas e escolaridades.

Cobre as US07–US09 (busca e detalhe) e US15–US17 (gestão pelo administrador).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Theme(TimestampMixin, Base):
    """Tema cadastrado pela editora (US16). Ex.: Bullying, Imaginação."""

    __tablename__ = "themes"
    __table_args__ = (Index("uq_themes_name_lower", text("lower(name)"), unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    books: Mapped[list[Book]] = relationship(secondary="book_themes", back_populates="themes")
    teachers: Mapped[list[User]] = relationship(secondary="teacher_themes", back_populates="themes")


class EducationLevel(TimestampMixin, Base):
    """Escolaridade cadastrada pela editora (US16).

    Ex.: Educação Infantil, Fundamental I, Fundamental II, Ensino Médio.
    """

    __tablename__ = "education_levels"
    __table_args__ = (Index("uq_education_levels_name_lower", text("lower(name)"), unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    books: Mapped[list[Book]] = relationship(back_populates="education_level")
    teachers: Mapped[list[User]] = relationship(
        secondary="teacher_education_levels", back_populates="education_levels"
    )


class Book(TimestampMixin, Base):
    """Obra do acervo (US15). Os campos espelham o detalhe exigido pela US09."""

    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "page_count IS NULL OR page_count > 0", name="ck_books_page_count_positive"
        ),
        Index("ix_books_education_level_id", "education_level_id"),
        Index(
            "ix_books_title_search",
            text("immutable_unaccent(lower(title))"),
            postgresql_using="gin",
            postgresql_ops={"immutable_unaccent(lower(title))": "gin_trgm_ops"},
        ),
        Index(
            "ix_books_author_search",
            text("immutable_unaccent(lower(author))"),
            postgresql_using="gin",
            postgresql_ops={"immutable_unaccent(lower(author))": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    store_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    book_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pedagogical_material_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_level_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("education_levels.id", ondelete="SET NULL"), nullable=True
    )

    education_level: Mapped[EducationLevel | None] = relationship(back_populates="books")
    themes: Mapped[list[Theme]] = relationship(secondary="book_themes", back_populates="books")
    saved_by: Mapped[list[User]] = relationship(
        secondary="saved_books", back_populates="saved_books"
    )


class InstitutionalPage(TimestampMixin, Base):
    """Seção institucional do menu lateral (US18).

    Uma seção ou tem conteúdo próprio (`body`), ou é um atalho para o site
    WordPress existente (`external_url`) — o protótipo usa as duas formas.
    """

    __tablename__ = "institutional_pages"
    __table_args__ = (
        CheckConstraint(
            "body IS NOT NULL OR external_url IS NOT NULL",
            name="ck_institutional_pages_has_content",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    is_published: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
