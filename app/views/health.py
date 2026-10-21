from pydantic import BaseModel, Field


class HelloResponse(BaseModel):
    message: str = Field(..., examples=["Hello World"])


class HealthResponse(BaseModel):
    status: str = Field(..., description="`ok` ou `error`.", examples=["ok"])
    database: str = Field(
        ...,
        description="`connected` quando o banco responde; caso contrário, o erro.",
        examples=["connected"],
    )
