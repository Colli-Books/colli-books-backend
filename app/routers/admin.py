"""US01: rotas da editora (administrador)."""

from fastapi import APIRouter, status

from app.models import User
from app.schemas.errors import ErrorResponse
from app.schemas.teachers import TeacherCreateRequest, TeacherInviteResponse
from app.security.dependencies import AdminUser, DbSession
from app.services import teachers as teachers_service
from app.services.invites import IssuedInvite

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
        "Cria o professor com status `invite_pending` e devolve o link de convite para a "
        "editora enviar. Enquanto a senha não for definida, o login fica bloqueado."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=TeacherInviteResponse,
    responses={**_AUTH_ERRORS, status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
)
def create_teacher(
    body: TeacherCreateRequest, db: DbSession, _: AdminUser
) -> TeacherInviteResponse:
    return _invite_response(*teachers_service.create_teacher(db, body.email))


@router.post(
    "/teachers/{teacher_id}/invite",
    summary="Gerar novo convite",
    description="Invalida os convites pendentes do professor e gera um novo link.",
    response_model=TeacherInviteResponse,
    responses={
        **_AUTH_ERRORS,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def reissue_invite(teacher_id: int, db: DbSession, _: AdminUser) -> TeacherInviteResponse:
    return _invite_response(*teachers_service.reissue_teacher_invite(db, teacher_id))
