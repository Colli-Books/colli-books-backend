from fastapi import FastAPI

from app.controllers import api_router, health
from app.errors import register_error_handlers
from app.rate_limit import register_rate_limit

DESCRIPTION = """
API do projeto **Colli Books**.

Esta documentação é gerada automaticamente a partir do código pelo padrão
[OpenAPI](https://www.openapis.org/) e fica disponível em `/docs`, onde é possível
executar as requisições direto do navegador.

As rotas de negócio ficam sob `/api/v1`. Todo erro segue o formato
`{"code": "...", "message": "...", "details": ...}`, em que `code` é estável e
pode ser usado pelo app para decidir o que mostrar.
"""

TAGS_METADATA = [
    {
        "name": "Root",
        "description": "Endpoint raiz da aplicação.",
    },
    {
        "name": "Health",
        "description": "Verificação de saúde da API e da conexão com o banco de dados.",
    },
    {
        "name": "Auth",
        "description": "Login, renovação de sessão, logout e dados do usuário logado.",
    },
    {
        "name": "Convites",
        "description": "Primeiro acesso do professor a partir do link de convite.",
    },
    {
        "name": "Admin",
        "description": "Rotas exclusivas da editora (papel `admin`).",
    },
]

app = FastAPI(
    title="Colli Books API",
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    contact={"name": "Colli Books", "email": "admin@colli.com"},
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url=None,
)

register_error_handlers(app)
register_rate_limit(app)
app.include_router(health.router)
app.include_router(api_router)
