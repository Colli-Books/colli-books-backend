from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole, UserStatus


class UserResponse(BaseModel):
    """Dados do usuário logado. O app usa `role` para mostrar (ou não) a área administrativa."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., examples=[1])
    email: str = Field(..., examples=["professor@escola.com"])
    full_name: str | None = Field(None, examples=["Maria Souza"])
    role: UserRole = Field(..., examples=[UserRole.TEACHER])
    status: UserStatus = Field(..., examples=[UserStatus.ACTIVE])
