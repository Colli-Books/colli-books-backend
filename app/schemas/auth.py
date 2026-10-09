from pydantic import BaseModel, EmailStr, Field

from app.schemas.users import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["professor@escola.com"])
    password: str = Field(..., min_length=1, examples=["senha-segura-123"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT curto, enviado em `Authorization: Bearer`.")
    refresh_token: str = Field(
        ...,
        description=(
            "Token opaco e longo. Guardar no armazenamento seguro do aparelho e usar em "
            "`/auth/refresh`. Cada uso devolve um novo; o anterior deixa de valer."
        ),
    )
    token_type: str = Field("bearer", examples=["bearer"])
    expires_in: int = Field(
        ..., description="Validade do access token, em segundos.", examples=[900]
    )
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., examples=["professor@escola.com"])


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Token do link ou código colado no app.")
    new_password: str = Field(..., examples=["minha-senha-nova"])
