"""US04 — Redefinição de senha (professor)."""

from app.models import UserRole
from tests.redefinicao_senha import RedefinicaoSenha


class TestRedefinicaoSenhaProfessor(RedefinicaoSenha):
    role = UserRole.TEACHER
