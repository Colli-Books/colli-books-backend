"""Campos de conteúdo em books: ano, URL da obra e material pedagógico

Campos pedidos pelo detalhamento do app (Ano de lançamento, URL do livro e
URL de material pedagógico) e exigidos pelos endpoints da US09/US15.

Revision ID: 0002_books_content_fields
Revises: 0001_initial_schema
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_books_content_fields"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("books", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("book_url", sa.Text(), nullable=True))
    op.add_column("books", sa.Column("pedagogical_material_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "pedagogical_material_url")
    op.drop_column("books", "book_url")
    op.drop_column("books", "year")
