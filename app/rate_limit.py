"""Rate limit dos endpoints sensíveis (login, convites, redefinição de senha).

Uso numa rota (o parâmetro `request: Request` é obrigatório para o slowapi):

    @router.post("/auth/login")
    @limiter.limit("5/minute")
    def login(request: Request, ...): ...

Limitações conhecidas: o contador fica em memória, por processo. Atrás de um
proxy reverso, o IP visto é o do proxy; nesse caso, `CLIENT_IP_HEADER` indica
o header com o IP real do cliente.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.errors import ErrorCode, error_body


def client_ip(request: Request) -> str:
    """IP usado como chave do rate limit."""
    header = get_settings().client_ip_header
    if header:
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip, enabled=get_settings().rate_limit_enabled)


async def rate_limit_exceeded_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_body(
            ErrorCode.RATE_LIMITED,
            "Muitas tentativas. Aguarde um pouco e tente de novo.",
            {"limit": str(exc.detail)},
        ),
    )


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
