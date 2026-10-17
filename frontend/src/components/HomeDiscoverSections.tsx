import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking, fetchTournamentDashboard } from '../api/client'
import type { RankedPlayer, SeasonItem, TournamentFixture, TournamentFixtureGroup } from '../types'
import { formatLocalDateShort, formatLocalTime, localDateKey } from '../utils/localTime'
import { isTournamentKnockout, LIVE_TOURNAMENT_STATUSES, tournamentCompetitionPriority, tournamentStageLabel, tournamentTeamLogo } from '../utils/tournaments'
import { TeamCrest } from './shared/FootballVisuals'
import './HomeDiscoverSections.css'

const POSITIONS = [
  { code: 'DEL', label: 'Delantero' }, { code: 'EXT', label: 'Extremo' },
  { code: 'MCO', label: 'Mediapunta' }, { code: 'MC', label: 'Centrocampista' },
  { code: 'LAT', label: 'Lateral' }, { code: 'DC', label: 'Defensa central' },
]

type PositionLeader = typeof POSITIONS[number] & { player: RankedPlayer | null; failed: boolean }
type FeaturedFixture = { fixture: TournamentFixture; competition: TournamentFixtureGroup['competition']; reason: string; priority: number }

async function loadPositionLeader(scope: string, position: string, signal: AbortSignal) {
  // The API applies contextual position overrides after pagination. A one-row
  // request can therefore be empty even though this position has scored players.
  let offset = 0
  const limit = 10
  while (!signal.aborted) {
    const result = await fetchRanking({ scope, position, limit, offset, signal })
    const player = result.ranking.find(item => item.position === position)
    if (player) return player
    offset += limit
    if (offset >= result.total) return null
  }
  return null
}

