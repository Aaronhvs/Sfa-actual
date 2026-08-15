import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchTournament, fetchTournaments } from '../api/client'
import TournamentFixtureRow from '../components/tournaments/TournamentFixtureRow'
import type {
  TournamentDetailResponse,
  TournamentFixture,
  TournamentStanding,
  TournamentTeam,
} from '../types'
import {
  FINAL_TOURNAMENT_STATUSES,
  isTournamentKnockout,
  tournamentCompetitionLogo,
  tournamentDateKey,
  tournamentDateLabel,
  tournamentSeasonLabel,
  tournamentTeamLogo,
} from '../utils/tournaments'

type DetailView = 'overview' | 'standings' | 'matches' | 'bracket'
type MatchMode = 'date' | 'matchday' | 'team'

interface TableRow {
  standing: TournamentStanding
  played: number
  won: number
  drawn: number
  lost: number
  goalsFor: number
  goalsAgainst: number
}

function TeamMark({ team }: { team: TournamentTeam }) {
  const logo = tournamentTeamLogo(team)
  return logo
    ? <img src={logo} alt="" loading="lazy" decoding="async" />
    : <span aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

function deriveTable(detail: TournamentDetailResponse): TableRow[] {
  const rows = new Map<number, TableRow>(detail.standings.map((standing) => [
    standing.team.id,
    {
      standing,
      played: 0,
      won: 0,
      drawn: 0,
      lost: 0,
      goalsFor: 0,
      goalsAgainst: 0,
    },
  ]))

  for (const fixture of detail.fixtures) {
    if (!FINAL_TOURNAMENT_STATUSES.has(fixture.status)) continue
    if (fixture.home_goals == null || fixture.away_goals == null) continue
    const home = rows.get(fixture.home_team.id)
    const away = rows.get(fixture.away_team.id)
    if (!home || !away) continue
    home.played += 1
    away.played += 1
    home.goalsFor += fixture.home_goals
    home.goalsAgainst += fixture.away_goals
    away.goalsFor += fixture.away_goals
    away.goalsAgainst += fixture.home_goals
    if (fixture.home_goals === fixture.away_goals) {
      home.drawn += 1
      away.drawn += 1
    } else if (fixture.home_goals > fixture.away_goals) {
      home.won += 1
      away.lost += 1
    } else {
      away.won += 1
      home.lost += 1
    }
  }
  return [...rows.values()].sort((a, b) => a.standing.position - b.standing.position)
}

function StandingsTable({ detail, compact = false }: {
  detail: TournamentDetailResponse
  compact?: boolean
}) {
  const rows = useMemo(() => deriveTable(detail), [detail])
  if (rows.length === 0) {
    return <div className="trn-state trn-state--inline">La tabla todavia no esta disponible.</div>
  }
  const visible = compact ? rows.slice(0, 8) : rows
  return (
    <div className="trn-table-wrap">
      <table className="trn-table">
        <thead><tr><th>#</th><th>Equipo</th><th>J</th><th>G</th><th>E</th><th>P</th><th>DG</th><th>Pts</th></tr></thead>
        <tbody>
          {visible.map((row) => (
            <tr key={row.standing.team.id}>
              <td>{row.standing.position}</td>
              <th scope="row"><TeamMark team={row.standing.team} /><span>{row.standing.team.name}</span></th>
              <td>{row.played}</td>
              <td>{row.won}</td>
              <td>{row.drawn}</td>
              <td>{row.lost}</td>
              <td>{row.goalsFor - row.goalsAgainst}</td>
              <td><strong>{row.standing.points}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function groupFixturesByDate(fixtures: TournamentFixture[]) {
  return fixtures.reduce<Map<string, TournamentFixture[]>>((groups, fixture) => {
    const key = tournamentDateKey(fixture.played_at)
    groups.set(key, [...(groups.get(key) ?? []), fixture])
    return groups
  }, new Map())
}

function nearestDate(values: string[]) {
  const today = tournamentDateKey(new Date())
  return values.find((value) => value >= today) ?? values[values.length - 1] ?? ''
}

function FixtureDateGroups({ fixtures }: { fixtures: TournamentFixture[] }) {
  const groups = groupFixturesByDate(fixtures)
  if (groups.size === 0) {
    return <div className="trn-state trn-state--inline">No hay partidos para este filtro.</div>
  }
  return (
    <div className="trn-detail-matches">
      {[...groups.entries()].map(([date, items]) => (
        <section key={date}>
          <h3>{tournamentDateLabel(date)}</h3>
          <div>{items.map((fixture) => <TournamentFixtureRow fixture={fixture} key={fixture.id} />)}</div>
        </section>
      ))}
    </div>
  )
}

function MatchExplorer({ fixtures }: { fixtures: TournamentFixture[] }) {
  const dates = useMemo(() => [...new Set(fixtures.map((fixture) => tournamentDateKey(fixture.played_at)))].sort(), [fixtures])
  const matchdays = useMemo(() => [...new Set(fixtures.map((fixture) => fixture.matchday).filter((value): value is number => value != null))].sort((a, b) => a - b), [fixtures])
  const teams = useMemo(() => {
    const values = new Map<number, TournamentTeam>()
    fixtures.forEach((fixture) => {
      values.set(fixture.home_team.id, fixture.home_team)
      values.set(fixture.away_team.id, fixture.away_team)
    })
    return [...values.values()].sort((a, b) => a.name.localeCompare(b.name))
  }, [fixtures])
  const [mode, setMode] = useState<MatchMode>('date')
  const [date, setDate] = useState(() => nearestDate(dates))
  const [matchday, setMatchday] = useState(matchdays[0] ?? 0)
  const [teamId, setTeamId] = useState(teams[0]?.id ?? 0)

  useEffect(() => { if (!dates.includes(date)) setDate(nearestDate(dates)) }, [date, dates])
  useEffect(() => { if (!matchdays.includes(matchday)) setMatchday(matchdays[0] ?? 0) }, [matchday, matchdays])
  useEffect(() => { if (!teams.some((team) => team.id === teamId)) setTeamId(teams[0]?.id ?? 0) }, [teamId, teams])

  const filtered = fixtures.filter((fixture) => {
    if (mode === 'date') return tournamentDateKey(fixture.played_at) === date
    if (mode === 'matchday') return fixture.matchday === matchday
    return fixture.home_team.id === teamId || fixture.away_team.id === teamId
  })
  const dateIndex = dates.indexOf(date)

  return (
    <section className="trn-explorer">
      <div className="trn-explorer__modes" role="group" aria-label="Modo de filtrado">
        {([['date', 'Por fecha'], ['matchday', 'Por jornada'], ['team', 'Por equipo']] as const).map(([value, label]) => (
          <button type="button" className={mode === value ? 'is-active' : ''} onClick={() => setMode(value)} key={value}>{label}</button>
        ))}
      </div>
      <div className="trn-explorer__control">
        {mode === 'date' && (
          <>
            <button type="button" onClick={() => setDate(dates[dateIndex - 1])} disabled={dateIndex <= 0} aria-label="Fecha anterior">&#8592;</button>
            <strong>{date ? tournamentDateLabel(date, false) : 'Sin fecha'}</strong>
            <button type="button" onClick={() => setDate(dates[dateIndex + 1])} disabled={dateIndex < 0 || dateIndex >= dates.length - 1} aria-label="Fecha siguiente">&#8594;</button>
          </>
        )}
        {mode === 'matchday' && (
          <select value={matchday} onChange={(event) => setMatchday(Number(event.target.value))} aria-label="Jornada">
            {matchdays.map((value) => <option value={value} key={value}>Jornada {value}</option>)}
          </select>
        )}
        {mode === 'team' && (
          <select value={teamId} onChange={(event) => setTeamId(Number(event.target.value))} aria-label="Equipo">
            {teams.map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}
          </select>
        )}
      </div>
      <FixtureDateGroups fixtures={filtered} />
    </section>
  )
}

function Bracket({ fixtures }: { fixtures: TournamentFixture[] }) {
  const knockout = fixtures.filter((fixture) => isTournamentKnockout(fixture.stage))
  const stages = knockout.reduce<Map<string, TournamentFixture[]>>((groups, fixture) => {
    groups.set(fixture.stage, [...(groups.get(fixture.stage) ?? []), fixture])
    return groups
  }, new Map())
  if (stages.size === 0) {
    return <div className="trn-state trn-state--inline">Los cruces apareceran cuando se definan las fases eliminatorias.</div>
  }
  return (
    <div className="trn-bracket">
      {[...stages.entries()].map(([stage, items]) => (
        <section key={stage}><h3>{stage.replace(/_/g, ' ')}</h3>{items.map((fixture) => <TournamentFixtureRow fixture={fixture} key={fixture.id} />)}</section>
      ))}
    </div>
  )
}

function Overview({ detail }: { detail: TournamentDetailResponse }) {
  const upcoming = detail.fixtures.filter((fixture) => !FINAL_TOURNAMENT_STATUSES.has(fixture.status)).slice(0, 8)
  return (
    <div className="trn-overview-grid">
      <section><header><span>Clasificacion</span><h2>Tabla actual</h2></header><StandingsTable detail={detail} compact /></section>
      <section><header><span>Calendario</span><h2>Proximos partidos</h2></header><FixtureDateGroups fixtures={upcoming} /></section>
    </div>
  )
}

export default function TournamentDetailPage() {
  const { competitionId } = useParams()
  const [searchParams] = useSearchParams()
  const requestedSeason = searchParams.get('season')
  const [detail, setDetail] = useState<TournamentDetailResponse | null>(null)
  const [view, setView] = useState<DetailView>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const id = Number(competitionId)
    if (!Number.isFinite(id)) {
      setError('Competicion invalida.')
      setLoading(false)
      return
    }
    setLoading(true)
    const seasonPromise = requestedSeason
      ? Promise.resolve(requestedSeason)
      : fetchTournaments().then((catalog) => catalog.season)
    seasonPromise
      .then((season) => fetchTournament(id, season))
      .then(setDetail)
      .catch(() => setError('No se pudo cargar esta competicion.'))
      .finally(() => setLoading(false))
  }, [competitionId, requestedSeason])

  if (loading) return <div className="trn-state" role="status">Cargando competicion</div>
  if (error || !detail) return <div className="trn-state trn-state--error" role="alert">{error ?? 'Competicion no disponible.'}</div>

  return (
    <main className="trn-detail-page">
      <Link className="trn-back" to="/torneos">&#8592; Todos los torneos</Link>
      <header className="trn-detail-header">
        <div className="trn-detail-header__identity">
          <img src={tournamentCompetitionLogo(detail.competition)} alt="" />
          <div><span>{detail.competition.country}</span><h1>{detail.competition.name}</h1></div>
        </div>
        <strong>Temporada {tournamentSeasonLabel(detail.competition.season)}</strong>
      </header>
      <nav className="trn-detail-tabs" aria-label="Secciones de la competicion">
        {([['overview', 'Resumen'], ['standings', 'Tabla'], ['matches', 'Partidos'], ['bracket', 'Cruces']] as const).map(([value, label]) => (
          <button type="button" className={view === value ? 'is-active' : ''} aria-current={view === value ? 'page' : undefined} onClick={() => setView(value)} key={value}>{label}</button>
        ))}
      </nav>
      <div className="trn-detail-content">
        {view === 'overview' && <Overview detail={detail} />}
        {view === 'standings' && <StandingsTable detail={detail} />}
        {view === 'matches' && <MatchExplorer fixtures={detail.fixtures} />}
        {view === 'bracket' && <Bracket fixtures={detail.fixtures} />}
      </div>
    </main>
  )
}
