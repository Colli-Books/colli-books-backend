from pydantic import BaseModel, Field


class InviteTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Token do link ou código colado no app.")


class InviteAcceptRequest(InviteTokenRequest):
    password: str = Field(..., examples=["senha-segura-123"])


class InviteVerifyResponse(BaseModel):
    email: str = Field(..., examples=["professor@escola.com"])


class MessageResponse(BaseModel):
    message: str
