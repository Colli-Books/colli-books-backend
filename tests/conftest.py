"""Fixtures compartilhadas entre todos os testes."""

import os

import pytest
from fastapi.testclient import TestClient

# Configura um banco SQLite em memória antes de qualquer import da aplicação,
# para que os testes unitários não dependam de PostgreSQL ou psycopg.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """Retorna um TestClient do FastAPI configurado para os testes."""
    return TestClient(app)
