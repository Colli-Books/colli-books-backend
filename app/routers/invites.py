"""US02: primeiro acesso pelo convite.

O token vai no corpo, nunca na URL: caminhos e query strings acabam em logs.
"""

from fastapi import APIRouter, Depends, Request, status

from app.rate_limit import limiter
from app.routers.auth import token_response
from app.schemas.auth import TokenResponse
from app.schemas.errors import ErrorResponse
from app.schemas.invites import (
    InviteAcceptRequest,
    InviteTokenRequest,
    InviteVerifyResponse,
    MessageResponse,
)
from app.security.dependencies import DbSession
from app.services import auth as auth_service
from app.services import invites as invites_service
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/invites", tags=["Convites"])

_INVITE_ERRORS = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "`INVITE_INVALID`"},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "`INVITE_ALREADY_USED`"},
    status.HTTP_410_GONE: {"model": ErrorResponse, "description": "`INVITE_EXPIRED`"},
}


@router.post(
    "/verify",
    summary="Conferir convite",
    description="Confere o convite sem consumi-lo e devolve o e-mail, para a tela de criar senha.",
    response_model=InviteVerifyResponse,
    responses=_INVITE_ERRORS,
)
@limiter.limit("20/minute")
def verify(request: Request, body: InviteTokenRequest, db: DbSession) -> InviteVerifyResponse:
    user = invites_service.verify_invite(db, body.token)
    return InviteVerifyResponse(email=user.email)


@router.post(
    "/accept",
    summary="Aceitar convite",
    description=(
        "Define a senha (mín. 8 caracteres), ativa a conta e já devolve a sessão autenticada. "
        "Senha fraca responde `422 WEAK_PASSWORD`."
    ),
    response_model=TokenResponse,
    responses={
        **_INVITE_ERRORS,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def accept(request: Request, body: InviteAcceptRequest, db: DbSession) -> TokenResponse:
    user = invites_service.accept_invite(db, body.token, body.password)
    return token_response(auth_service.start_session(db, user))


@router.post(
    "/resend",
    summary="Reenviar convite expirado",
    description=(
        "Se o convite estiver expirado e não usado, gera um novo e o envia para o e-mail "
        "cadastrado. Sempre responde `202` com a mesma mensagem; o link novo nunca volta aqui."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
)
@limiter.limit("5/minute")
def resend(
    request: Request,
    body: InviteTokenRequest,
    db: DbSession,
    sender: EmailSender = Depends(get_email_sender),  # noqa: B008
) -> MessageResponse:
    invites_service.resend_invite(db, sender, body.token)
    return MessageResponse(
        message="Se o convite puder ser renovado, um novo link será enviado para o e-mail cadastrado."
    )
