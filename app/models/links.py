"""Tabelas de associação do domínio.

São tabelas puras de ligação (sem entidade própria), declaradas como `Table`
para que o SQLAlchemy as use diretamente no `secondary=` das relationships.
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Table, func

from app.database import Base

# US17: uma obra pertence a um ou mais temas e aparece na busca de todos eles.
book_themes = Table(
    "book_themes",
    Base.metadata,
    Column(
        "book_id",
        BigInteger,
        ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "theme_id",
        BigInteger,
        ForeignKey("themes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # A PK já cobre buscas por obra; o filtro da US08 parte do tema.
    Index("ix_book_themes_theme_id", "theme_id"),
)

# US11: o professor se vincula aos temas que leciona para que o sistema
# priorize as obras da área dele.
teacher_themes = Table(
    "teacher_themes",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "theme_id",
        BigInteger,
        ForeignKey("themes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_teacher_themes_theme_id", "theme_id"),
)

# US11: mesma ideia, para as escolaridades que o professor atende.
teacher_education_levels = Table(
    "teacher_education_levels",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "education_level_id",
        BigInteger,
        ForeignKey("education_levels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_teacher_education_levels_education_level_id", "education_level_id"),
)

# US12: "Minha Seleção" — as obras que o professor guardou entre sessões.
saved_books = Table(
    "saved_books",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "book_id",
        BigInteger,
        ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Index("ix_saved_books_book_id", "book_id"),
)
