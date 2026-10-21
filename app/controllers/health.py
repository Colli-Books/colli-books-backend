"""Raiz e health check. Ficam fora de `/api/v1`: não fazem parte do contrato do app."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.database import engine
from app.views.health import HealthResponse, HelloResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    tags=["Root"],
    summary="Hello World",
    description="Retorna uma mensagem estática para confirmar que a API está no ar.",
    response_model=HelloResponse,
)
def hello_world() -> HelloResponse:
    return HelloResponse(message="Hello World")


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Executa um `SELECT 1` no PostgreSQL. "
        "Responde **200** quando o banco está acessível e **503** quando não está."
    ),
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "O banco de dados não está acessível.",
        }
    },
)
def health(response: Response) -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        # O detalhe vai só para o log: a mensagem do driver pode expor host e usuário.
        logger.exception("Health check: banco inacessível")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database="unavailable")
    return HealthResponse(status="ok", database="connected")
