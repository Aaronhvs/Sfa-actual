from __future__ import annotations

from sqlalchemy import text

from sfa.domain.event_integrity import digest
from sfa.domain.event_integrity_ports import IntegrityPublicationSnapshot, SeasonIntegrityPublicationRepositoryPort
from sfa.infrastructure.repositories.season_repository import SeasonRepository

BEFORE = "integrity_before_2025"
AFTER = "integrity_after_2025"
PUBLISHED = "integrity_published_2025"
TABLES = (
    "fixtures",
    "player_events",
    "player_stats",
    "player_event_scores",
    "sfa_season_scores",
    "player_achievement_bonuses",
    "individual_honors",
)
DEPENDENCIES = (
    "fixture_team_strengths",
    "competition_achievements",
    "scoring_rules_versions",
    "players",
    "competition_stages",
    "player_position_assignments",
    "position_scope_classifications",
    "position_correction_batches",
)
KEYS = {
    "player_event_scores": ("event_id", "rules_version_id"),
    "sfa_season_scores": ("player_id", "competition_id", "season", "rules_version_id"),
    "player_achievement_bonuses": ("player_id", "achievement_id", "rules_version_id"),
    "individual_honors": ("scope_key", "context_key", "honor_type", "rules_version_id"),
}


class SeasonIntegrityPublicationRepository(SeasonIntegrityPublicationRepositoryPort):
    """Fixed, private staging schemas. No scoring, provider requests or implicit cascades."""

    def __init__(self, session) -> None:
        self._session = session
        self._parameters = {}
        self._pairs = "FALSE"

    async def lock(self) -> None:
        # PositionAwareSession must receive the exclusive intent before its first SQL.
        self._session.info["position_publication_exclusive"] = True
        acquired = await self._session.scalar(text("SELECT pg_try_advisory_xact_lock(736615320261019)"))
        if not acquired:
            raise ValueError("Publication busy; roll back and retry a fresh transaction")
        await self._session.execute(text("SET LOCAL lock_timeout='5s'"))
        scope = await SeasonRepository(self._session).resolve_scope("season-2025")
        if not scope:
            raise ValueError("Missing season-2025 scope")
        clauses = []
        for i, source in enumerate(scope.sources):
            self._parameters[f"s{i}"] = source.season
            self._parameters[f"c{i}"] = list(source.competition_ids)
            clauses.append(f"(season=:s{i} AND competition_id=ANY(:c{i}))")
        self._pairs = "(" + " OR ".join(clauses) + ")"

    def _condition(self, table):
        if table == "fixtures":
            return self._pairs
        if table in {"player_events", "player_stats", "fixture_team_strengths"}:
            return f"fixture_id IN(SELECT id FROM {BEFORE}.fixtures)"
        if table in {
            "player_event_scores",
            "sfa_season_scores",
            "player_achievement_bonuses",
            "competition_achievements",
        }:
            return self._pairs
        if table == "individual_honors":
            return "scope_key='season-2025'"
        if table in {"players", "player_position_assignments", "position_scope_classifications"}:
            field = "id" if table == "players" else "player_id"
            actors = " UNION ".join(
                f"SELECT player_id FROM {schema}.{source}"
                for schema in (BEFORE, AFTER)
                for source in ("player_events", "player_stats", "player_event_scores")
            )
            return f"{field} IN({actors})"
        if table == "competition_stages":
            return f"(competition_id,stage) IN(SELECT competition_id,stage FROM {BEFORE}.fixtures)"
        return "TRUE"

    async def _columns(self, table, *, generated=False):
        rows = await self._session.execute(
            text("""
            SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(:name)
              AND attnum>0 AND NOT attisdropped AND (:generated OR attgenerated='') ORDER BY attnum
        """),
            {"name": "public." + table, "generated": generated},
        )
        return tuple(rows.scalars())

    async def _equal(self, table, schema):
        columns = await self._columns(table, generated=True)
        # Frozen players deliberately omit mutable biography fields unrelated to scoring.
        if table == "players":
            columns = ("id", "external_id", "name", "position", "birth_date")
        fields = ",".join('"' + c + '"' for c in columns)
        count = await self._session.scalar(
            text(f"""
            SELECT count(*) FROM (
              (SELECT {fields} FROM public.{table} WHERE {self._condition(table)}
               EXCEPT ALL SELECT {fields} FROM {schema}.{table})
              UNION ALL
              (SELECT {fields} FROM {schema}.{table} EXCEPT ALL
               SELECT {fields} FROM public.{table} WHERE {self._condition(table)})
            ) differences
        """),
            self._parameters,
        )
        if count:
            raise ValueError(f"Integrity publication CAS failed for {table}: {count} different rows")

    async def _snapshot(self):
        values = []
        for table in (*TABLES, *DEPENDENCIES):
            row = (
                await self._session.execute(
                    text(f"""
                SELECT count(*) n,md5(coalesce(
                  string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) hash
                FROM public.{table} t WHERE {self._condition(table)}
            """),
                    self._parameters,
                )
            ).one()
            values.append((table, row.n, row.hash))
        return IntegrityPublicationSnapshot(digest(values), tuple((t, n) for t, n, _ in values))

    async def validate(self, reverting: bool):
        schema = PUBLISHED if reverting else BEFORE
        for table in (*TABLES, *DEPENDENCIES):
            await self._equal(table, schema)
        # No hidden references may be removed or silently cascaded during replacement.
        refs = list((await self._session.execute(text("""
            SELECT conrelid::regclass::text,confrelid::regclass::text FROM pg_constraint
            WHERE contype='f' AND confrelid IN('player_events'::regclass,'player_event_scores'::regclass,
              'sfa_season_scores'::regclass,'player_achievement_bonuses'::regclass,'individual_honors'::regclass)
        """))).all())
        if refs != [("player_event_scores", "player_events")]:
            raise ValueError(f"Unexpected projection references: {refs}")
        unexpected = await self._session.scalar(text(f"""
            SELECT count(*) FROM public.player_event_scores s JOIN public.player_events e ON e.id=s.event_id
            WHERE e.fixture_id IN(SELECT id FROM {BEFORE}.fixtures)
              AND NOT EXISTS(SELECT 1 FROM {schema}.player_event_scores x WHERE x.id=s.id)
        """))
        if unexpected:
            raise ValueError("Uninventoried scores reference target events; implicit cascade is forbidden")
        if not reverting:
            for table in DEPENDENCIES:
                columns = await self._columns(table, generated=True)
                if table == "players":
                    columns = ("id", "external_id", "name", "position", "birth_date")
                names = ",".join('"' + c + '"' for c in columns)
                differences = await self._session.scalar(text(f"""
                    SELECT count(*) FROM (
                      (SELECT {names} FROM {BEFORE}.{table} EXCEPT ALL SELECT {names} FROM {AFTER}.{table})
                      UNION ALL
                      (SELECT {names} FROM {AFTER}.{table} EXCEPT ALL SELECT {names} FROM {BEFORE}.{table})
                    ) d
                """))
                if differences:
                    raise ValueError(f"Prepared scoring dependencies changed: {table}")
            added = await self._session.scalar(text(f"""
                SELECT count(*) FROM {AFTER}.player_stats a LEFT JOIN {BEFORE}.player_stats b USING(id)
                WHERE b.id IS NULL
            """))
            if added:
                raise ValueError("New player appearances require a separately reviewed repair")
            for table in KEYS:
                count = await self._session.scalar(
                    text(f"SELECT count(*) FROM {AFTER}.{table} WHERE rules_version_id IS DISTINCT FROM 4")
                )
                if count:
                    raise ValueError("Only complete v4 may be promoted; archive v3 before serving")
            count = await self._session.scalar(text(f"""
                SELECT count(*) FROM {AFTER}.player_events e JOIN players p ON p.id=e.player_id
                WHERE p.position::text<>'GK' AND NOT EXISTS(
                  SELECT 1 FROM {AFTER}.player_event_scores s WHERE s.event_id=e.id AND s.rules_version_id=4)
            """))
            if count:
                raise ValueError(f"Prepared projection has {count} eligible unscored events")
            checks = {
                "score identity": f"""
                    SELECT count(*) FROM {AFTER}.player_event_scores s
                    LEFT JOIN {AFTER}.player_events e ON e.id=s.event_id
                    LEFT JOIN {AFTER}.fixtures f ON f.id=e.fixture_id
                    WHERE e.id IS NULL OR (s.player_id,s.fixture_id,s.season,s.competition_id)
                      IS DISTINCT FROM (e.player_id,e.fixture_id,f.season,f.competition_id)
                """,
                "season aggregate": f"""
                    SELECT count(*) FROM {AFTER}.sfa_season_scores s FULL JOIN(
                      SELECT player_id,competition_id,season,rules_version_id,sum(final_points) points,
                        count(DISTINCT fixture_id) matches FROM {AFTER}.player_event_scores
                      GROUP BY player_id,competition_id,season,rules_version_id
                    ) x USING(player_id,competition_id,season,rules_version_id)
                    WHERE s.id IS NULL OR s.total_pts<>coalesce(x.points,0)
                      OR s.matches_played<>coalesce(x.matches,0)
                """,
                "achievement aggregate": f"""
                    SELECT count(*) FROM {AFTER}.sfa_season_scores s FULL JOIN(
                      SELECT player_id,competition_id,season,rules_version_id,sum(final_bonus) bonus
                      FROM {AFTER}.player_achievement_bonuses
                      GROUP BY player_id,competition_id,season,rules_version_id
                    ) x USING(player_id,competition_id,season,rules_version_id)
                    LEFT JOIN public.players p ON p.id=coalesce(s.player_id,x.player_id)
                    WHERE (s.id IS NULL AND p.position::text<>'GK')
                      OR (s.id IS NOT NULL AND s.achievement_bonus_pts<>coalesce(x.bonus,0))
                """,
            }
            for label, sql in checks.items():
                if await self._session.scalar(text(sql)):
                    raise ValueError(f"Prepared projection failed {label} validation")
        return await self._snapshot()

    async def _prepare_expected(self, reverting):
        source = BEFORE if reverting else AFTER
        for table in TABLES:
            await self._session.execute(
                text(f"CREATE TEMP TABLE integrity_expected_{table} ON COMMIT DROP AS SELECT * FROM {source}.{table}")
            )
            await self._session.execute(text(f"CREATE INDEX ON integrity_expected_{table}(id)"))
        if reverting:
            await self._validate_expected_ids()
            return
        await self._session.execute(text(f"""
            CREATE TEMP TABLE integrity_event_map ON COMMIT DROP AS
            SELECT a.id clone_id,CASE WHEN b.id IS NOT NULL THEN a.id
              ELSE nextval(pg_get_serial_sequence('public.player_events','id'))::int END production_id
            FROM {AFTER}.player_events a LEFT JOIN {BEFORE}.player_events b USING(id)
        """))
        await self._session.execute(text("CREATE UNIQUE INDEX ON integrity_event_map(clone_id)"))
        await self._session.execute(text("""
            UPDATE integrity_expected_player_events a SET id=m.production_id
            FROM integrity_event_map m WHERE a.id=m.clone_id
        """))
        await self._session.execute(text("""
            UPDATE integrity_expected_player_event_scores a SET event_id=m.production_id
            FROM integrity_event_map m WHERE a.event_id=m.clone_id
        """))
        # Current calculation details contain no event references. Refuse new shapes rather than guessing.
        for table in KEYS:
            bad = (
                await self._session.scalar(text(f"""
                SELECT count(*) FROM integrity_expected_{table}
                WHERE to_jsonb(integrity_expected_{table})::text ~ '"(event_id|player_event_id|score_id)"'
            """))
                if table != "player_event_scores"
                else await self._session.scalar(text("""
                SELECT count(*) FROM integrity_expected_player_event_scores
                WHERE calculation_details::text ~ '"(event_id|player_event_id|score_id)"'
            """))
            )
            if bad:
                raise ValueError(f"Unmapped nested event references in {table}")
            join = " AND ".join(f"p.{k}=a.{k}" for k in KEYS[table])
            await self._session.execute(text(f"""
                UPDATE integrity_expected_{table} a SET id=coalesce(
                  (SELECT p.id FROM public.{table} p WHERE {join}),
                  nextval(pg_get_serial_sequence('public.{table}','id'))::int)
            """))
        await self._validate_expected_ids()

    async def _validate_expected_ids(self):
        for table in TABLES:
            await self._session.execute(text(f"CREATE UNIQUE INDEX ON integrity_expected_{table}(id)"))
            collision = await self._session.scalar(
                text(f"""
                SELECT count(*) FROM integrity_expected_{table} e WHERE EXISTS(
                  SELECT 1 FROM public.{table} p WHERE p.id=e.id AND NOT ({self._condition(table)}))
            """),
                self._parameters,
            )
            if collision:
                raise ValueError(f"Reserved IDs collide outside the publication scope: {table}")

    async def replace(self, reverting: bool):
        await self._prepare_expected(reverting)
        # Sanctioned 0065 publication protocol, scoped to this locked transaction.
        # The caller has already archived intent and validated the complete before cut.
        await self._session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        # Explicitly retire dependent scores first; PE deletions never rely on cascade.
        for table in (*KEYS, "player_events"):
            await self._session.execute(
                text(f"""
                DELETE FROM public.{table} p WHERE {self._condition(table)}
                  AND NOT EXISTS(SELECT 1 FROM integrity_expected_{table} e WHERE e.id=p.id)
            """),
                self._parameters,
            )
        for table in (
            "fixtures",
            "player_events",
            "player_stats",
            "player_event_scores",
            "player_achievement_bonuses",
            "individual_honors",
            "sfa_season_scores",
        ):
            columns = await self._columns(table)
            if table == "fixtures":
                update_columns = ("home_goals", "away_goals", "score_source")
            elif table == "player_stats":
                update_columns = ("goals", "assists", "minutes")
            else:
                update_columns = tuple(c for c in columns if c != "id")
            fields = ",".join('"' + c + '"' for c in columns)
            assignment = ",".join(f'"{c}"=e."{c}"' for c in update_columns)
            changed = " OR ".join(f'p."{c}" IS DISTINCT FROM e."{c}"' for c in update_columns)
            await self._session.execute(text(f"""
                UPDATE public.{table} p SET {assignment} FROM integrity_expected_{table} e
                WHERE p.id=e.id AND ({changed})
            """))
            if table not in {"fixtures", "player_stats"}:
                await self._session.execute(text(f"""
                    INSERT INTO public.{table}({fields}) SELECT {','.join('e."'+c+'"' for c in columns)}
                    FROM integrity_expected_{table} e WHERE NOT EXISTS(SELECT 1 FROM public.{table} p WHERE p.id=e.id)
                """))
        await self._session.execute(text("SELECT set_config('sfa.position_publication','off',true)"))
        # Store exact production IDs and rows in a durable private schema, in the same transaction.
        destination = "integrity_restored_2025" if reverting else PUBLISHED
        await self._session.execute(text(f"CREATE SCHEMA {destination}"))
        for table in (*TABLES, *DEPENDENCIES):
            await self._session.execute(
                text(f"""
                CREATE TABLE {destination}.{table} AS
                SELECT * FROM public.{table} WHERE {self._condition(table)}
            """),
                self._parameters,
            )
            if table in TABLES:
                differences = await self._session.scalar(text(f"""
                    SELECT count(*) FROM (
                      (SELECT to_jsonb(t) FROM {destination}.{table} t
                       EXCEPT ALL SELECT to_jsonb(t) FROM integrity_expected_{table} t)
                      UNION ALL (SELECT to_jsonb(t) FROM integrity_expected_{table} t
                       EXCEPT ALL SELECT to_jsonb(t) FROM {destination}.{table} t)
                    ) d
                """))
                if differences:
                    raise ValueError(f"Publication after verification failed: {table}: {differences}")
            else:
                await self._equal(table, BEFORE)
        if not reverting:
            await self._session.execute(
                text(f"CREATE TABLE {destination}.event_id_map AS SELECT * FROM integrity_event_map")
            )
        return await self._snapshot()
