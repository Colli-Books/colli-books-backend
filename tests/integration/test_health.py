"""Testes do endpoint de health check (GET /health).

O banco de dados não está disponível durante os testes unitários, portanto
mockamos a conexão para cobrir os dois cenários: banco acessível e banco
inacessível.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_health_banco_ok(client: TestClient) -> None:
    """GET /health deve retornar 200 quando o banco responde."""
    mock_conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("app.main.engine.connect", return_value=mock_ctx):
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_banco_indisponivel(client: TestClient) -> None:
    """GET /health deve retornar 503 quando o banco não está acessível."""
    with patch("app.main.engine.connect", side_effect=Exception("connection refused")):
        response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "connection refused" in data["database"]
