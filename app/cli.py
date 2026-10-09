"""Comandos administrativos.

    python -m app.cli seed-admin --email admin@colli.com [--name "Editora Colli"]

A senha é lida da variável `ADMIN_PASSWORD` ou pedida no terminal, para não
ficar no histórico do shell. O comando é idempotente: se o admin já existe,
nada muda (nem a senha).
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.errors import AppError
from app.models import User, UserRole, UserStatus
from app.security.passwords import hash_password, validate_password_strength
from app.services.auth import normalize_email


class SeedAdminError(Exception):
    pass


def seed_admin(db: Session, email: str, password: str, full_name: str | None = None) -> bool:
    """US05: cria o administrador inicial. Retorna `True` se criou, `False` se já existia."""
    email = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.role != UserRole.ADMIN:
            raise SeedAdminError(f"O e-mail {email} já pertence a um usuário que não é admin.")
        return False

    try:
        validate_password_strength(password)
    except AppError as exc:
        raise SeedAdminError(exc.message) from exc

    db.add(
        User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            full_name=full_name,
        )
    )
    db.commit()
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser("seed-admin", help="Cria o administrador inicial (idempotente).")
    seed.add_argument("--email", required=True)
    seed.add_argument("--name", default=None, help="Nome exibido no cabeçalho do app.")

    args = parser.parse_args(argv)

    if args.command == "seed-admin":
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Senha do admin: ")
        with SessionLocal() as db:
            try:
                created = seed_admin(db, args.email, password, args.name)
            except SeedAdminError as exc:
                print(f"Erro: {exc}", file=sys.stderr)
                return 1
        print("Admin criado." if created else "Admin já existe; nada foi alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