function normalize(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

function selectFixtures(groups: TournamentFixtureGroup[], players: RankedPlayer[]): FeaturedFixture[] {
  const now = Date.now()
  const teams = new Set(players.map((player) => normalize(player.team)))
  const seen = new Set<number>()
  const fixtures: FeaturedFixture[] = []
  for (const { competition, fixtures: matches } of groups) {
    for (const fixture of matches) {
      if (seen.has(fixture.external_id)) continue
      seen.add(fixture.external_id)
      const live = LIVE_TOURNAMENT_STATUSES.has(fixture.status)
      const upcoming = fixture.status === 'NS' && new Date(fixture.played_at).getTime() >= now
      if (!live && !upcoming) continue
      const topTeam = teams.has(normalize(fixture.home_team.name)) || teams.has(normalize(fixture.away_team.name))
      const knockout = isTournamentKnockout(fixture.stage)
      fixtures.push({
        fixture, competition,
        reason: topTeam ? 'Equipo del top 3 SFA' : knockout ? 'Cruce de eliminatoria' : live ? 'En juego' : 'Próxima jornada',
        priority: (topTeam ? 100 : 0) + (live ? 50 : 0) + (knockout ? 25 : 0),
      })
    }
  }
  return fixtures.sort((a, b) => b.priority - a.priority
    || new Date(a.fixture.played_at).getTime() - new Date(b.fixture.played_at).getTime()
    || tournamentCompetitionPriority(a.competition) - tournamentCompetitionPriority(b.competition)
    || a.fixture.external_id - b.fixture.external_id).slice(0, 3)
}

function Photo({ url, name, className }: { url: string | null; name: string; className: string }) {
  const [failed, setFailed] = useState(false)
  return <span className={className}>{url && !failed
    ? <img src={url} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
    : <span aria-hidden="true">{name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>}</span>
}

export default function HomeDiscoverSections({ season, topPlayers }: { season: SeasonItem; topPlayers: RankedPlayer[] }) {
  const [leaders, setLeaders] = useState<PositionLeader[]>([])
  const [positionsLoading, setPositionsLoading] = useState(true)
  const [groups, setGroups] = useState<TournamentFixtureGroup[]>([])
  const [matchesLoading, setMatchesLoading] = useState(true)
  const [matchesError, setMatchesError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setPositionsLoading(true)
    void Promise.allSettled(POSITIONS.map(position => loadPositionLeader(season.key, position.code, controller.signal))).then((results) => {
      if (controller.signal.aborted) return
      setLeaders(results.map((result, index) => ({
        ...POSITIONS[index],
        player: result.status === 'fulfilled' ? result.value : null,
        failed: result.status === 'rejected',
      })))
      setPositionsLoading(false)
    })
    return () => controller.abort()
  }, [season.key, retry])

  useEffect(() => {
    const controller = new AbortController()
    setMatchesLoading(true)
    setMatchesError(false)
    async function load() {
      try {
        const today = localDateKey(new Date().toISOString())
        const dashboard = await fetchTournamentDashboard(season.season, today, controller.signal)
        let available = dashboard.groups
        // Also inspect the next scheduled day, without scanning the full season.
        const distance = dashboard.next_date
          ? new Date(`${dashboard.next_date}T12:00:00Z`).getTime() - new Date(`${today}T12:00:00Z`).getTime()
          : 0
        if (dashboard.next_date && distance > 0 && distance <= 14 * 86400000) {
          try {
            const next = await fetchTournamentDashboard(season.season, dashboard.next_date, controller.signal)
            available = [...available, ...next.groups]
          } catch {
            // Current-day fixtures remain usable if the next day is unavailable.
          }
        }
        if (!controller.signal.aborted) setGroups(available)
      } catch {
        if (!controller.signal.aborted) setMatchesError(true)
      } finally {
        if (!controller.signal.aborted) setMatchesLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [season.season, retry])

  const fixtures = selectFixtures(groups, topPlayers)
  const rankingUrl = `/ranking?${new URLSearchParams({ scope: season.key })}`
  const positionsFailed = leaders.some((leader) => leader.failed)

  return (
    <>
      <section className="home-positions" aria-labelledby="home-positions-title" aria-busy={positionsLoading}>
        <div className="home-positions__intro">
          <div>
            <p className="home-eyebrow">Líderes por posición · {season.label}</p>
            <h2 id="home-positions-title">Quién lidera en cada posición</h2>
            <p>El primero de cada posición según los puntos SFA de la temporada.</p>
          </div>
          <Link to={rankingUrl} className="home-positions__explore">Ver todas las posiciones <span aria-hidden="true">↗</span></Link>
        </div>
        <div className="home-positions__content">
          {positionsLoading ? <div className="home-positions__loading" role="status"><span className="home-sr-only">Cargando líderes por posición</span>{POSITIONS.map(({ code }) => <div key={code} className="skeleton" />)}</div>
            : <><ul className="home-position-list">{leaders.filter(({ player }) => player).map(({ code, label, player }) => player && (
              <li key={code}>
                <Link className="home-position-player" to={`${rankingUrl}&position=${code}`} aria-label={`Ver ranking: ${label}. ${player.name}, ${Math.round(player.sfa_pts).toLocaleString('es-ES')} puntos SFA`}>
                  <span className="home-position-list__role">{label}</span>
                  <Photo key={player.id} url={player.photo_url} name={player.name} className="home-position-player__photo" />
                  <span className="home-position-player__identity"><strong>{player.name}</strong><span className="home-position-player__club"><TeamCrest key={player.team} url={player.team_logo_url} name={player.team} /><span>{player.team}</span></span></span>
                  <span className="home-position-player__points">{Math.round(player.sfa_pts).toLocaleString('es-ES')}<small>puntos SFA</small></span>
                  <span className="home-position-player__arrow" aria-hidden="true">↗</span>
                </Link>
              </li>
            ))}</ul>
            {!leaders.some(({ player }) => player) && <p className="home-positions__empty">No hay líderes disponibles para esta temporada. Puedes consultar la clasificación de cada posición.</p>}
            {leaders.some(({ player }) => !player) && <div className="home-positions__unavailable">
              <p>Sin líder disponible:</p>
              <ul>{leaders.filter(({ player }) => !player).map(({ code, label, failed }) => <li key={code}>
                <Link to={`${rankingUrl}&position=${code}`} aria-label={`${label}: ${failed ? 'No se pudo cargar' : 'Sin puntuaciones'}. Ver ranking`}>{label}{failed && <small>Error de carga</small>}</Link>
              </li>)}</ul>
            </div>}
            </>}
          {positionsFailed && <button className="home-discover-retry" onClick={() => setRetry((value) => value + 1)} type="button">Reintentar posiciones</button>}
        </div>
      </section>

      <section className="home-fixtures" aria-labelledby="home-fixtures-title" aria-busy={matchesLoading}>
        <div className="home-fixtures__intro">
          <p className="home-eyebrow">En el calendario</p>
          <h2 id="home-fixtures-title">Partidos<br />a seguir.</h2>
          <p>Equipos del top 3, eliminatorias y encuentros en juego, entre hoy y la próxima fecha disponible.</p>
          <Link to="/torneos" className="home-text-link">Ver todos los partidos <span aria-hidden="true">↗</span></Link>
        </div>
        <div className="home-fixtures__content">
          {matchesLoading ? <div className="home-fixtures__loading" role="status"><span className="home-sr-only">Cargando partidos</span><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>
            : matchesError ? <div className="home-discover-state" role="alert"><p>No pudimos consultar el calendario.</p><button className="home-discover-retry" onClick={() => setRetry((value) => value + 1)} type="button">Reintentar partidos</button></div>
              : fixtures.length === 0 ? <div className="home-discover-state"><p>No hay partidos programados o en juego en las fechas consultadas.</p><Link to="/torneos" className="sfa-action-link">Explorar el calendario completo ↗</Link></div>
                : <ul className="home-fixture-list">{fixtures.map(({ fixture, competition, reason }) => {
                  const live = LIVE_TOURNAMENT_STATUSES.has(fixture.status)
                  return <li key={fixture.external_id}><Link className="home-fixture" to={`/torneos/partido/${fixture.external_id}?${new URLSearchParams({ season: season.season })}`}>
                    <span className="home-fixture__competition">{competition.name}<span>{live ? 'En juego' : formatLocalDateShort(fixture.played_at)}</span></span>
                    <span className="home-fixture__teams">
                      <span><Photo url={tournamentTeamLogo(fixture.home_team)} name={fixture.home_team.name} className="home-fixture__crest" /><strong>{fixture.home_team.name}</strong></span>
                      <span className="home-fixture__versus">vs</span>
                      <span><Photo url={tournamentTeamLogo(fixture.away_team)} name={fixture.away_team.name} className="home-fixture__crest" /><strong>{fixture.away_team.name}</strong></span>
                    </span>
                    <span className="home-fixture__time">{live ? `${fixture.home_goals ?? '–'} : ${fixture.away_goals ?? '–'}` : formatLocalTime(fixture.played_at)}<small>{tournamentStageLabel(fixture.stage, fixture.matchday)}</small></span>
                    <span className="home-fixture__reason">{reason}<span aria-hidden="true">↗</span></span>
                  </Link></li>
                })}</ul>}
          {!matchesLoading && !matchesError && fixtures.length > 0 && <p className="home-fixtures__note">Horarios de Chile. Estado de los partidos al cargar la página.</p>}
        </div>
      </section>
    </>
  )
}
