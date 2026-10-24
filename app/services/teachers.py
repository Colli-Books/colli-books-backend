"""US01: cadastro de professor pela editora.

A editora informa só o e-mail. O professor recebe o link de convite por e-mail e
completa o cadastro (nome, escola e senha) na US02.
"""

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models import Book, User, UserRole, UserStatus
from app.services.auth import normalize_email
from app.services.email import EmailSender
from app.services.invites import IssuedInvite, issue_invite, send_invite_email


def _email_taken() -> AppError:
    return AppError(
        ErrorCode.EMAIL_ALREADY_REGISTERED,
        "Já existe um usuário com este e-mail.",
        status.HTTP_409_CONFLICT,
    )


def create_teacher(db: Session, sender: EmailSender, email: str) -> tuple[User, IssuedInvite]:
    """Cria o professor com convite pendente e manda o link para o e-mail dele. Faz commit."""
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
    send_invite_email(sender, user, invite)
    return user, invite


def reissue_teacher_invite(
    db: Session, sender: EmailSender, teacher_id: int
) -> tuple[User, IssuedInvite]:
    """Gera um convite novo para professor que ainda não ativou a conta e o manda por e-mail.

    Faz commit.
    """
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
    send_invite_email(sender, user, invite, renewed=True)
    return user, invite


def list_teachers(db: Session, *, status_filter: UserStatus | None, q: str | None) -> list[User]:
    """Gestão de professores (tela do admin): filtro por status e busca por
    nome/e-mail. Lista integral — a base é pequena e o app monta os filtros."""
    stmt = select(User).where(User.role == UserRole.TEACHER)
    if status_filter is not None:
        stmt = stmt.where(User.status == status_filter)
    if q and q.strip():
        pattern = f"%{q.strip().lower()}%"
        unaccented = func.immutable_unaccent(func.lower(func.coalesce(User.full_name, "")))
        stmt = stmt.where(unaccented.like(pattern) | User.email.like(pattern))
    stmt = stmt.order_by(func.lower(func.coalesce(User.full_name, "")), User.email, User.id)
    return list(db.scalars(stmt))


def overview(db: Session) -> tuple[int, int, int]:
    """US13: (obras, professores, convites pendentes) em consultas COUNT."""
    books_count = db.scalar(select(func.count(Book.id))) or 0
    teachers_count = (
        db.scalar(select(func.count(User.id)).where(User.role == UserRole.TEACHER)) or 0
    )
    pending_invites = (
        db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.TEACHER,
                User.status == UserStatus.INVITE_PENDING,
            )
        )
        or 0
    )
    return books_count, teachers_count, pending_invites
