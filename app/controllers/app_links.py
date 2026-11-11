"""Página `/abrir/...`: destino https dos links de convite e de redefinição de senha.

Fica fora de `/api/v1`: é uma página para pessoas, não parte do contrato do app.
Com `APP_LINK_BASE_URL=https://<api>/abrir`, o e-mail leva
`https://<api>/abrir/convite?token=...` (clicável em qualquer cliente) e esta
página oferece o botão que abre `collibooks://convite?token=...`.

Só monta HTML: não consulta nem consome o token, então um antivírus de e-mail que
"visita" o link antes da pessoa não invalida o convite.
"""

import re
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Query, status
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.views.app_links import PAGE_COPY, render_invalid_link_page, render_open_page

router = APIRouter()

# Tokens vêm de `secrets.token_urlsafe`; qualquer outra coisa é link adulterado.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _html(content: str, nonce: str, status_code: int = status.HTTP_200_OK) -> HTMLResponse:
    return HTMLResponse(
        content,
        status_code=status_code,
        headers={
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; frame-ancestors 'none'; base-uri 'none'"
            ),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/abrir/{destino}", include_in_schema=False)
def open_in_app(destino: str, token: str = Query(default="")) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    copy = PAGE_COPY.get(destino)
    if copy is None or not _TOKEN_RE.fullmatch(token):
        return _html(render_invalid_link_page(nonce), nonce, status.HTTP_404_NOT_FOUND)

    app_link = f"{get_settings().app_scheme}://{destino}?{urlencode({'token': token})}"
    return _html(render_open_page(copy, app_link, token, nonce), nonce)
