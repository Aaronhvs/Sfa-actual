from pydantic import BaseModel


class SeasonSchema(BaseModel):
    season: str
    is_latest: bool
    is_world_cup: bool = False
    key: str
    label: str
    kind: str
    includes_world_cup: bool = False


class SeasonsResponseSchema(BaseModel):
    seasons: list[SeasonSchema]
