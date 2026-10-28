"""Configuração da aplicação, lida de variáveis de ambiente (ou do `.env`).

Todo valor ajustável por ambiente mora aqui, para que o restante do código não
leia `os.environ` diretamente.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-change-me-dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/colli_books"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    invite_ttl_hours: int = 72
    password_reset_ttl_minutes: int = 30

    app_link_base_url: str = "collibooks://"

    password_min_length: int = 8
    password_max_length: int = 128

    media_dir: str = "media"
    cover_max_bytes: int = 5 * 1024 * 1024

    brevo_api_key: str = ""
    brevo_template_invite: int = 0
    brevo_template_invite_renewal: int = 0
    brevo_template_password_reset: int = 0

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
