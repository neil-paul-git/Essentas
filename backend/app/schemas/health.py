from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    environment: str


class DbHealthResponse(BaseModel):
    status: Literal["ok"]
