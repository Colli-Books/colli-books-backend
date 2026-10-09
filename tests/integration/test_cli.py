"""US05: comando `seed-admin`."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import SeedAdminError, seed_admin
from app.models import User, UserRole, UserStatus
from app.security.passwords import verify_password
from tests.factories import create_user


def test_seed_cria_admin_ativo(db_session: Session) -> None:
    created = seed_admin(db_session, "Admin@Colli.com", "senha-segura-123", "Editora Colli")

    admin = db_session.scalar(select(User).where(User.email == "admin@colli.com"))
    assert created is True
    assert admin.role == UserRole.ADMIN
    assert admin.status == UserStatus.ACTIVE
    assert admin.full_name == "Editora Colli"
    assert verify_password("senha-segura-123", admin.password_hash)


def test_seed_rodado_duas_vezes_nao_duplica_nem_troca_a_senha(db_session: Session) -> None:
    seed_admin(db_session, "admin@colli.com", "senha-segura-123")

    created = seed_admin(db_session, "admin@colli.com", "outra-senha-456")

    admin = db_session.scalar(select(User).where(User.email == "admin@colli.com"))
    assert created is False
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert verify_password("senha-segura-123", admin.password_hash)


def test_seed_recusa_email_de_professor(db_session: Session) -> None:
    create_user(db_session, email="prof@escola.com")

    with pytest.raises(SeedAdminError):
        seed_admin(db_session, "prof@escola.com", "senha-segura-123")


def test_seed_recusa_senha_fraca(db_session: Session) -> None:
    with pytest.raises(SeedAdminError, match="8 caracteres"):
        seed_admin(db_session, "admin@colli.com", "curta")
