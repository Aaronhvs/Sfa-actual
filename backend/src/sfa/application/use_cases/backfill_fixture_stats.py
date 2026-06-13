from __future__ import annotations

import logging

from sfa.domain.ingestion_ports import FootballDataProviderPort, IngestionRepositoryPort

logger = logging.getLogger(__name__)


class BackfillFixtureStatsUseCase:
    """Re-fetch player stats from API-Football for all existing fixtures in a season.

    Only updates player_stats rows — does not touch events, scores, or fixtures.
    Skips players not yet in the DB (e.g. subs who never played a scored event).
    """

    def __init__(
        self,
        repo: IngestionRepositoryPort,
        provider: FootballDataProviderPort,
    ) -> None:
        self._repo = repo
        self._provider = provider

    async def execute(self, competition_id: int, season: str) -> dict:
        fixtures = await self._repo.get_season_fixtures(competition_id, season)
        logger.info(
            "[BackfillFixtureStatsUseCase] Found %d fixtures for competition=%d season=%s",
            len(fixtures), competition_id, season,
        )

        upserted = 0
        skipped = 0

        for fx in fixtures:
            players = await self._provider.fetch_all_fixture_players(fx.fixture_external_id)
            for ps in players:
                player_id = await self._repo.get_player_id_by_external(ps.player_external_id)
                if player_id is None:
                    skipped += 1
                    continue

                await self._repo.upsert_player_stats(
                    player_id=player_id,
                    fixture_id=fx.fixture_id,
                    season=fx.season,
                    stats={
                        "goals": ps.goals,
                        "assists": ps.assists,
                        "shots_on": ps.shots_on,
                        "shots_total": ps.shots_total,
                        "passes_key": ps.passes_key,
                        "passes_total": ps.passes_total,
                        "passes_accuracy": ps.passes_accuracy,
                        "dribbles_won": ps.dribbles_success,
                        "dribbles_attempts": ps.dribbles_attempts,
                        "dribbles_past": ps.dribbles_past,
                        "duels_won": ps.duels_won,
                        "duels_total": ps.duels_total,
                        "tackles_won": ps.tackles,
                        "interceptions": ps.interceptions,
                        "blocks": ps.blocks,
                        "fouls_drawn": ps.fouls_drawn,
                        "fouls_committed": ps.fouls_committed,
                        "cards_yellow": ps.cards_yellow,
                        "cards_red": ps.cards_red,
                        "penalty_won": ps.penalty_won,
                        "saves": ps.saves,
                        "goals_conceded": ps.goals_conceded,
                        "minutes": ps.minutes,
                        "rating": ps.rating,
                    },
                )
                upserted += 1

        logger.info(
            "[BackfillFixtureStatsUseCase] Done — upserted=%d skipped=%d",
            upserted, skipped,
        )
        return {"fixtures": len(fixtures), "upserted": upserted, "skipped": skipped}
