# Team ranking football enrichment

## Business context

Expose actual last-five results and the highest total individual SFA player for the
approved football-first Teams UI through the existing ranking endpoint.

## Constraints

- Backend only. No scoring, normalization, trends, DB writes, migrations, deployment, commit or SSH.
- Reuse existing verified last-ten team-match appearances and selected scoring rules version.
- No new entities, providers, DI factories or endpoints.

## Decisions

| Decision | Rejected alternative | Reason |
|---|---|---|
| One page-team batch query after pagination | Full population form or N+1 | At most 50 teams and 250 result rows |
| Requested physical season only | Previous-season display fallback | Form and featured player must not imply current evidence |
| PlayerStats team attribution | Catalog Player.team_id | Transfers retain actual appearance attribution |
| Existing total individual_points, tie by lowest player ID | SFA/90 or normalized merit | Featured player is greatest aggregate individual SFA |
| Null outcome for incomplete scores or level PEN | Inventing a shootout winner | Fixture stores no penalty evidence |

## Exact contract

`RankedTeamDTO.recent_results: tuple[TeamRankingMatchDTO, ...] = ()` serializes to an array.
Each match has `fixture_external_id: int`, `played_at: datetime`, `opponent_name: str`,
`opponent_logo_url: str | None`, `is_home: bool`, `goals_for: int | None`,
`goals_against: int | None`, `outcome: Literal['W', 'D', 'L'] | None`, `status: str`.
Use the last five FT/AET/PEN fixtures at or before the request timestamp, within
the requested season and participant kind. Return oldest first, breaking timestamp
ties by fixture internal ID. Missing scores occupy a slot with unknown outcome;
no padding, future/live fixtures or historical fallback. Level PEN is unknown;
FT/AET level scores are draws. Goals and home/away are team-relative.
PEN W/L describes only the stored pre-shootout score, never the shootout winner.
Frontend labeling policy: explicitly identify results before penalties; for level
PEN show shootout unavailable/unknown rather than a win or loss.
Frontend owner confirmed the neutral label: "Ganador por penaltis no disponible".

`RankedTeamDTO.featured_player: TeamRankingFeaturedPlayerDTO | None = None` has
`id: int`, `name: str`, `photo_url: str | None`, `individual_points: float`,
`appearances: int`, `season: str`. Select only requested-season players with
non-null individual_points, positive scored minutes and scored appearances;
appearances means scored verified appearances within the last ten completed team
matches. Zero and negative totals are eligible. No rounding or historical fallback.
`TeamRankingPlayerDTO` adds trailing `name: str = ''` and `photo_url: str | None = None`.

## External integrations

None. Images use existing catalog photo URLs and API-Sports team-logo URL convention.

## Read-only capture follow-up

The user subsequently requested VPS capture after local tests using temporary code mounts.
This permits isolated SSH/read-only integration only, not deployment, restarting production
services, modifying production source or DB writes. `--fixture-json` aliases `--response-json`.
The frontend owner subsequently took ownership of SCP and isolated container execution;
this session does not execute the read-only script against production.

## Integration result (reported by frontend owner)

The user reported successful read-only integration using the isolated temporary-mount
workflow after local verification. All enrichment checks passed:

- First page: five queries, total response 2.724s, page form query 0.018s.
- Second page: total response 2.520s, page form query 0.011s.
- Population: 751 club teams and 48 national teams.
- Observed scored-data cutoff: September 20, as reported by the user. This is source
  evidence, not a fixed expected timestamp or a claim of current ingestion/ELO freshness.
- Both measured pages are within the configured default response/form budgets of 30s/5s.

No deployment, migrations, scoring changes or commit. The frontend remains a local design preview.
This session records the user's integration report; it did not execute or independently
re-run the VPS capture.
