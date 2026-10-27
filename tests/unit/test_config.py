import pytest
from pydantic import ValidationError

from app.config import DEV_JWT_SECRET, Settings


def test_desenvolvimento_aceita_segredo_padrao() -> None:
    assert Settings(app_env="development").jwt_secret == DEV_JWT_SECRET


@pytest.mark.parametrize("secret", [DEV_JWT_SECRET, "curto-demais"])
def test_producao_recusa_segredo_inseguro(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret=secret)


def test_producao_aceita_segredo_forte() -> None:
    settings = Settings(app_env="production", jwt_secret="x" * 48)
    assert settings.app_env == "production"


def test_configuracoes_do_brevo_tem_defaults_neutros() -> None:
    """Sem chave, o e-mail cai no log; sem template, o envio com Brevo falha no log."""
    defaults = Settings.model_fields
    assert defaults["brevo_api_key"].default == ""
    assert defaults["brevo_template_invite"].default == 0
    assert defaults["brevo_template_invite_renewal"].default == 0
    assert defaults["brevo_template_password_reset"].default == 0
