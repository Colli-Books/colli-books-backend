"""Rate limit dos endpoints sensíveis (login, convites, redefinição de senha).

Uso numa rota (o parâmetro `request: Request` é obrigatório para o slowapi):

    @router.post("/auth/login")
    @limiter.limit("5/minute")
    def login(request: Request, ...): ...

Limitações conhecidas: o contador fica em memória, por processo. Atrás de um
proxy reverso, o IP visto é o do proxy; nesse caso é preciso configurar o
uvicorn com `--proxy-headers`.
"""

import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.errors import ErrorCode, error_body

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)


def _retry_after_seconds(request: Request) -> int | None:
    """Tempo até a janela do rate limit reiniciar, em segundos.

    O slowapi guarda em `request.state.view_rate_limit` o limite que falhou
    (RateLimitItem + chaves); `get_window_stats` devolve o instante do reset.
    """
    current_limit = getattr(request.state, "view_rate_limit", None)
    if current_limit is None:
        return None
    try:
        window_stats = limiter.limiter.get_window_stats(current_limit[0], *current_limit[1])
        return max(int(1 + window_stats[0] - time.time()), 1)
    except Exception:
        return None


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_body(
            ErrorCode.RATE_LIMITED,
            "Muitas tentativas. Aguarde um pouco e tente de novo.",
            {"limit": str(exc.detail)},
        ),
    )
    retry_after = _retry_after_seconds(request)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
