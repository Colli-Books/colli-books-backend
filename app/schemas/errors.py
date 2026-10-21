from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Formato de todas as respostas de erro (ver `app/errors.py`)."""

    code: str = Field(..., description="Código estável, usado pelo app.", examples=["FORBIDDEN"])
    message: str = Field(..., examples=["Acesso restrito a administradores."])
    details: Any = Field(None, description="Informação extra; em 422, a lista de campos inválidos.")
