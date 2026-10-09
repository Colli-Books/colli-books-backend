import logging

import pytest

from app.services.email import ConsoleEmailSender, EmailMessage, get_email_sender


def test_sem_provedor_o_email_vai_para_o_log(caplog: pytest.LogCaptureFixture) -> None:
    sender = get_email_sender()
    assert isinstance(sender, ConsoleEmailSender)

    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        sender.send(EmailMessage(to="p@escola.com", subject="Assunto", body="collibooks://x"))

    assert "p@escola.com" in caplog.text
    assert "collibooks://x" in caplog.text
