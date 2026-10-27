import logging

import pytest
from fastapi import BackgroundTasks

from app.config import get_settings
from app.services import email as email_service
from app.services.email import (
    BackgroundEmailSender,
    BrevoEmailSender,
    ConsoleEmailSender,
    EmailKind,
    EmailMessage,
    _safe_send,
    get_email_sender,
)

_MESSAGE = EmailMessage(
    to="p@escola.com",
    kind=EmailKind.INVITE,
    params={"link": "collibooks://x?token=t", "code": "t", "expires_at": "25/10/2026 14:00 (UTC)"},
)


class _FakeBrevoClient:
    """Finge o cliente do SDK: registra as chamadas de envio."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def transactional_emails(self) -> "_FakeBrevoClient":
        return self

    def send_transac_email(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _RaisingSender:
    def send(self, message: EmailMessage) -> None:
        raise RuntimeError("provedor fora do ar")


def test_sem_provedor_o_email_vai_para_o_log(caplog: pytest.LogCaptureFixture) -> None:
    sender = ConsoleEmailSender()

    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        sender.send(_MESSAGE)

    assert "p@escola.com" in caplog.text
    assert "invite" in caplog.text
    assert "collibooks://x?token=t" in caplog.text


def test_em_producao_o_log_nao_expoe_os_params(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING, logger="app.services.email"):
            ConsoleEmailSender().send(_MESSAGE)
    finally:
        get_settings.cache_clear()

    assert "p@escola.com" in caplog.text
    assert "token=t" not in caplog.text


def test_brevo_usa_o_template_do_kind_e_passa_os_params() -> None:
    client = _FakeBrevoClient()
    sender = BrevoEmailSender(client, {EmailKind.INVITE: 7})

    sender.send(_MESSAGE)

    [call] = client.calls
    assert call["template_id"] == 7
    assert [to.email for to in call["to"]] == ["p@escola.com"]
    assert call["params"] == _MESSAGE.params


def test_brevo_sem_template_configurado_falha() -> None:
    sender = BrevoEmailSender(_FakeBrevoClient(), {EmailKind.INVITE: 0})

    with pytest.raises(RuntimeError, match="invite"):
        sender.send(_MESSAGE)


def test_background_enfileira_o_envio() -> None:
    tasks = BackgroundTasks()
    client = _FakeBrevoClient()
    sender = BackgroundEmailSender(tasks, BrevoEmailSender(client, {EmailKind.INVITE: 7}))

    sender.send(_MESSAGE)

    [task] = tasks.tasks
    assert task.func is _safe_send
    assert client.calls == []  # nada saiu ainda: o envio roda depois da resposta
    task.func(*task.args, **task.kwargs)
    [call] = client.calls
    assert call["params"] == _MESSAGE.params


def test_safe_send_loga_a_falha_e_nao_propaga(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="app.services.email"):
        _safe_send(_RaisingSender(), _MESSAGE)  # não levanta

    assert "Falha ao enviar e-mail para p@escola.com (tipo=invite)" in caplog.text
    assert "provedor fora do ar" in caplog.text
    assert "token=t" not in caplog.text


def test_get_email_sender_envolve_o_default_em_background(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tasks = BackgroundTasks()
    sender = get_email_sender(tasks)

    assert isinstance(sender, BackgroundEmailSender)
    sender.send(_MESSAGE)

    [task] = tasks.tasks
    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        task.func(*task.args, **task.kwargs)
    assert "p@escola.com" in caplog.text


def test_default_usa_brevo_quando_ha_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BREVO_API_KEY", "xkeys")
    monkeypatch.setattr(email_service, "Brevo", lambda api_key: _FakeBrevoClient())
    get_settings.cache_clear()
    email_service._default_sender.cache_clear()
    try:
        assert isinstance(email_service._default_sender(), BrevoEmailSender)
    finally:
        get_settings.cache_clear()
        email_service._default_sender.cache_clear()
