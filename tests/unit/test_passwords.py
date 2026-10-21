import pytest

from app.errors import AppError, ErrorCode
from app.security.passwords import hash_password, validate_password_strength, verify_password


def test_hash_nao_guarda_a_senha_em_claro() -> None:
    hashed = hash_password("senha-segura-123")
    assert "senha-segura-123" not in hashed
    assert hashed.startswith("$argon2")


def test_verifica_senha_correta_e_rejeita_incorreta() -> None:
    hashed = hash_password("senha-segura-123")
    assert verify_password("senha-segura-123", hashed) is True
    assert verify_password("senha-errada-123", hashed) is False


def test_mesma_senha_gera_hashes_diferentes() -> None:
    # Salt aleatório: dois usuários com a mesma senha não têm o mesmo hash.
    assert hash_password("senha-segura-123") != hash_password("senha-segura-123")


def test_sem_hash_a_verificacao_sempre_falha() -> None:
    # Usuário inexistente ou convite pendente (password_hash = NULL).
    assert verify_password("qualquer-coisa", None) is False


@pytest.mark.parametrize("password", ["12345678", "a" * 128])
def test_aceita_senha_dentro_dos_limites(password: str) -> None:
    validate_password_strength(password)


@pytest.mark.parametrize("password", ["", "1234567", "a" * 129])
def test_rejeita_senha_fora_dos_limites(password: str) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_password_strength(password)
    assert exc_info.value.code == ErrorCode.WEAK_PASSWORD
    assert exc_info.value.status_code == 422
