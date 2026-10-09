from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import UserStatus


class TeacherCreateRequest(BaseModel):
    email: EmailStr = Field(..., examples=["professor@escola.com"])


class TeacherInviteResponse(BaseModel):
    """Professor com o convite recém-gerado.

    O link é exibido para a editora copiar e enviar (WhatsApp, e-mail). Como nem
    todo app deixa clicável um link `collibooks://`, o `invite_code` (o mesmo
    token) pode ser colado na tela "Tenho um convite".
    """

    id: int = Field(..., examples=[42])
    email: str = Field(..., examples=["professor@escola.com"])
    status: UserStatus = Field(..., examples=[UserStatus.INVITE_PENDING])
    invite_link: str = Field(..., examples=["collibooks://convite?token=..."])
    invite_code: str
    invite_expires_at: datetime
