"""Envio de e-mails (convite na US01/US02, redefinição de senha na US04/US06).

Ainda não há provedor de e-mail definido. Por enquanto a única implementação é
`ConsoleEmailSender`, que escreve a mensagem no log do servidor. Quando houver
provedor, basta criar outra classe com o mesmo método `send` e devolvê-la em
`get_email_sender`.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Escreve o e-mail no log, para desenvolvimento.

    O corpo leva links de convite e de redefinição de senha válidos; quem lê o
    log conseguiria usá-los. Por isso, em produção só o destinatário e o
    assunto são escritos (a editora ainda recebe o link do convite na resposta).
    """

    def send(self, message: EmailMessage) -> None:
        if get_settings().app_env == "production":
            logger.error(
                "E-mail NÃO enviado (sem provedor configurado). Para: %s | Assunto: %s",
                message.to,
                message.subject,
            )
            return
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
