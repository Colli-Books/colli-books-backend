"""Links abertos pelo app mobile (convite e redefinição de senha)."""

from urllib.parse import urlencode

from app.config import get_settings


def build_app_link(path: str, token: str) -> str:
    """Monta `APP_LINK_BASE_URL` + `path?token=...`.

    Com o padrão `collibooks://`, gera `collibooks://convite?token=...`. Com um
    domínio (`https://colli.com.br`), gera `https://colli.com.br/convite?token=...`.
    """
    base = get_settings().app_link_base_url
    if not base.endswith("/"):
        base += "/"
    return f"{base}{path}?{urlencode({'token': token})}"
