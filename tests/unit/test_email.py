import logging

import pytest

from app.config import get_settings
from app.services.email import ConsoleEmailSender, EmailMessage, get_email_sender


def test_sem_provedor_o_email_vai_para_o_log(caplog: pytest.LogCaptureFixture) -> None:
    sender = get_email_sender()
    assert isinstance(sender, ConsoleEmailSender)

    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        sender.send(EmailMessage(to="p@escola.com", subject="Assunto", body="collibooks://x"))

    assert "p@escola.com" in caplog.text
    assert "collibooks://x" in caplog.text


def test_em_producao_o_log_nao_expoe_o_corpo(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING, logger="app.services.email"):
            ConsoleEmailSender().send(
                EmailMessage(to="p@escola.com", subject="Assunto", body="collibooks://x?token=t")
            )
    finally:
        get_settings.cache_clear()

    assert "p@escola.com" in caplog.text
    assert "token=t" not in caplog.text
