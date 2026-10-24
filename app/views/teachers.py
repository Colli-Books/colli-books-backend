from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import UserStatus


class TeacherCreateRequest(BaseModel):
    email: EmailStr = Field(..., examples=["professor@escola.com"])


class AdminOverviewResponse(BaseModel):
    """Contadores do painel do admin (US13) em uma única chamada."""

    books_count: int = Field(..., examples=[58])
    teachers_count: int = Field(..., examples=[23])
    pending_invites_count: int = Field(
        ..., description="Professores com convite ainda não aceito.", examples=[4]
    )


class TeacherInviteResponse(BaseModel):
    """Professor com o convite recém-gerado.

    O convite já foi enviado para o e-mail do professor. O link também volta aqui
    para a editora reenviar por outro canal (WhatsApp) se o e-mail não chegar.
    Como nem todo app deixa clicável um link `collibooks://`, o `invite_code`
    (o mesmo token) pode ser colado na tela "Tenho um convite".
    """

    id: int = Field(..., examples=[42])
    email: str = Field(..., examples=["professor@escola.com"])
    status: UserStatus = Field(..., examples=[UserStatus.INVITE_PENDING])
    invite_link: str = Field(..., examples=["collibooks://convite?token=..."])
    invite_code: str
    invite_expires_at: datetime
