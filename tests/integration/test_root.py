"""Testes do endpoint raiz (GET /)."""

from fastapi.testclient import TestClient


def test_hello_world_retorna_200(client: TestClient) -> None:
    """GET / deve retornar HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_hello_world_retorna_mensagem(client: TestClient) -> None:
    """GET / deve retornar o JSON com a mensagem esperada."""
    response = client.get("/")
    data = response.json()
    assert data == {"message": "Hello World"}
