from typing import Any

from fastapi import status
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Formato de todas as respostas de erro (ver `app/errors.py`)."""

    code: str = Field(..., description="Código estável, usado pelo app.", examples=["FORBIDDEN"])
    message: str = Field(..., examples=["Acesso restrito a administradores."])
    details: Any = Field(None, description="Informação extra; em 422, a lista de campos inválidos.")


VALIDATION_RESPONSE: dict = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "`VALIDATION_ERROR`; campos inválidos em `details`.",
    }
}

RATE_LIMITED_RESPONSE: dict = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": ErrorResponse,
        "description": "`RATE_LIMITED`; aguardar o header `Retry-After` antes de tentar de novo.",
    }
}
