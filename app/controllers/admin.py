"""US01: rotas da editora (administrador)."""

from fastapi import APIRouter, Depends, status

from app.models import User
from app.security.dependencies import AdminUser, DbSession
from app.services import teachers as teachers_service
from app.services.email import EmailSender, get_email_sender
from app.services.invites import IssuedInvite
from app.views.errors import ErrorResponse
from app.views.teachers import TeacherCreateRequest, TeacherInviteResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

_AUTH_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}


def _invite_response(user: User, invite: IssuedInvite) -> TeacherInviteResponse:
    return TeacherInviteResponse(
        id=user.id,
        email=user.email,
        status=user.status,
        invite_link=invite.link,
        invite_code=invite.code,
        invite_expires_at=invite.expires_at,
    )


@router.post(
    "/teachers",
    summary="Cadastrar professor",
    description=(
        "Cria o professor com status `invite_pending` e manda o link de convite para o e-mail "
        "dele, onde ele completa o cadastro (nome, escola e senha). O link também volta na "
        "resposta, para a editora reenviar por outro canal. Enquanto o cadastro não for "
        "completado, o login fica bloqueado."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=TeacherInviteResponse,
    responses={**_AUTH_ERRORS, status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
)
def create_teacher(
    body: TeacherCreateRequest,
    db: DbSession,
    _: AdminUser,
    sender: EmailSender = Depends(get_email_sender),  # noqa: B008
) -> TeacherInviteResponse:
    return _invite_response(*teachers_service.create_teacher(db, sender, body.email))


@router.post(
    "/teachers/{teacher_id}/invite",
    summary="Gerar novo convite",
    description=(
        "Invalida os convites pendentes do professor, gera um novo link e o manda por e-mail."
    ),
    response_model=TeacherInviteResponse,
    responses={
        **_AUTH_ERRORS,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def reissue_invite(
    teacher_id: int,
    db: DbSession,
    _: AdminUser,
    sender: EmailSender = Depends(get_email_sender),  # noqa: B008
) -> TeacherInviteResponse:
    return _invite_response(*teachers_service.reissue_teacher_invite(db, sender, teacher_id))
