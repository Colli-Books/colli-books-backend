"""Envio de e-mails (reenvio de convite na US02, redefinição de senha na US04/US06).

Ainda não há provedor de e-mail definido. Por enquanto a única implementação é
`ConsoleEmailSender`, que escreve a mensagem no log do servidor. Quando houver
provedor, basta criar outra classe com o mesmo método `send` e devolvê-la em
`get_email_sender`.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Escreve o e-mail no log. Só para desenvolvimento: o log expõe os links."""

    def send(self, message: EmailMessage) -> None:
        logger.warning(
            "E-mail NÃO enviado (sem provedor configurado). Para: %s | Assunto: %s\n%s",
            message.to,
            message.subject,
            message.body,
        )


_default_sender = ConsoleEmailSender()


def get_email_sender() -> EmailSender:
    """Dependency do FastAPI. Nos testes, é sobrescrita por um sender em memória."""
    return _default_sender
