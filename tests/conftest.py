"""Fixtures compartilhadas entre todos os testes.

Os testes de integração rodam contra um **PostgreSQL real**: o schema usa
recursos exclusivos dele (`unaccent`, `pg_trgm`, índices GIN e funcionais), que
não existem no SQLite.

* Na primeira vez que um teste pede o banco, o banco de teste é recriado do
  zero e as migrations do Alembic são aplicadas (`alembic upgrade head`).
* Cada teste roda dentro de uma transação que é desfeita no final, então um
  teste nunca enxerga dados de outro.

Para rodar localmente: `docker compose up -d db` e depois `pytest`.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/colli_books_test",
)

# Precisa acontecer antes de importar `app`: o engine é criado no import.
# Sobrescreve (não usa setdefault) para nunca rodar os testes no banco de dev.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.services.email import get_email_sender  # noqa: E402
from tests.factories import create_user  # noqa: E402
from tests.fakes import InMemoryEmailSender  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _recreate_database(url: str) -> None:
    parsed = make_url(url)
    if not (parsed.database or "").endswith("_test"):
        raise RuntimeError(
            f"Recusando recriar o banco '{parsed.database}': o nome precisa terminar em '_test'."
        )
    admin_engine = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{parsed.database}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    finally:
        admin_engine.dispose()


def _run_migrations() -> None:
    # Config sem arquivo .ini: assim o env.py não chama `fileConfig`, que
    # desligaria os loggers da aplicação (e quebraria testes que usam caplog).
    config = Config()
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def _database() -> Iterator[None]:
    _recreate_database(TEST_DATABASE_URL)
    _run_migrations()
    yield
    engine.dispose()


@pytest.fixture()
def db_session(_database: None) -> Iterator[Session]:
    """Sessão ligada a uma transação desfeita ao fim do teste.

    `create_savepoint` faz os `commit()` do código testado virarem savepoints,
    então o rollback final apaga tudo, inclusive o que foi "commitado".
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def email_outbox() -> InMemoryEmailSender:
    return InMemoryEmailSender()


@pytest.fixture()
def client(db_session: Session, email_outbox: InMemoryEmailSender) -> Iterator[TestClient]:
    """TestClient da aplicação, usando a sessão transacional e o e-mail em memória."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: email_outbox
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    return create_user(db_session, email="admin@colli.com", role=UserRole.ADMIN)


@pytest.fixture()
def teacher_user(db_session: Session) -> User:
    return create_user(db_session, email="professor@escola.com", role=UserRole.TEACHER)
