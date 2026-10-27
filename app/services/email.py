"""Envio de e-mails (convite na US01/US02, redefinição de senha na US04/US06).

O provedor é o **Brevo** (API transacional). Assunto, remetente e corpo de cada
e-mail vivem em *templates* cadastrados no painel do Brevo — o backend só envia
o tipo de e-mail (`EmailKind`, que mapeia para o ID do template), o destinatário
e os parâmetros (`params`) usados pelos templates (`link`, `code`,
`expires_at`/`ttl_minutes`).

Duas proteções:

* Sem `BREVO_API_KEY` configurada, cai no `ConsoleEmailSender`, que escreve a
  mensagem no log do servidor (comportamento de desenvolvimento).
* O envio roda em background, **depois** da resposta HTTP: uma falha no Brevo
  nunca quebra o request e não o atrasa. A falha é registrada em log
  (`_safe_send`) e todos os fluxos são recuperáveis — o link do convite volta
  na resposta da API e há endpoints de reenvio e de novo pedido de redefinição.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Protocol

from brevo import Brevo
from brevo.transactional_emails import SendTransacEmailRequestToItem
from fastapi import BackgroundTasks

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailKind(StrEnum):
    """Tipos de e-mail; cada um mapeia para um template do Brevo."""

    INVITE = "invite"
    INVITE_RENEWAL = "invite_renewal"
    PASSWORD_RESET = "password_reset"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    kind: EmailKind
    params: dict[str, str]


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Escreve o e-mail no log, para desenvolvimento.

    Os params levam links de convite e de redefinição válidos; quem lê o log
    conseguiria usá-los. Por isso, em produção só o destinatário e o tipo são
    escritos (a editora ainda recebe o link do convite na resposta).
    """

    def send(self, message: EmailMessage) -> None:
        if get_settings().app_env == "production":
            logger.error(
                "E-mail NÃO enviado (sem provedor configurado). Para: %s | Tipo: %s",
                message.to,
                message.kind.value,
            )
            return
        logger.warning(
            "E-mail NÃO enviado (sem provedor configurado). Para: %s | Tipo: %s\nparams=%s",
            message.to,
            message.kind.value,
            message.params,
        )


class BrevoEmailSender:
    """Envia pela API transacional do Brevo, com template do painel.

    Com `template_id`, o assunto e o remetente do próprio template são usados
    pelo Brevo — o backend não os define. O cliente é injetável para os testes.
    """

    def __init__(self, client: Brevo, template_ids: dict[EmailKind, int]) -> None:
        self._client = client
        self._template_ids = template_ids

    def send(self, message: EmailMessage) -> None:
        template_id = self._template_ids[message.kind]
        if template_id <= 0:
            raise RuntimeError(f"Template do Brevo não configurado para '{message.kind.value}'.")
        self._client.transactional_emails.send_transac_email(
            template_id=template_id,
            # Nome opcional: no convite, o professor ainda não o cadastrou.
            to=[SendTransacEmailRequestToItem(email=message.to)],
            params=message.params,
        )


def _safe_send(sender: EmailSender, message: EmailMessage) -> None:
    """Executa o envio em background; falhas são logadas, nunca propagadas.

    O log traz destinatário e tipo, mas não os params: o link carrega um token
    de uso único e não deve vazar em log.
    """
    try:
        sender.send(message)
    except Exception:
        logger.exception(
            "Falha ao enviar e-mail para %s (tipo=%s).",
            message.to,
            message.kind.value,
        )


class BackgroundEmailSender:
    """Enfileira o envio para depois da resposta HTTP.

    A dependency `get_email_sender` devolve esta classe em volta do sender real:
    controllers e services chamam `send()` normalmente, e o acesso ao provedor
    acontece em background, sem atrasar ou quebrar o request.
    """

    def __init__(self, tasks: BackgroundTasks, inner: EmailSender) -> None:
        self._tasks = tasks
        self._inner = inner

    def send(self, message: EmailMessage) -> None:
        self._tasks.add_task(_safe_send, self._inner, message)


@lru_cache
def _default_sender() -> EmailSender:
    settings = get_settings()
    if settings.brevo_api_key:
        return BrevoEmailSender(
            Brevo(api_key=settings.brevo_api_key),
            {
                EmailKind.INVITE: settings.brevo_template_invite,
                EmailKind.INVITE_RENEWAL: settings.brevo_template_invite_renewal,
                EmailKind.PASSWORD_RESET: settings.brevo_template_password_reset,
            },
        )
    if settings.app_env == "production":
        logger.error("BREVO_API_KEY não configurada: nenhum e-mail sairá em produção.")
    return ConsoleEmailSender()


def get_email_sender(background_tasks: BackgroundTasks) -> EmailSender:
    """Dependency do FastAPI: sender real (Brevo ou console) + envio em background.

    Nos testes, é sobrescrita por um sender em memória (envolto nesta classe,
    o caminho de background continua exercitado).
    """
    return BackgroundEmailSender(background_tasks, _default_sender())
