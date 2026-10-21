from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

_Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]


class InviteTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Token do link ou código colado no app.")


class InviteAcceptRequest(InviteTokenRequest):
    """Dados que faltam no cadastro: a editora só informou o e-mail."""

    full_name: Annotated[_Text, StringConstraints(min_length=1)] = Field(
        ..., examples=["Maria Souza"]
    )
    school: _Text | None = Field(
        None,
        description="Opcional; pode ser preenchida depois.",
        examples=["E.E. Machado de Assis"],
    )
    password: str = Field(..., examples=["senha-segura-123"])

    @field_validator("school")
    @classmethod
    def _blank_school_is_none(cls, value: str | None) -> str | None:
        return value or None


class InviteVerifyResponse(BaseModel):
    email: str = Field(..., examples=["professor@escola.com"])


class MessageResponse(BaseModel):
    message: str
