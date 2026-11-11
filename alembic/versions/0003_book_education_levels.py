"""Obra com várias escolaridades: books.education_level_id vira book_education_levels

Antes a obra tinha no máximo uma escolaridade (FK em books). A editora precisa
marcar várias (ex.: Fundamental I e II), como já acontece com os temas.

A escolaridade atual de cada obra é copiada para a tabela nova antes de a
coluna sair. O downgrade volta a coluna com a escolaridade de menor
`sort_order` de cada obra (as demais se perdem).

Revision ID: 0003_book_education_levels
Revises: 0002_books_content_fields
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_book_education_levels"
down_revision: str | None = "0002_books_content_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "book_education_levels",
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("education_level_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name=op.f("fk_book_education_levels_book_id_books"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["education_level_id"],
            ["education_levels.id"],
            name=op.f("fk_book_education_levels_education_level_id_education_levels"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "book_id", "education_level_id", name=op.f("pk_book_education_levels")
        ),
    )
    op.create_index(
        "ix_book_education_levels_education_level_id",
        "book_education_levels",
        ["education_level_id"],
    )
    op.execute(
        "INSERT INTO book_education_levels (book_id, education_level_id) "
        "SELECT id, education_level_id FROM books WHERE education_level_id IS NOT NULL"
    )
    op.drop_index("ix_books_education_level_id", table_name="books")
    op.drop_column("books", "education_level_id")


def downgrade() -> None:
    op.add_column("books", sa.Column("education_level_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_books_education_level_id_education_levels"),
        "books",
        "education_levels",
        ["education_level_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_books_education_level_id", "books", ["education_level_id"])
    op.execute(
        "UPDATE books SET education_level_id = ("
        "  SELECT bel.education_level_id FROM book_education_levels bel"
        "  JOIN education_levels el ON el.id = bel.education_level_id"
        "  WHERE bel.book_id = books.id ORDER BY el.sort_order, el.id LIMIT 1"
        ")"
    )
    op.drop_index("ix_book_education_levels_education_level_id", table_name="book_education_levels")
    op.drop_table("book_education_levels")
