from pydantic import BaseModel


class SeasonSchema(BaseModel):
    season: str
    is_latest: bool


class SeasonsResponseSchema(BaseModel):
    seasons: list[SeasonSchema]
