"""Routers da API de negócio, todos sob `/api/v1`.

O prefixo versionado existe porque o app publicado na loja não é atualizado na
hora: uma mudança incompatível vai para `/api/v2`, e as versões antigas do app
continuam funcionando.
"""

from fastapi import APIRouter

from app.routers import admin, auth, invites

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(auth.router)
api_router.include_router(invites.router)
api_router.include_router(admin.router)
