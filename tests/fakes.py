"""Implementações falsas usadas nos testes."""

from app.services.email import EmailMessage


class InMemoryEmailSender:
    """Guarda os e-mails em `outbox` em vez de enviá-los."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
