from __future__ import annotations

import hashlib
import json
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
from sfa.infrastructure.models import Competition, Fixture, Player, PlayerEvent, PlayerEventScore, SFASeasonScore, Team
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
    "key_pass": "pase clave",
}


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
                    "team": ranked.team_name,
                    "team_logo_url": ranked.team_logo_url,
                    "position": ranked.position,
                    "competition": ranked.competition_name,
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
                "comparison": comparison.get(ranked.player_id, {}),
            }
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
        update_values = {key: getattr(stmt.excluded, key) for key in values if key not in {"player_id"}}
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
        if not fresh_hashes:
            return 0
        stale_conditions = [
            RankingPlayerExplanation.player_id.in_(list(fresh_hashes)),
            RankingPlayerExplanation.season == request.season,
            RankingPlayerExplanation.scope == request.scope,
            RankingPlayerExplanation.status.in_(PUBLIC_STATUSES),
        ]
        if request.competition_id is None:
            stale_conditions.append(RankingPlayerExplanation.competition_id.is_(None))
        else:
            stale_conditions.append(RankingPlayerExplanation.competition_id == request.competition_id)
        if request.rules_version_id is None:
            stale_conditions.append(RankingPlayerExplanation.rules_version_id.is_(None))
        else:
            stale_conditions.append(RankingPlayerExplanation.rules_version_id == request.rules_version_id)

        updated = 0
        for player_id, source_hash in fresh_hashes.items():
            stmt = (
                update(RankingPlayerExplanation)
                .where(*stale_conditions)
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
        return [self._clean(dict(row)) for row in rows]

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
        return [self._enrich_event_context(dict(row)) for row in rows]

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
                    "mvisit": row["mvisit"],
                    "m1_context": self._m1_context(row["m1"]),
                    "m3_context": self._m3_context(row["m3"]),
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
        return [self._clean(item) for item in summaries[:6]]

    def _methodology_context(self) -> dict[str, Any]:
        return {
            "product_thesis": (
                "SFA no mide solo cuanto juega un futbolista; mide cuanto pesa cuando juega."
            ),
            "principles": [
                "El volumen de partidos suma, pero la eficiencia por partido puede explicar un liderato.",
                "Los goles y asistencias pesan mas cuando llegan con el partido abierto o en momentos clave.",
                "La dificultad del rival puede restar o elevar el valor de una accion.",
                "El recorrido del equipo y los perfiles especiales, como veterano o promesa, son contexto adicional.",
                "El bonus de perfil no debe presentarse como la unica razon si el rendimiento base ya es alto.",
            ],
            "multiplier_glossary": {
                "m1": "dificultad del rival; menor que 1 castiga si el rival era inferior, mayor que 1 premia rival fuerte",
                "m2": "importancia de la fase o torneo",
                "m3": "contexto del marcador; sube si la accion llega con tension o cambia el partido",
                "mvisit": "bono por jugar fuera cuando aplica",
            },
            "language_rules": [
                "Escribe todo en espanol.",
                "Usa Mundial en lugar de World Cup.",
                "Usa dieciseisavos, octavos, cuartos, semifinal o final cuando corresponda.",
                "No uses palabras como scope, ranking peers, knockout, score, stage o bonus label.",
            ],
        }

    def _enrich_event_context(self, row: dict[str, Any]) -> dict[str, Any]:
        row["action_label"] = self._action_label(row.get("action_type"))
        row["stage_label"] = self._stage_label(row.get("stage"))
        row["score_context"] = self._score_context(row.get("score_diff"))
        row["m1_context"] = self._m1_context(row.get("m1"))
        row["m3_context"] = self._m3_context(row.get("m3"))
        return self._clean(row)

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
