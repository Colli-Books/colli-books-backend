"""US01: cadastro de professor pela editora."""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models import User, UserRole, UserStatus
from app.services.auth import normalize_email
from app.services.invites import IssuedInvite, issue_invite


def _email_taken() -> AppError:
    return AppError(
        ErrorCode.EMAIL_ALREADY_REGISTERED,
        "Já existe um usuário com este e-mail.",
        status.HTTP_409_CONFLICT,
    )


def create_teacher(db: Session, email: str) -> tuple[User, IssuedInvite]:
    """Cria o professor com convite pendente. Faz commit."""
    email = normalize_email(email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise _email_taken()

    user = User(email=email, role=UserRole.TEACHER, status=UserStatus.INVITE_PENDING)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        # Dois cadastros simultâneos do mesmo e-mail: a UNIQUE do banco decide.
        db.rollback()
        raise _email_taken() from exc

    invite = issue_invite(db, user)
    db.commit()
    return user, invite


def reissue_teacher_invite(db: Session, teacher_id: int) -> tuple[User, IssuedInvite]:
    """Gera um convite novo para professor que ainda não ativou a conta. Faz commit."""
    user = db.get(User, teacher_id)
    if user is None or user.role != UserRole.TEACHER:
        raise AppError(ErrorCode.NOT_FOUND, "Professor não encontrado.", status.HTTP_404_NOT_FOUND)
    if user.status != UserStatus.INVITE_PENDING:
        raise AppError(
            ErrorCode.ACCOUNT_ALREADY_ACTIVE,
            "Este professor já definiu a senha.",
            status.HTTP_409_CONFLICT,
        )

    invite = issue_invite(db, user)
    db.commit()
    return user, invite
