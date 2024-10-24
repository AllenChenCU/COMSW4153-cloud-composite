from typing import Any

from pydantic import BaseModel, Json


class SavedRoute(BaseModel):
    source: str
    destination: str
    user_id: str
    route: Json[Any] # MySQL: route JSON NOT NULL
    