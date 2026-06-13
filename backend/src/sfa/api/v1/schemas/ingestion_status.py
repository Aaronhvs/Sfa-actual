from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompetitionIngestionStatusResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    competition_name: str
    league_id: int
    season: str
    status: str
    fixtures_in_db: int
    last_ingested_at: datetime | None
    error_msg: str | None
