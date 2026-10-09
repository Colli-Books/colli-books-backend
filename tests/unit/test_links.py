import pytest

from app.config import get_settings
from app.services.links import build_app_link


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("collibooks://", "collibooks://convite?token=abc-123"),
        ("https://colli.com.br", "https://colli.com.br/convite?token=abc-123"),
        ("https://colli.com.br/app/", "https://colli.com.br/app/convite?token=abc-123"),
    ],
)
def test_monta_link_a_partir_da_base(
    monkeypatch: pytest.MonkeyPatch, base: str, expected: str
) -> None:
    monkeypatch.setattr(get_settings(), "app_link_base_url", base)

    assert build_app_link("convite", "abc-123") == expected
