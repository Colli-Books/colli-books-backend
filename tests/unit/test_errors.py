"""Contrato de erros: todo erro sai como {code, message, details}."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.errors import AppError, ErrorCode, register_error_handlers
from app.rate_limit import rate_limit_exceeded_handler


class _Body(BaseModel):
    email: str


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    limiter = Limiter(key_func=get_remote_address, enabled=True)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/negocio")
    def negocio() -> None:
        raise AppError(
            ErrorCode.INVITE_EXPIRED, "O convite expirou.", 410, details={"can_resend": True}
        )

    @app.post("/validacao")
    def validacao(body: _Body) -> _Body:
        return body

    @app.get("/limitado")
    @limiter.limit("2/minute")
    def limitado(request: Request) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_erro_de_negocio_segue_o_contrato(client: TestClient) -> None:
    response = client.get("/negocio")

    assert response.status_code == 410
    assert response.json() == {
        "code": "INVITE_EXPIRED",
        "message": "O convite expirou.",
        "details": {"can_resend": True},
    }


def test_erro_de_validacao_segue_o_contrato(client: TestClient) -> None:
    response = client.post("/validacao", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"][0]["loc"] == ["body", "email"]


def test_rota_inexistente_segue_o_contrato(client: TestClient) -> None:
    response = client.get("/nao-existe")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_metodo_nao_permitido_segue_o_contrato(client: TestClient) -> None:
    response = client.delete("/negocio")

    assert response.status_code == 405
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"


def test_rate_limit_segue_o_contrato(client: TestClient) -> None:
    assert client.get("/limitado").status_code == 200
    assert client.get("/limitado").status_code == 200

    response = client.get("/limitado")

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
