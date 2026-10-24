"""Controllers (C do MVC): recebem o HTTP, chamam o Model e devolvem a View.

Cada controller é um `APIRouter` do FastAPI. Não guardam regra de negócio: só
validam a entrada (via Views), chamam `app/services/` e traduzem o resultado.
Todos ficam sob `/api/v1`.

O prefixo versionado existe porque o app publicado na loja não é atualizado na
hora: uma mudança incompatível vai para `/api/v2`, e as versões antigas do app
continuam funcionando.
"""

from fastapi import APIRouter

from app.controllers import admin, auth, books, education_levels, invites, me, themes

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(auth.router)
api_router.include_router(invites.router)
api_router.include_router(admin.router)
api_router.include_router(themes.router)
api_router.include_router(education_levels.router)
api_router.include_router(books.router)
api_router.include_router(me.router)
