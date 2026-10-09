"""Funções para criar dados de teste."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import User, UserRole, UserStatus
from app.security.passwords import hash_password
from app.security.tokens import create_access_token

DEFAULT_PASSWORD = "senha-segura-123"


def create_user(
    session: Session,
    *,
    email: str | None = None,
    role: UserRole = UserRole.TEACHER,
    status: UserStatus = UserStatus.ACTIVE,
    password: str | None = DEFAULT_PASSWORD,
    full_name: str | None = None,
) -> User:
    """Cria e persiste (flush) um usuário.

    Para um convite pendente, use `status=UserStatus.INVITE_PENDING, password=None`
    (o banco proíbe conta ativa sem senha).
    """
    user = User(
        email=(email or f"user-{uuid4().hex[:8]}@example.com").lower(),
        role=role,
        status=status,
        password_hash=hash_password(password) if password is not None else None,
        full_name=full_name,
    )
    session.add(user)
    session.flush()
    return user


def auth_headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.role.value)
    return {"Authorization": f"Bearer {token}"}
