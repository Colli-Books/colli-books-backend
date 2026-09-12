# Colli Books Backend

Ambiente Docker com **PostgreSQL**, **pgAdmin** e um **backend FastAPI** (hello world).

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) 24+
- Docker Compose v2 (já incluso no Docker Desktop)

Verifique com:

```bash
docker --version
docker compose version
```

## Estrutura

```
colli-books-backend/
├── app/
│   ├── __init__.py
│   └── main.py           # aplicação FastAPI
├── Dockerfile            # imagem do backend
├── docker-compose.yml    # orquestra db + pgadmin + backend
├── requirements.txt      # dependências Python
└── .env.example          # variáveis de ambiente de exemplo
```

## Como executar

1. Copie o arquivo de variáveis de ambiente:

```bash
cp .env.example .env
```

2. Suba os serviços:

```bash
docker compose up --build
```

Use `-d` para rodar em segundo plano:

```bash
docker compose up --build -d
```

3. Acompanhe os logs (se estiver em segundo plano):

```bash
docker compose logs -f backend
```

## Serviços disponíveis

| Serviço      | URL                                  | Credenciais                 |
|--------------|--------------------------------------|-----------------------------|
| Backend      | http://localhost:8000                | —                           |
| Swagger UI   | http://localhost:8000/docs           | —                           |
| ReDoc        | http://localhost:8000/redoc          | —                           |
| OpenAPI JSON | http://localhost:8000/openapi.json   | —                           |
| pgAdmin      | http://localhost:5050                | `admin@colli.com` / `admin` |
| Postgres     | `localhost:5432`                     | `postgres` / `postgres`     |

## Documentação da API

A documentação é gerada automaticamente pelo FastAPI a partir do código, seguindo o
padrão [OpenAPI 3.1](https://www.openapis.org/). Não é preciso escrever nem manter
nada à mão: ao adicionar um endpoint, ele aparece na página sozinho.

Com os containers no ar, acesse:

- **http://localhost:8000/docs** — Swagger UI. Lista todos os endpoints agrupados por
  tag e permite **executar** as requisições direto do navegador (botão *Try it out*).
- **http://localhost:8000/redoc** — ReDoc. Mesma informação, layout de leitura,
  bom para consulta e para imprimir/exportar.
- **http://localhost:8000/openapi.json** — o esquema OpenAPI bruto, usado para gerar
  clientes (`openapi-generator`), importar no Postman/Insomnia, etc.

### Endpoints

| Método | Rota      | Tag    | Descrição                                  | Respostas  |
|--------|-----------|--------|--------------------------------------------|------------|
| `GET`  | `/`       | Root   | Hello world; confirma que a API está no ar | `200`      |
| `GET`  | `/health` | Health | Executa `SELECT 1` no PostgreSQL           | `200`, `503` |

### Testando o backend

```bash
curl http://localhost:8000
# {"message":"Hello World"}

curl http://localhost:8000/health
# {"status":"ok","database":"connected"}

# com o banco fora do ar, o mesmo endpoint responde 503:
docker compose stop db
curl -i http://localhost:8000/health
# HTTP/1.1 503 Service Unavailable
# {"status":"error","database":"(psycopg.OperationalError) ..."}
docker compose start db
```

### Documentando novos endpoints

Os metadados da página ficam em `app/main.py`:

- `FastAPI(title=..., description=..., version=..., openapi_tags=...)` controla o
  cabeçalho da página e a descrição de cada tag.
- Em cada rota, `tags`, `summary`, `description` e `response_model` definem como o
  endpoint aparece na documentação.
- Os modelos Pydantic (`HelloResponse`, `HealthResponse`) viram os *schemas* exibidos
  no rodapé da página, com os exemplos definidos em `Field(..., examples=[...])`.

### Conectando o pgAdmin ao Postgres

1. Acesse http://localhost:5050 e faça login com as credenciais acima.
2. Clique com o botão direito em **Servers** → **Register** → **Server...**
3. Aba **General**: `Name` = `colli-books`
4. Aba **Connection**:
   - Host name/address: `db`  ← nome do serviço no compose, **não** use `localhost`
   - Port: `5432`
   - Maintenance database: `colli_books`
   - Username: `postgres`
   - Password: `postgres` (marque *Save password*)
5. **Save**.

## Comandos úteis

```bash
# parar os containers (mantém os dados)
docker compose down

# parar e apagar os volumes (apaga o banco)
docker compose down -v

# reconstruir apenas o backend
docker compose up --build backend

# abrir um shell no container do backend
docker compose exec backend bash

# abrir o psql no container do banco
docker compose exec db psql -U postgres -d colli_books

# ver o status dos serviços
docker compose ps
```

## Observações

- O diretório `./app` é montado como volume no container do backend e o `uvicorn` roda com `--reload`, então alterações no código são aplicadas automaticamente.
- O backend só inicia depois que o healthcheck do Postgres passa (`depends_on: service_healthy`).
- Os dados do Postgres e do pgAdmin persistem nos volumes `postgres_data` e `pgadmin_data`.
- As credenciais padrão servem apenas para desenvolvimento local. Troque-as no `.env` antes de qualquer uso real.

## Solução de problemas

**Porta já em uso** (`port is already allocated`): altere `POSTGRES_PORT`, `PGADMIN_PORT` ou `BACKEND_PORT` no `.env` e suba novamente.

**pgAdmin não conecta**: confirme que usou `db` como host, e não `localhost`. Dentro da rede do Docker, `localhost` aponta para o próprio container do pgAdmin.

**Backend não sobe**: veja os logs com `docker compose logs backend` e confirme que o serviço `db` está *healthy* com `docker compose ps`.
