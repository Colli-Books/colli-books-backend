"""Routers da API de negócio, todos sob `/api/v1`.

O prefixo versionado existe porque o app publicado na loja não é atualizado na
hora: uma mudança incompatível vai para `/api/v2`, e as versões antigas do app
continuam funcionando.
"""

from fastapi import APIRouter

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)

# Os routers de auth, convites e admin entram aqui nas próximas fases:
# api_router.include_router(auth.router)
