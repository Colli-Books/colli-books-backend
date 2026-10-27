from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from app.config import get_settings
from app.controllers import api_router, health
from app.errors import register_error_handlers
from app.rate_limit import register_rate_limit

DESCRIPTION = """
API do projeto **Colli Books**.

As rotas de negócio ficam sob `/api/v1`. Todo erro segue o formato
`{"code": "...", "message": "...", "details": ...}`.
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
    {
        "name": "Obras",
        "description": "Catálogo de obras: busca e detalhe para todos; cadastro e edição só da editora.",
    },
    {
        "name": "Temas",
        "description": "Temas do acervo: listagem aberta a logados; criação e renomeação só da editora.",
    },
    {
        "name": "Escolaridades",
        "description": "Escolaridades do acervo: listagem aberta a logados; criação e renomeação só da editora.",
    },
    {
        "name": "Perfil",
        "description": "Dados do próprio usuário, temas/escolaridades que leciona e Minha Seleção.",
    },
]

app = FastAPI(
    title="Colli Books API",
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    # /docs é servido pela rota custom abaixo, com os assets do swagger-ui
    # hospedados no próprio backend (sem depender de CDN).
    docs_url=None,
    redoc_url=None,
)

register_error_handlers(app)
register_rate_limit(app)
app.include_router(health.router)
app.include_router(api_router)

_STATIC_DIR = Path(__file__).parent / "static"
_SWAGGER_UI_DIR = "/static/swagger-ui"

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    """Swagger UI (SmartBear) com assets locais — funciona sem internet."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — Swagger UI",
        swagger_js_url=f"{_SWAGGER_UI_DIR}/swagger-ui-bundle.js",
        swagger_css_url=f"{_SWAGGER_UI_DIR}/swagger-ui.css",
        swagger_favicon_url=f"{_SWAGGER_UI_DIR}/favicon-32x32.png",
        # Mantém o Bearer do Authorize depois de dar refresh na página.
        swagger_ui_parameters={"persistAuthorization": True},
    )


# Capas enviadas pelo admin; a pasta só é criada no primeiro upload
# (`check_dir=False` permite importar o app sem que ela exista).
app.mount(
    "/media",
    StaticFiles(directory=get_settings().media_dir, check_dir=False),
    name="media",
)
