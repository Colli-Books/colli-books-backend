"""Configuração da aplicação, lida de variáveis de ambiente (ou do `.env`).

Todo valor ajustável por ambiente mora aqui, para que o restante do código não
leia `os.environ` diretamente.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Segredo usado só em desenvolvimento. Em produção a aplicação se recusa a subir
# com ele (ver `_reject_insecure_secret_in_production`).
DEV_JWT_SECRET = "dev-secret-change-me-dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/colli_books"

    # --- Tokens de sessão (US03) ------------------------------------------
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # Access token curto: o app mobile renova com o refresh token.
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # --- Tokens de uso único (US01, US02, US04) ---------------------------
    invite_ttl_hours: int = 72
    password_reset_ttl_minutes: int = 30

    # Base dos links abertos pelo app. Sem domínio, usamos esquema customizado;
    # quando houver domínio, basta trocar para `https://...` (App/Universal Links).
    app_link_base_url: str = "collibooks://"

    # --- Senhas (US02) ----------------------------------------------------
    password_min_length: int = 8
    # Teto para evitar que uma senha gigante vire custo de CPU no hash.
    password_max_length: int = 128

    # --- Proteção contra força bruta --------------------------------------
    rate_limit_enabled: bool = True

    @model_validator(mode="after")
    def _reject_insecure_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET precisa ser definido (mín. 32 caracteres) em produção.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
