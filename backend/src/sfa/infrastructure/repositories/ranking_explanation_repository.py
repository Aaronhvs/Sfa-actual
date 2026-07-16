from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import RankedPlayerDTO
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationEvidenceDTO,
    RankingExplanationRequestDTO,
    RankingExplanationWriteResultDTO,
    RankingPlayerExplanationDTO,
)
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models import (
    Competition,
    Fixture,
    Player,
    PlayerEvent,
    PlayerEventScore,
    PlayerStats,
    SFASeasonScore,
    Team,
)
from sfa.infrastructure.models.ranking_explanations.models import RankingPlayerExplanation


PUBLIC_STATUSES = ("generated", "fallback")
STAGE_LABELS_ES = {
    "group": "fase de grupos",
    "group_stage": "fase de grupos",
    "round_of_32": "dieciseisavos",
    "round_of_16": "octavos",
    "quarter_final": "cuartos de final",
    "semi_final": "semifinal",
    "third_place": "tercer puesto",
    "final": "final",
}
ACTION_LABELS_ES = {
    "goal": "gol",
    "goal_penalty": "gol de penal",
    "goal_shootout": "penal convertido en tanda",
    "goal_shootout_decisive": "penal decisivo convertido en tanda",
    "assist": "asistencia",
    "corner_assist": "asistencia de corner",
    "stats": "estadisticas",
    "key_pass": "oportunidad creada",
}
COMPETITION_NAMES_ES = {
    "World Cup": "Mundial",
    "FIFA World Cup 2026": "Mundial 2026",
}
TEAM_NAMES_ES = {
    "Algeria": "Argelia",
    "Argentina": "Argentina",
    "Australia": "Australia",
    "Austria": "Austria",
    "Belgium": "Bélgica",
    "Bosnia & Herzegovina": "Bosnia y Herzegovina",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Brazil": "Brasil",
    "Canada": "Canadá",
    "Cape Verde Islands": "Cabo Verde",
    "Cape Verde": "Cabo Verde",
    "Colombia": "Colombia",
    "Congo DR": "R.D. Congo",
    "Croatia": "Croacia",
    "Curaçao": "Curazao",
    "Curacao": "Curazao",
    "Czechia": "Chequia",
    "DR Congo": "R.D. Congo",
    "Ecuador": "Ecuador",
    "Egypt": "Egipto",
    "England": "Inglaterra",
    "France": "Francia",
    "Germany": "Alemania",
    "Ghana": "Ghana",
    "Haiti": "Haití",
    "Iran": "Irán",
    "Iraq": "Irak",
    "Ivory Coast": "Costa de Marfil",
    "Japan": "Japón",
    "Jordan": "Jordania",
    "Korea Republic": "Corea del Sur",
    "Mexico": "México",
    "Morocco": "Marruecos",
    "Netherlands": "Países Bajos",
    "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega",
    "Panama": "Panamá",
    "Paraguay": "Paraguay",
    "Portugal": "Portugal",
    "Qatar": "Catar",
    "Saudi Arabia": "Arabia Saudita",
    "Scotland": "Escocia",
    "Senegal": "Senegal",
    "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur",
    "Spain": "España",
    "Sweden": "Suecia",
    "Switzerland": "Suiza",
    "Tunisia": "Túnez",
    "Turkey": "Turquía",
    "Türkiye": "Turquía",
    "Uruguay": "Uruguay",
    "USA": "Estados Unidos",
    "United States": "Estados Unidos",
    "Uzbekistan": "Uzbekistán",
}


def _replace_full_terms(text: str, replacements: dict[str, str]) -> str:
    result = text
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\w){re.escape(source)}(?!\w)"
        result = re.sub(pattern, target, result)
    return result


class RankingExplanationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_evidence(
        self,
        request: RankingExplanationRequestDTO,
        ranked_players: list[RankedPlayerDTO],
    ) -> list[RankingExplanationEvidenceDTO]:
        if not ranked_players:
            return []

        comparison = self._comparison(ranked_players)
        evidence_items: list[RankingExplanationEvidenceDTO] = []
        for ranked in ranked_players:
            score_rows = await self._score_rows(ranked.player_id, request)
            top_events = await self._top_events(ranked.player_id, request)
            match_summaries = await self._match_summaries(ranked.player_id, request)
            stat_profile = await self._stat_profile(ranked.player_id, request)
            score_total = round(float(ranked.total_pts or 0), 2)
            achievement_bonus = round(
                sum(float(row.get("achievement_bonus_pts") or 0) for row in score_rows),
                2,
            )
            breakdown = self._merge_breakdown(score_rows)
            evidence = {
                "methodology": self._methodology_context(),
                "scope": {
                    "season": request.season,
                    "competition_id": request.competition_id,
                    "rules_version_id": request.rules_version_id,
                    "scope": request.scope,
                    "use_total": request.use_total,
                },
                "player": {
                    "id": ranked.player_id,
                    "name": ranked.player_name,
                    "team": self._localize_name(ranked.team_name),
                    "team_logo_url": ranked.team_logo_url,
                    "position": ranked.position,
                    "competition": self._localize_name(ranked.competition_name),
                    "rank": ranked.rank,
                    "total_pts": score_total,
                    "matches": int(ranked.matches_played or 0),
                    "goals": int(ranked.goals or 0),
                    "assists": int(ranked.assists or 0),
                    "dribbles_won": int(ranked.dribbles_won or 0),
                    "duels_won": int(ranked.duels_won or 0),
                    "b1_bonus_pts": round(float(ranked.b1_bonus_pts or 0), 2),
                    "b1_bonus_label": ranked.b1_bonus_label,
                    "achievement_bonus_pts": achievement_bonus,
                },
                "breakdown": breakdown,
                "score_rows": score_rows,
                "top_events": top_events,
                "match_summaries": match_summaries,
                "stat_profile": stat_profile,
                "comparison": comparison.get(ranked.player_id, {}),
            }
            evidence = self._localize_evidence(evidence)
            evidence["allowed_names"] = self._allowed_names(evidence)
            source_hash = self._source_hash(evidence)
            evidence_items.append(
                RankingExplanationEvidenceDTO(
                    player_id=ranked.player_id,
                    season=request.season,
                    competition_id=request.competition_id,
                    rules_version_id=request.rules_version_id,
                    scope=request.scope,
                    rank=ranked.rank,
                    source_hash=source_hash,
                    evidence=evidence,
                )
            )
        return evidence_items

    async def get_cached_for_scope(
        self,
        request: RankingExplanationRequestDTO,
    ) -> list[RankingPlayerExplanationDTO]:
        stmt = (
            select(RankingPlayerExplanation)
            .where(
                RankingPlayerExplanation.season == request.season,
                RankingPlayerExplanation.scope == request.scope,
                RankingPlayerExplanation.status.in_(PUBLIC_STATUSES),
            )
            .order_by(RankingPlayerExplanation.rank.asc())
            .limit(request.limit)
        )
        stmt = self._apply_scope_filters(stmt, request)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_dto(row) for row in rows]

    async def get_cached_for_player(
        self,
        player_id: int,
        request: RankingExplanationRequestDTO,
    ) -> RankingPlayerExplanationDTO | None:
        stmt = select(RankingPlayerExplanation).where(
            RankingPlayerExplanation.player_id == player_id,
            RankingPlayerExplanation.season == request.season,
            RankingPlayerExplanation.scope == request.scope,
            RankingPlayerExplanation.status.in_(PUBLIC_STATUSES),
        )
        stmt = self._apply_scope_filters(stmt, request)
        row = (await self._session.execute(stmt)).scalars().first()
        return self._to_dto(row) if row else None

    async def get_source_hash(
        self,
        player_id: int,
        request: RankingExplanationRequestDTO,
    ) -> str | None:
        stmt = select(RankingPlayerExplanation.source_hash).where(
            RankingPlayerExplanation.player_id == player_id,
            RankingPlayerExplanation.season == request.season,
            RankingPlayerExplanation.scope == request.scope,
        )
        stmt = self._apply_scope_filters(stmt, request)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_explanation(
        self,
        evidence: RankingExplanationEvidenceDTO,
        result: RankingExplanationWriteResultDTO,
        prompt_version: str,
    ) -> None:
        values = {
            "player_id": evidence.player_id,
            "season": evidence.season,
            "competition_id": evidence.competition_id,
            "rules_version_id": evidence.rules_version_id,
            "scope": evidence.scope,
            "rank": evidence.rank,
            "variant": result.variant,
            "status": result.status,
            "short_text": result.short_text[:280],
            "long_text": result.long_text[:1800],
            "bullets": result.bullets,
            "evidence_json": evidence.evidence,
            "model_name": result.model_name,
            "prompt_version": prompt_version,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_estimate_usd": result.cost_estimate_usd,
            "source_hash": evidence.source_hash,
            "generated_at": datetime.now(timezone.utc),
            "error": result.error,
        }
        stmt = insert(RankingPlayerExplanation).values(**values)
        update_values = {
            getattr(RankingPlayerExplanation, key): getattr(stmt.excluded, key)
            for key in values
            if key not in {"player_id"}
        }
        if evidence.competition_id is None:
            stmt = stmt.on_conflict_do_update(
                index_elements=["player_id", "season", "rules_version_id", "scope"],
                index_where=RankingPlayerExplanation.competition_id.is_(None),
                set_=update_values,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=["player_id", "season", "competition_id", "rules_version_id", "scope"],
                index_where=RankingPlayerExplanation.competition_id.is_not(None),
                set_=update_values,
            )
        await self._session.execute(stmt)

    async def mark_stale_for_scope(
        self,
        request: RankingExplanationRequestDTO,
        fresh_hashes: dict[int, str],
    ) -> int:
        scope_conditions = [
            RankingPlayerExplanation.season == request.season,
            RankingPlayerExplanation.scope == request.scope,
            RankingPlayerExplanation.status.in_(PUBLIC_STATUSES),
        ]
        if request.competition_id is None:
            scope_conditions.append(RankingPlayerExplanation.competition_id.is_(None))
        else:
            scope_conditions.append(RankingPlayerExplanation.competition_id == request.competition_id)
        if request.rules_version_id is None:
            scope_conditions.append(RankingPlayerExplanation.rules_version_id.is_(None))
        else:
            scope_conditions.append(RankingPlayerExplanation.rules_version_id == request.rules_version_id)

        updated = 0
        current_player_ids = list(fresh_hashes)
        removed_stmt = update(RankingPlayerExplanation).where(*scope_conditions)
        if current_player_ids:
            removed_stmt = removed_stmt.where(
                RankingPlayerExplanation.player_id.not_in(current_player_ids)
            )
        result = await self._session.execute(removed_stmt.values(status="stale"))
        updated += int(result.rowcount or 0)

        for player_id, source_hash in fresh_hashes.items():
            stmt = (
                update(RankingPlayerExplanation)
                .where(*scope_conditions)
                .where(RankingPlayerExplanation.player_id == player_id)
                .where(RankingPlayerExplanation.source_hash != source_hash)
                .values(status="stale")
            )
            result = await self._session.execute(stmt)
            updated += int(result.rowcount or 0)
        return updated

    async def _score_rows(self, player_id: int, request: RankingExplanationRequestDTO) -> list[dict[str, Any]]:
        stmt = (
            select(
                SFASeasonScore.competition_id,
                Competition.name.label("competition"),
                Team.name.label("team"),
                SFASeasonScore.total_pts,
                SFASeasonScore.achievement_bonus_pts,
                SFASeasonScore.matches_played,
                SFASeasonScore.breakdown,
            )
            .join(Competition, Competition.id == SFASeasonScore.competition_id)
            .outerjoin(Team, Team.id == SFASeasonScore.team_id)
            .where(
                SFASeasonScore.player_id == player_id,
                SFASeasonScore.season == request.season,
            )
        )
        stmt = self._apply_score_scope(stmt, request)
        rows = (await self._session.execute(stmt)).mappings().all()
        return [self._clean(self._localize_evidence(dict(row))) for row in rows]

    async def _stat_profile(self, player_id: int, request: RankingExplanationRequestDTO) -> dict[str, Any]:
        stmt = (
            select(
                func.coalesce(func.sum(PlayerStats.minutes), 0).label("minutes"),
                func.count(PlayerStats.fixture_id.distinct()).label("matches"),
                func.coalesce(func.sum(PlayerStats.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStats.assists), 0).label("assists"),
                func.coalesce(func.sum(PlayerStats.corner_assists), 0).label("corner_assists"),
                func.coalesce(func.sum(PlayerStats.shots_on), 0).label("shots_on"),
                func.coalesce(func.sum(PlayerStats.shots_total), 0).label("shots_total"),
                func.coalesce(func.sum(PlayerStats.passes_key), 0).label("passes_key"),
                func.coalesce(func.sum(PlayerStats.passes_total), 0).label("passes_total"),
                func.coalesce(func.sum(PlayerStats.passes_completed), 0).label("passes_completed"),
                func.coalesce(func.sum(PlayerStats.dribbles_won), 0).label("dribbles_won"),
                func.coalesce(func.sum(PlayerStats.dribbles_attempts), 0).label("dribbles_attempts"),
                func.coalesce(func.sum(PlayerStats.duels_won), 0).label("duels_won"),
                func.coalesce(func.sum(PlayerStats.duels_total), 0).label("duels_total"),
                func.coalesce(func.sum(PlayerStats.tackles_won), 0).label("tackles_won"),
                func.coalesce(func.sum(PlayerStats.interceptions), 0).label("interceptions"),
                func.coalesce(func.sum(PlayerStats.blocks), 0).label("blocks"),
                func.avg(PlayerStats.rating).label("rating_avg"),
            )
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(
                PlayerStats.player_id == player_id,
                PlayerStats.season == request.season,
            )
        )
        if request.competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == request.competition_id)
        row = (await self._session.execute(stmt)).mappings().first()
        if not row:
            return {}

        data = dict(row)
        shots_total = int(data.get("shots_total") or 0)
        shots_on = int(data.get("shots_on") or 0)
        goals = int(data.get("goals") or 0)
        passes_total = int(data.get("passes_total") or 0)
        passes_completed = round(float(data.get("passes_completed") or 0), 2)
        passes_accuracy = (
            round(passes_completed * 100 / passes_total, 2)
            if passes_total
            else None
        )
        dribbles_attempts = int(data.get("dribbles_attempts") or 0)
        dribbles_won = int(data.get("dribbles_won") or 0)
        duels_total = int(data.get("duels_total") or 0)
        duels_won = int(data.get("duels_won") or 0)
        defensive_actions = (
            int(data.get("tackles_won") or 0)
            + int(data.get("interceptions") or 0)
            + int(data.get("blocks") or 0)
        )
        offensive_contributions = (
            goals
            + int(data.get("assists") or 0)
            + int(data.get("corner_assists") or 0)
        )
        profile = {
            "minutes": int(data.get("minutes") or 0),
            "matches": int(data.get("matches") or 0),
            "goals": goals,
            "assists": int(data.get("assists") or 0),
            "corner_assists": int(data.get("corner_assists") or 0),
            "offensive_contributions": offensive_contributions,
            "shots_on": shots_on,
            "shots_total": shots_total,
            "shot_accuracy_pct": round((shots_on / shots_total) * 100, 2) if shots_total else None,
            "goal_conversion_pct": round((goals / shots_total) * 100, 2) if shots_total else None,
            "passes_key": int(data.get("passes_key") or 0),
            "passes_total": passes_total,
            "passes_accuracy_avg": passes_accuracy,
            "estimated_completed_passes": passes_completed,
            "dribbles_won": dribbles_won,
            "dribbles_attempts": dribbles_attempts,
            "dribble_success_pct": (
                round((dribbles_won / dribbles_attempts) * 100, 2)
                if dribbles_attempts
                else None
            ),
            "duels_won": duels_won,
            "duels_total": duels_total,
            "duel_win_pct": round((duels_won / duels_total) * 100, 2) if duels_total else None,
            "tackles_won": int(data.get("tackles_won") or 0),
            "interceptions": int(data.get("interceptions") or 0),
            "blocks": int(data.get("blocks") or 0),
            "defensive_actions": defensive_actions,
            "rating_avg": round(float(data["rating_avg"]), 2) if data.get("rating_avg") is not None else None,
        }
        return self._clean(profile)

    async def _top_events(self, player_id: int, request: RankingExplanationRequestDTO) -> list[dict[str, Any]]:
        home = aliased(Team)
        away = aliased(Team)
        stmt = (
            select(
                PlayerEventScore.final_points,
                PlayerEventScore.action_type,
                PlayerEventScore.base_points,
                PlayerEventScore.m1,
                PlayerEventScore.m2,
                PlayerEventScore.m3,
                PlayerEventScore.m4,
                PlayerEventScore.mvisit,
                PlayerEvent.minute,
                PlayerEvent.score_before,
                PlayerEvent.score_diff,
                Fixture.external_id.label("fixture_external_id"),
                Fixture.stage,
                Fixture.played_at,
                home.name.label("home_team"),
                away.name.label("away_team"),
            )
            .join(PlayerEvent, PlayerEvent.id == PlayerEventScore.event_id)
            .join(Fixture, Fixture.id == PlayerEventScore.fixture_id)
            .join(home, home.id == Fixture.home_team_id)
            .join(away, away.id == Fixture.away_team_id)
            .where(
                PlayerEventScore.player_id == player_id,
                PlayerEventScore.season == request.season,
            )
            .order_by(PlayerEventScore.final_points.desc())
            .limit(5)
        )
        if request.competition_id is not None:
            stmt = stmt.where(PlayerEventScore.competition_id == request.competition_id)
        if request.rules_version_id is not None:
            stmt = stmt.where(PlayerEventScore.rules_version_id == request.rules_version_id)
        rows = (await self._session.execute(stmt)).mappings().all()
        return [self._enrich_event_context(self._localize_evidence(dict(row))) for row in rows]

    async def _match_summaries(self, player_id: int, request: RankingExplanationRequestDTO) -> list[dict[str, Any]]:
        home = aliased(Team)
        away = aliased(Team)
        stmt = (
            select(
                Fixture.id.label("fixture_id"),
                Fixture.external_id.label("fixture_external_id"),
                Fixture.stage,
                Fixture.played_at,
                home.name.label("home_team"),
                away.name.label("away_team"),
                PlayerEvent.event_type,
                PlayerEvent.minute,
                PlayerEvent.score_before,
                PlayerEvent.score_diff,
                PlayerEventScore.action_type,
                PlayerEventScore.final_points,
                PlayerEventScore.base_points,
                PlayerEventScore.m1,
                PlayerEventScore.m2,
                PlayerEventScore.m3,
                PlayerEventScore.m4,
                PlayerEventScore.mvisit,
            )
            .join(PlayerEvent, PlayerEvent.id == PlayerEventScore.event_id)
            .join(Fixture, Fixture.id == PlayerEventScore.fixture_id)
            .join(home, home.id == Fixture.home_team_id)
            .join(away, away.id == Fixture.away_team_id)
            .where(
                PlayerEventScore.player_id == player_id,
                PlayerEventScore.season == request.season,
            )
            .order_by(Fixture.played_at.asc(), PlayerEvent.minute.asc())
        )
        if request.competition_id is not None:
            stmt = stmt.where(PlayerEventScore.competition_id == request.competition_id)
        if request.rules_version_id is not None:
            stmt = stmt.where(PlayerEventScore.rules_version_id == request.rules_version_id)

        rows = (await self._session.execute(stmt)).mappings().all()
        by_fixture: dict[int, dict[str, Any]] = {}
        goal_types = {EventType.GOAL, EventType.GOAL_PENALTY}
        assist_types = {EventType.ASSIST, EventType.CORNER_ASSIST}
        for row in rows:
            fixture_id = int(row["fixture_id"])
            item = by_fixture.setdefault(
                fixture_id,
                {
                    "fixture_external_id": row["fixture_external_id"],
                    "stage": row["stage"],
                    "stage_label": self._stage_label(row["stage"]),
                    "played_at": row["played_at"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "goals": 0,
                    "assists": 0,
                    "total_points": 0.0,
                    "top_action": None,
                    "impact_minutes": [],
                },
            )
            event_type = row["event_type"]
            final_points = round(float(row["final_points"] or 0), 2)
            item["total_points"] = round(float(item["total_points"]) + final_points, 2)
            if event_type in goal_types:
                item["goals"] += 1
            elif event_type in assist_types:
                item["assists"] += 1
            if final_points > float((item["top_action"] or {}).get("points") or 0):
                item["top_action"] = {
                    "type": row["action_type"],
                    "label": self._action_label(row["action_type"]),
                    "minute": row["minute"],
                    "score_before": row["score_before"],
                    "score_context": self._score_context(row["score_diff"]),
                    "points": final_points,
                    "base_points": row["base_points"],
                    "m1": row["m1"],
                    "m2": row["m2"],
                    "m3": row["m3"],
                    "m4": row["m4"],
                    "mvisit": row["mvisit"],
                    "m1_context": self._m1_context(row["m1"]),
                    "m3_context": self._m3_context(row["m3"]),
                    "m4_context": self._m4_context(row["m4"]),
                }
            if event_type in goal_types or event_type in assist_types:
                item["impact_minutes"].append(
                    {
                        "type": row["action_type"],
                        "label": self._action_label(row["action_type"]),
                        "minute": row["minute"],
                        "score_before": row["score_before"],
                        "score_context": self._score_context(row["score_diff"]),
                        "points": final_points,
                    }
                )

        summaries = list(by_fixture.values())
        summaries.sort(key=lambda item: float(item.get("total_points") or 0), reverse=True)
        return [self._clean(self._localize_evidence(item)) for item in summaries[:6]]

    def _methodology_context(self) -> dict[str, Any]:
        return {
            "product_thesis": (
                "SFA valora cuanto pesan las acciones de un futbolista dentro del partido."
            ),
            "principles": [
                "Una accion pesa mas si cambia o abre el marcador, llega con tension o aparece en minutos sensibles.",
                "El rendimiento sostenido partido a partido es mas fuerte que una sola noche aislada.",
                "La dificultad del rival puede restar o elevar el valor de una accion.",
                "La fase importa: no vale igual aparecer en grupos que en una ronda de eliminacion.",
                "El recorrido del equipo y los perfiles especiales, como veterano o promesa, son contexto adicional.",
                "El bonus de perfil no debe presentarse como la unica razon si el rendimiento base ya es alto.",
                "Una participacion de gol vale distinto segun la posicion: en defensas y laterales es mas rara.",
                "La eficiencia tambien importa: precision de pase, tiros a puerta, conversion, duelos y regates.",
            ],
            "multiplier_glossary": {
                "m1": "dificultad del rival; menor que 1 castiga si el rival era inferior, mayor que 1 premia rival fuerte",
                "m2": "importancia de la fase o torneo",
                "m3": "contexto del marcador; sube si la accion llega con tension o cambia el partido",
                "m4": "dificultad tecnica de la accion; sube si la definicion o jugada fue mas compleja",
                "mvisit": "bono por jugar fuera cuando aplica",
            },
            "language_rules": [
                "Escribe todo en espanol.",
                "Usa Mundial en lugar de World Cup.",
                "Usa los nombres localizados del JSON; no traduzcas de vuelta al ingles.",
                "No menciones equipos o rivales que no aparezcan en allowed_names.",
                "Usa dieciseisavos, octavos, cuartos, semifinal o final cuando corresponda.",
                "No uses palabras como scope, ranking peers, knockout, score, stage o bonus label.",
                "No repitas que SFA no mide minutos; explica por que las acciones del jugador fueron relevantes.",
            ],
            "positional_lens": {
                "DC": (
                    "central: recalca aportes de gol/asistencia si aparecen, "
                    "porque son diferenciales para un defensor"
                ),
                "LAT": "lateral: valora ida y vuelta, oportunidades creadas, asistencias, duelos y acciones defensivas",
                "GK": "arquero: prioriza atajadas, goles evitados, seguridad y contexto defensivo",
                "MC": "mediocampista: valora control, precision de pase, duelos, oportunidades creadas y ritmo del partido",
                "MCO": (
                    "mediapunta: valora creatividad, oportunidades creadas, asistencias "
                    "y llegada al area"
                ),
                "EXT": "extremo: valora regates, goles, asistencias, tiros a puerta y desequilibrio",
                "DEL": (
                    "delantero: valora goles, conversion, tiros a puerta "
                    "y aparicion en momentos decisivos"
                ),
            },
        }

    def _enrich_event_context(self, row: dict[str, Any]) -> dict[str, Any]:
        row["action_label"] = self._action_label(row.get("action_type"))
        row["stage_label"] = self._stage_label(row.get("stage"))
        row["score_context"] = self._score_context(row.get("score_diff"))
        row["m1_context"] = self._m1_context(row.get("m1"))
        row["m3_context"] = self._m3_context(row.get("m3"))
        row["m4_context"] = self._m4_context(row.get("m4"))
        return self._clean(row)

    def _localize_name(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if value in TEAM_NAMES_ES:
            return TEAM_NAMES_ES[value]
        if value in COMPETITION_NAMES_ES:
            return COMPETITION_NAMES_ES[value]
        return value

    def _localize_text(self, value: str) -> str:
        replacements = {**COMPETITION_NAMES_ES, **TEAM_NAMES_ES}
        return _replace_full_terms(value, replacements)

    def _localize_evidence(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._localize_evidence(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._localize_evidence(item) for item in value]
        if isinstance(value, str):
            return self._localize_text(value)
        return value

    def _allowed_names(self, evidence: dict[str, Any]) -> list[str]:
        names: set[str] = set()
        player = evidence.get("player") or {}
        for key in ("name", "team", "competition"):
            value = player.get(key)
            if isinstance(value, str) and value:
                names.add(value)
        for event in evidence.get("top_events") or []:
            if isinstance(event, dict):
                for key in ("home_team", "away_team"):
                    value = event.get(key)
                    if isinstance(value, str) and value:
                        names.add(value)
        for match in evidence.get("match_summaries") or []:
            if isinstance(match, dict):
                for key in ("home_team", "away_team"):
                    value = match.get(key)
                    if isinstance(value, str) and value:
                        names.add(value)
        return sorted(names)

    def _action_label(self, action_type: Any) -> str:
        return ACTION_LABELS_ES.get(str(action_type or ""), str(action_type or "accion"))

    def _stage_label(self, stage: Any) -> str:
        return STAGE_LABELS_ES.get(str(stage or ""), str(stage or "fase").replace("_", " "))

    def _score_context(self, score_diff: Any) -> str:
        if score_diff is None:
            return "contexto de marcador no disponible"
        diff = int(score_diff)
        if diff < 0:
            return f"su equipo iba perdiendo por {abs(diff)}"
        if diff == 0:
            return "el partido estaba empatado"
        return f"su equipo ganaba por {diff}"

    def _m1_context(self, value: Any) -> str:
        if value is None:
            return "dificultad de rival no disponible"
        m1 = float(value)
        if m1 < 0.9:
            return "el rival era inferior y el multiplicador castigo la accion"
        if m1 > 1.1:
            return "el rival era fuerte y el multiplicador premio la accion"
        return "dificultad de rival neutra"

    def _m3_context(self, value: Any) -> str:
        if value is None:
            return "contexto de momento no disponible"
        m3 = float(value)
        if m3 > 1.1:
            return "momento de alta tension o impacto en el marcador"
        if m3 < 0.95:
            return "momento de menor tension"
        return "momento de valor normal"

    def _m4_context(self, value: Any) -> str:
        if value is None:
            return "dificultad tecnica no disponible"
        m4 = float(value)
        if m4 > 1.2:
            return "accion de dificultad tecnica alta"
        if m4 > 1.05:
            return "accion de dificultad tecnica media"
        return "accion de dificultad tecnica normal"

    def _apply_scope_filters(self, stmt: Any, request: RankingExplanationRequestDTO) -> Any:
        if request.competition_id is None:
            stmt = stmt.where(RankingPlayerExplanation.competition_id.is_(None))
        else:
            stmt = stmt.where(RankingPlayerExplanation.competition_id == request.competition_id)
        if request.rules_version_id is not None:
            stmt = stmt.where(RankingPlayerExplanation.rules_version_id == request.rules_version_id)
        return stmt

    def _apply_score_scope(self, stmt: Any, request: RankingExplanationRequestDTO) -> Any:
        if request.competition_id is not None:
            stmt = stmt.where(SFASeasonScore.competition_id == request.competition_id)
        if request.rules_version_id is None:
            stmt = stmt.where(SFASeasonScore.rules_version_id.is_(None))
        else:
            stmt = stmt.where(SFASeasonScore.rules_version_id == request.rules_version_id)
        return stmt

    def _to_dto(self, row: RankingPlayerExplanation) -> RankingPlayerExplanationDTO:
        evidence = row.evidence_json or {}
        player = evidence.get("player", {})
        return RankingPlayerExplanationDTO(
            id=row.id,
            player_id=row.player_id,
            player_name=player.get("name"),
            team_name=player.get("team"),
            team_logo_url=player.get("team_logo_url"),
            season=row.season,
            competition_id=row.competition_id,
            rules_version_id=row.rules_version_id,
            scope=row.scope,
            rank=row.rank,
            variant=row.variant,
            status=row.status,
            short_text=row.short_text,
            long_text=row.long_text,
            bullets=list(row.bullets or []),
            evidence=evidence,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            generated_at=row.generated_at,
        )

    def _merge_breakdown(self, score_rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
        merged: dict[str, dict[str, float | int]] = {}
        for row in score_rows:
            breakdown = row.get("breakdown") or {}
            for action, data in breakdown.items():
                slot = merged.setdefault(action, {"count": 0, "pts": 0.0})
                slot["count"] = int(slot["count"]) + int(data.get("count") or 0)
                slot["pts"] = round(float(slot["pts"]) + float(data.get("pts") or 0), 2)
        return merged

    def _comparison(self, ranked_players: list[RankedPlayerDTO]) -> dict[int, dict[str, Any]]:
        if not ranked_players:
            return {}
        leader_pts = float(ranked_players[0].total_pts or 0)
        peers = [
            {
                "rank": player.rank,
                "name": player.player_name,
                "matches": int(player.matches_played or 0),
                "total_pts": round(float(player.total_pts or 0), 2),
                "points_per_match": round(
                    float(player.total_pts or 0) / max(int(player.matches_played or 0), 1),
                    2,
                ),
            }
            for player in ranked_players[:10]
        ]
        best_ppg = max(peers, key=lambda item: float(item["points_per_match"]))
        return {
            player.player_id: {
                "gap_to_leader": round(leader_pts - float(player.total_pts or 0), 2),
                "points_per_match": round(
                    float(player.total_pts or 0) / max(int(player.matches_played or 0), 1),
                    2,
                ),
                "top_10_size": len(ranked_players),
                "top_peers": peers,
                "best_points_per_match": best_ppg,
                "players_with_more_matches_ahead_or_near": [
                    peer
                    for peer in peers
                    if int(peer["matches"]) > int(player.matches_played or 0)
                    and int(peer["rank"]) > int(player.rank or 0)
                ][:4],
            }
            for player in ranked_players
        }

    def _source_hash(self, evidence: dict[str, Any]) -> str:
        payload = json.dumps(
            self._clean(evidence),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _clean(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): self._clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._clean(v) for v in value]
        return value
