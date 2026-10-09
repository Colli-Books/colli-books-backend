"""Modelo físico inicial do Colli Books

Cria o esquema que atende aos épicos 1 a 4 do backlog: contas e tokens de
acesso, acervo (obras, temas, escolaridades), vínculos do professor, seleção
pessoal e seções institucionais.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_role = sa.Enum("admin", "teacher", name="user_role")
user_status = sa.Enum("invite_pending", "active", "inactive", name="user_status")


def upgrade() -> None:
    # --- Extensões usadas pela busca da US07 -------------------------------
    # A busca por nome ignora acentuação e caixa. `unaccent` não é IMMUTABLE
    # (depende do dicionário carregado) e por isso não pode ser indexada
    # diretamente; o wrapper abaixo é o contorno documentado pelo PostgreSQL.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION immutable_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE STRICT PARALLEL SAFE
        AS $$ SELECT public.unaccent('public.unaccent', $1) $$
        """
    )

    # --- Épico 1 — Acesso e Contas ----------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", user_role, server_default="teacher", nullable=False),
        sa.Column("status", user_status, server_default="invite_pending", nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("school", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint(
            "status <> 'active' OR password_hash IS NOT NULL",
            name="ck_users_active_requires_password",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index("ix_users_role_status", "users", ["role", "status"])

    op.create_table(
        "invites",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_invites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
    )
    op.create_index("ix_invites_user_id", "invites", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # --- Épico 3 — Acervo --------------------------------------------------
    op.create_table(
        "themes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_themes")),
    )
    # US16: nomes duplicados são proibidos, ignorando maiúsculas/minúsculas.
    op.execute("CREATE UNIQUE INDEX uq_themes_name_lower ON themes (lower(name))")

    op.create_table(
        "education_levels",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_education_levels")),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_education_levels_name_lower ON education_levels (lower(name))"
    )

    op.create_table(
        "books",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("isbn", sa.String(length=20), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("edition", sa.String(length=50), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("store_url", sa.Text(), nullable=True),
        sa.Column("education_level_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0", name="ck_books_page_count_positive"
        ),
        sa.ForeignKeyConstraint(
            ["education_level_id"],
            ["education_levels.id"],
            name=op.f("fk_books_education_level_id_education_levels"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_books")),
        sa.UniqueConstraint("isbn", name=op.f("uq_books_isbn")),
    )
    op.create_index("ix_books_education_level_id", "books", ["education_level_id"])
    # US07: busca por trecho do título/autor, sem acento e sem distinguir caixa.
    op.execute(
        "CREATE INDEX ix_books_title_search ON books "
        "USING gin (immutable_unaccent(lower(title)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_books_author_search ON books "
        "USING gin (immutable_unaccent(lower(author)) gin_trgm_ops)"
    )

    # --- Épico 4 — Conteúdo institucional ---------------------------------
    op.create_table(
        "institutional_pages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "body IS NOT NULL OR external_url IS NOT NULL",
            name="ck_institutional_pages_has_content",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutional_pages")),
        sa.UniqueConstraint("slug", name=op.f("uq_institutional_pages_slug")),
    )

    # --- Vínculos ----------------------------------------------------------
    op.create_table(
        "book_themes",
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("theme_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_book_themes_book_id_books"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            name=op.f("fk_book_themes_theme_id_themes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("book_id", "theme_id", name=op.f("pk_book_themes")),
    )
    op.create_index("ix_book_themes_theme_id", "book_themes", ["theme_id"])

    op.create_table(
        "teacher_themes",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("theme_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_teacher_themes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            name=op.f("fk_teacher_themes_theme_id_themes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "theme_id", name=op.f("pk_teacher_themes")),
    )
    op.create_index("ix_teacher_themes_theme_id", "teacher_themes", ["theme_id"])

    op.create_table(
        "teacher_education_levels",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("education_level_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_teacher_education_levels_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["education_level_id"],
            ["education_levels.id"],
            name=op.f("fk_teacher_education_levels_education_level_id_education_levels"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "education_level_id", name=op.f("pk_teacher_education_levels")
        ),
    )
    op.create_index(
        "ix_teacher_education_levels_education_level_id",
        "teacher_education_levels",
        ["education_level_id"],
    )

    op.create_table(
        "saved_books",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_saved_books_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_saved_books_book_id_books"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "book_id", name=op.f("pk_saved_books")),
    )
    op.create_index("ix_saved_books_book_id", "saved_books", ["book_id"])


def downgrade() -> None:
    op.drop_table("saved_books")
    op.drop_table("teacher_education_levels")
    op.drop_table("teacher_themes")
    op.drop_table("book_themes")
    op.drop_table("institutional_pages")
    op.drop_table("books")
    op.drop_table("education_levels")
    op.drop_table("themes")
    op.drop_table("refresh_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("invites")
    op.drop_table("users")

    user_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)

    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text)")
