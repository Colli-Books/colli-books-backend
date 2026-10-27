"""Entrypoint serverless da Vercel — expõe o app ASGI de `app.main`."""

from app.main import app  # noqa: F401
