"""Contas de acesso e os tokens de uso único que governam o ciclo de vida delas.

Cobre as US01–US06 (Épico 1 — Acesso e Contas). Professor e administrador vivem
na mesma tabela `users`, diferenciados pela coluna `role`, conforme a nota
técnica da US05: não há endpoint nem tabela separada para administrador.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Book, EducationLevel, Theme


class UserRole(str, enum.Enum):
    """Perfis do sistema. Não há auto-cadastro: quem entra é criado pela editora."""

    ADMIN = "admin"
    TEACHER = "teacher"


class UserStatus(str, enum.Enum):
    """Estado da conta.

    `INVITE_PENDING` é o estado inicial da US01 — a conta existe, mas ainda não
    tem senha e por isso o login é bloqueado.
    """

    INVITE_PENDING = "invite_pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # O e-mail é a identidade do usuário e a chave do convite: guardamos
        # sempre em minúsculas para que a UNIQUE acima seja, na prática,
        # insensível a maiúsculas.
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        # US01: "ENQUANTO a senha não for definida, o login é bloqueado."
        # Uma conta ativa sem hash de senha seria exatamente esse furo.
        CheckConstraint(
            "status <> 'active' OR password_hash IS NOT NULL",
            name="ck_users_active_requires_password",
        ),
        Index("ix_users_role_status", "role", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Nulo enquanto o convite não é aceito (US01/US02).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.TEACHER,
        server_default=UserRole.TEACHER.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserStatus.INVITE_PENDING,
        server_default=UserStatus.INVITE_PENDING.value,
    )
    # US10: o professor completa nome e escola; a editora só informa o e-mail.
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    school: Mapped[str | None] = mapped_column(String(255), nullable=True)

    invites: Mapped[list[Invite]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    themes: Mapped[list[Theme]] = relationship(
        secondary="teacher_themes", back_populates="teachers"
    )
    education_levels: Mapped[list[EducationLevel]] = relationship(
        secondary="teacher_education_levels", back_populates="teachers"
    )
    saved_books: Mapped[list[Book]] = relationship(
        secondary="saved_books", back_populates="saved_by"
    )


class _SingleUseToken(TimestampMixin):
    """Base dos tokens de uso único (convite e redefinição de senha).

    Guardamos apenas o *hash* do token: o valor em claro só existe no link
    entregue ao usuário. Vazamento do banco não permite forjar um acesso.
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # `used_at` preenchido distingue "já usado" de "expirado" — a US02 exige
    # mensagens diferentes para os dois casos.
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Invite(_SingleUseToken, Base):
    """Link de convite gerado na US01 e consumido na US02."""

    __tablename__ = "invites"
    __table_args__ = (Index("ix_invites_user_id", "user_id"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="invites")


class PasswordResetToken(_SingleUseToken, Base):
    """Link de "Esqueci minha senha" das US04 e US06."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (Index("ix_password_reset_tokens_user_id", "user_id"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class RefreshToken(TimestampMixin, Base):
    """Refresh token revogável da US03.

    O access token (JWT) é curto e expira sozinho; o logout precisa de algo
    revogável, e é este registro.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
