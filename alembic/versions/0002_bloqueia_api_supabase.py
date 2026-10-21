"""Bloqueia o acesso às tabelas pela API pública do Supabase

No Supabase, o schema `public` é exposto pela Data API (PostgREST) aos papéis
`anon` e `authenticated`, que recebem todos os privilégios em tabelas novas.
Como o app fala só com o backend (FastAPI), esses papéis não devem ler nem
gravar nada; sem este bloqueio, a chave pública do projeto bastaria para ler
`users.password_hash`.

* RLS ligado em todas as tabelas, sem nenhuma policy (nega tudo por padrão).
  O backend conecta como dono das tabelas, que ignora o RLS.
* Privilégios de `anon` e `authenticated` revogados, inclusive para tabelas
  e sequências criadas depois (default privileges).

Fora do Supabase (Docker local, CI) esses papéis não existem e só o RLS é
ligado, o que não muda nada para o dono das tabelas.

Revision ID: 0002_bloqueia_api_supabase
Revises: 0001_initial_schema
Create Date: 2026-10-21

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_bloqueia_api_supabase"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "alembic_version",
    "users",
    "invites",
    "password_reset_tokens",
    "refresh_tokens",
    "themes",
    "education_levels",
    "books",
    "institutional_pages",
    "book_themes",
    "teacher_themes",
    "teacher_education_levels",
    "saved_books",
)

REVOKE_SUPABASE_ROLES = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
       AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
        REVOKE ALL ON FUNCTION public.immutable_unaccent(text) FROM anon, authenticated;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE ALL ON TABLES FROM anon, authenticated;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE ALL ON SEQUENCES FROM anon, authenticated;
    END IF;
END
$$;
"""


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(REVOKE_SUPABASE_ROLES)
    # O corpo já usa nomes qualificados; fixar o search_path impede que outro
    # papel troque `unaccent` por uma função sua (aviso do linter do Supabase).
    op.execute("ALTER FUNCTION immutable_unaccent(text) SET search_path = ''")


def downgrade() -> None:
    op.execute("ALTER FUNCTION immutable_unaccent(text) RESET search_path")
    # Os privilégios revogados não voltam: devolvê-los reabriria as tabelas
    # para a chave pública do Supabase.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
