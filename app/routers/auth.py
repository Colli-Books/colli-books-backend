"""US03 (login, logout, sessão) e US05 (identificação do usuário logado)."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.errors import ErrorCode
from app.rate_limit import limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.errors import ErrorResponse
from app.schemas.invites import MessageResponse
from app.schemas.users import UserResponse
from app.security.dependencies import CurrentUser, DbSession
from app.services import auth as auth_service
from app.services import password_reset as password_reset_service
from app.services.auth import SessionTokens
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/auth", tags=["Auth"])

_UNAUTHORIZED = {status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}


def token_response(tokens: SessionTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserResponse.model_validate(tokens.user),
    )


@router.post(
    "/login",
    summary="Login",
    description=(
        "Autentica com e-mail e senha. Qualquer falha (e-mail inexistente, senha errada, "
        f"convite pendente, conta inativa) responde `401 {ErrorCode.INVALID_CREDENTIALS}`."
    ),
    response_model=TokenResponse,
    responses=_UNAUTHORIZED,
)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: DbSession) -> TokenResponse:
    user = auth_service.authenticate(db, body.email, body.password)
    return token_response(auth_service.start_session(db, user))


@router.post(
    "/refresh",
    summary="Renovar sessão",
    description=(
        "Troca o refresh token por um par novo. O token enviado deixa de valer. "
        "Reusar um token já trocado encerra todas as sessões do usuário. "
        f"Qualquer falha responde `401 {ErrorCode.TOKEN_INVALID}`: o app deve voltar ao login."
    ),
    response_model=TokenResponse,
    responses=_UNAUTHORIZED,
)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    return token_response(auth_service.rotate_refresh_token(db, body.refresh_token))


@router.post(
    "/logout",
    summary="Logout",
    description="Revoga o refresh token informado. Sempre responde `204`, mesmo se já revogado.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(body: RefreshTokenRequest, db: DbSession) -> Response:
    auth_service.end_session(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    summary="Usuário logado",
    description="Dados do usuário dono do access token. O app usa `role` para exibir a área admin.",
    response_model=UserResponse,
    responses=_UNAUTHORIZED,
)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post(
    "/forgot-password",
    summary="Esqueci minha senha",
    description=(
        "Envia o link de redefinição para o e-mail, se houver conta ativa. Sempre responde "
        "`202` com a mesma mensagem, para não revelar se o e-mail está cadastrado."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: DbSession,
    sender: EmailSender = Depends(get_email_sender),  # noqa: B008
) -> MessageResponse:
    password_reset_service.request_password_reset(db, sender, body.email)
    return MessageResponse(
        message="Se houver uma conta com este e-mail, enviaremos um link de redefinição."
    )


@router.post(
    "/reset-password",
    summary="Redefinir senha",
    description=(
        "Troca a senha usando o token do link. O token vale uma vez só e todas as sessões "
        f"abertas são encerradas. Token inválido, usado ou expirado: `400 "
        f"{ErrorCode.RESET_TOKEN_INVALID}`; senha fraca: `422 {ErrorCode.WEAK_PASSWORD}`."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: DbSession) -> Response:
    password_reset_service.reset_password(db, body.token, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
