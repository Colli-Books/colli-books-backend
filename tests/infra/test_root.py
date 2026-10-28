"""Endpoint raiz (GET /)."""

from fastapi.testclient import TestClient


def test_raiz_responde_hello_world(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
