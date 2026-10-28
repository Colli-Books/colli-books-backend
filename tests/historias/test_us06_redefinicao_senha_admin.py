"""US06 — Redefinição de senha do administrador."""

from app.models import UserRole
from tests.redefinicao_senha import RedefinicaoSenha


class TestRedefinicaoSenhaAdmin(RedefinicaoSenha):
    role = UserRole.ADMIN
