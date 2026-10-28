"""Health check (GET /health), com a conexão do banco simulada."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _banco_ok() -> dict:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return {"return_value": ctx}


def _banco_fora() -> dict:
    return {"side_effect": Exception("connection refused")}


@pytest.mark.parametrize(
    ("mock_kwargs", "status_code", "status", "database"),
    [
        pytest.param(_banco_ok, 200, "ok", "connected", id="banco-ok"),
        pytest.param(_banco_fora, 503, "error", "connection refused", id="banco-indisponivel"),
    ],
)
def test_health_reflete_o_estado_do_banco(
    client: TestClient, mock_kwargs, status_code: int, status: str, database: str
) -> None:
    with patch("app.controllers.health.engine.connect", **mock_kwargs()):
        response = client.get("/health")

    assert response.status_code == status_code
    data = response.json()
    assert data["status"] == status
    assert database in data["database"]
