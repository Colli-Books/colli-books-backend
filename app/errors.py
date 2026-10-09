"""Contrato de erros da API.

O cliente é um app mobile: ele precisa decidir *qual tela mostrar* a partir do
erro, sem interpretar texto. Por isso toda resposta de erro tem o formato

    {"code": "INVITE_EXPIRED", "message": "...", "details": null}

onde `code` é estável (o app pode depender dele) e `message` é só uma sugestão
de texto em português.
"""

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    # Genéricos
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

    # Autenticação e autorização
    UNAUTHENTICATED = "UNAUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    FORBIDDEN = "FORBIDDEN"

    # Contas e convites
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    INVITE_INVALID = "INVITE_INVALID"
    INVITE_EXPIRED = "INVITE_EXPIRED"
    INVITE_ALREADY_USED = "INVITE_ALREADY_USED"
    WEAK_PASSWORD = "WEAK_PASSWORD"
    RESET_TOKEN_INVALID = "RESET_TOKEN_INVALID"


class AppError(Exception):
    """Erro de negócio que vira uma resposta HTTP no formato do contrato."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.headers = headers


def error_body(code: ErrorCode, message: str, details: Any = None) -> dict[str, Any]:
    return {"code": code.value, "message": message, "details": details}


_HTTP_STATUS_CODES = {
    status.HTTP_404_NOT_FOUND: (ErrorCode.NOT_FOUND, "Recurso não encontrado."),
    status.HTTP_405_METHOD_NOT_ALLOWED: (ErrorCode.METHOD_NOT_ALLOWED, "Método não permitido."),
}


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_body(exc.code, exc.message, exc.details)),
        headers=exc.headers,
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            ErrorCode.VALIDATION_ERROR,
            "Dados inválidos.",
            jsonable_encoder(exc.errors()),
        ),
    )


async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_STATUS_CODES.get(exc.status_code, (ErrorCode.HTTP_ERROR, str(exc.detail)))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message),
        headers=getattr(exc, "headers", None),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
