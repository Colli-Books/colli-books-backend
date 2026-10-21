from fastapi import FastAPI, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.errors import register_error_handlers
from app.rate_limit import register_rate_limit
from app.routers import api_router

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
app.include_router(api_router)


class HelloResponse(BaseModel):
    message: str = Field(..., examples=["Hello World"])


class HealthResponse(BaseModel):
    status: str = Field(..., description="`ok` ou `error`.", examples=["ok"])
    database: str = Field(
        ...,
        description="`connected` quando o banco responde; caso contrário, o erro.",
        examples=["connected"],
    )


@app.get(
    "/",
    tags=["Root"],
    summary="Hello World",
    description="Retorna uma mensagem estática para confirmar que a API está no ar.",
    response_model=HelloResponse,
)
def hello_world() -> HelloResponse:
    return HelloResponse(message="Hello World")


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Executa um `SELECT 1` no PostgreSQL. "
        "Responde **200** quando o banco está acessível e **503** quando não está."
    ),
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "O banco de dados não está acessível.",
        }
    },
)
def health(response: Response) -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database=str(exc))
    return HealthResponse(status="ok", database="connected")
