"""Resposta 429 no formato do contrato + header Retry-After (seção 4.4)."""

import asyncio
from unittest.mock import Mock

from fastapi import Request
from limits import RateLimitItemPerMinute

from app.rate_limit import limiter, rate_limit_exceeded_handler


def _request_with_limit(item, keys: list[str]) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "state": {}}
    request = Request(scope)
    request.state.view_rate_limit = (item, keys)
    return request


def test_429_tem_envelope_do_contrato_e_retry_after() -> None:
    item = RateLimitItemPerMinute(5)
    limiter.limiter.hit(item, "teste-retry-after")

    response = asyncio.run(
        rate_limit_exceeded_handler(
            _request_with_limit(item, ["teste-retry-after"]),
            Mock(detail="5 per 1 minute"),
        )
    )

    assert response.status_code == 429
    body = response.body.decode()
    assert '"code":"RATE_LIMITED"' in body
    # A janela de 1 minuto está aberta: faltam entre 1 e 60 segundos para o reset.
    assert 1 <= int(response.headers["Retry-After"]) <= 61


def test_429_sem_limite_identificado_nao_envia_retry_after() -> None:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "state": {}}
    request = Request(scope)

    response = asyncio.run(rate_limit_exceeded_handler(request, Mock(detail="5 per 1 minute")))

    assert response.status_code == 429
    assert "Retry-After" not in response.headers
