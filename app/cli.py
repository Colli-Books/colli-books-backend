"""Comandos administrativos.

    python -m app.cli seed-admin --email admin@colli.com [--name "Editora Colli"]
    python -m app.cli seed-demo
    python -m app.cli export-openapi [--output openapi.yaml]

A senha é lida da variável `ADMIN_PASSWORD` ou pedida no terminal, para não
ficar no histórico do shell. O comando é idempotente: se o admin já existe,
nada muda (nem a senha).

`seed-demo` popula temas, escolaridades, obras e páginas institucionais com os
mesmos dados do protótipo do app — também idempotente (rodar de novo não
duplica nada).

`export-openapi` grava a especificação OpenAPI do app em YAML (padrão) ou JSON
(sufixo `.json` no --output) — o arquivo versionado no repo serve para gerar o
cliente do app e comparar mudanças de contrato entre versões.
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.errors import AppError
from app.models import User, UserRole, UserStatus
from app.security.passwords import hash_password, validate_password_strength
from app.services.auth import normalize_email
from app.services.demo_seed import seed_demo


class SeedAdminError(Exception):
    pass


def export_openapi(output: Path) -> None:
    """Exporta `app.openapi()` em YAML (ou JSON, se o arquivo terminar em `.json`)."""
    from app.main import app  # importa tarde para não pagar o custo nos outros comandos

    spec = app.openapi()
    if output.suffix == ".json":
        output.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
        return

    try:
        import yaml
    except ImportError:
        raise SeedAdminError(
            "PyYAML não instalado; rode `pip install -r requirements-dev.txt` "
            "ou exporte com `--output openapi.json`."
        ) from None
    output.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False))


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

    commands.add_parser(
        "seed-demo",
        help="Popula temas, escolaridades, obras e páginas institucionais de demonstração.",
    )

    export = commands.add_parser(
        "export-openapi",
        help="Exporta a especificação OpenAPI em YAML (ou JSON, sufixo .json).",
    )
    export.add_argument("--output", default="openapi.yaml", type=Path)

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
    elif args.command == "seed-demo":
        with SessionLocal() as db:
            report = seed_demo(db)
        print(
            "Seed concluído. Criados agora: "
            f"{report.themes_created} temas, {report.education_levels_created} escolaridades, "
            f"{report.books_created} obras, {report.institutional_pages_created} páginas "
            "institucionais (o resto já existia)."
        )
    elif args.command == "export-openapi":
        try:
            export_openapi(args.output)
        except SeedAdminError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        print(f"Especificação exportada para {args.output}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
