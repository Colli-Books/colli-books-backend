"""As migrations precisam produzir exatamente o schema descrito pelos models."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra todos os models no metadata)
from app.database import Base


def test_models_e_migrations_estao_sincronizados(db_session: Session) -> None:
    """Falha se um model mudou sem a migration correspondente.

    Para corrigir: `alembic revision --autogenerate -m "..."` e revisar o arquivo.
    """
    context = MigrationContext.configure(db_session.connection(), opts={"compare_type": True})

    diff = compare_metadata(context, Base.metadata)

    assert diff == [], f"Models e migrations divergem: {diff}"
