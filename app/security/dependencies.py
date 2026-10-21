"""Dependencies de autenticação e autorização para as rotas.

Uso:

    @router.get("/algo")
    def algo(user: CurrentUser): ...

    @router.post("/admin/algo")
    def admin_algo(admin: AdminUser): ...
"""

from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models import User, UserRole, UserStatus
from app.security.tokens import decode_access_token

# auto_error=False: sem header, quem responde é a nossa função, no formato do contrato.
_bearer = HTTPBearer(auto_error=False, description="Access token obtido em `/api/v1/auth/login`.")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Autenticação necessária.",
            status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = decode_access_token(credentials.credentials)

    # O usuário é sempre relido do banco: uma conta desativada perde o acesso
    # na hora, sem esperar o access token expirar.
    user = db.get(User, claims.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Autenticação necessária.",
            status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """US05: rotas administrativas.

    O papel vem do banco, não do claim `role` do JWT, para que uma mudança de
    papel valha imediatamente.
    """
    if user.role != UserRole.ADMIN:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Acesso restrito a administradores.",
            status.HTTP_403_FORBIDDEN,
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
