from starlette.requests import Request

from app.config import get_settings
from app.rate_limit import client_ip


def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("10.0.0.1", 1234),
        }
    )


def test_sem_header_configurado_usa_o_ip_da_conexao(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "client_ip_header", None)
    assert client_ip(_request({"X-Forwarded-For": "203.0.113.7"})) == "10.0.0.1"


def test_com_header_configurado_usa_o_ip_do_cliente(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "client_ip_header", "x-forwarded-for")
    assert client_ip(_request({"X-Forwarded-For": "203.0.113.7, 10.0.0.2"})) == "203.0.113.7"


def test_header_configurado_ausente_usa_o_ip_da_conexao(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "client_ip_header", "x-forwarded-for")
    assert client_ip(_request({})) == "10.0.0.1"
