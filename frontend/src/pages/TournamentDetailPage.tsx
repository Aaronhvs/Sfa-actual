import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchTournament, fetchTournaments } from '../api/client'
import TournamentFixtureRow from '../components/tournaments/TournamentFixtureRow'
import TournamentKnockoutBracket from '../components/tournaments/TournamentKnockoutBracket'
import TournamentLeaders from '../components/tournaments/TournamentLeaders'
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
type StandingVenue = 'all' | 'home' | 'away'
type FormResult = 'G' | 'E' | 'P'

interface TableRow {
  standing: TournamentStanding
  played: number
  won: number
  drawn: number
  lost: number
  goalsFor: number
  goalsAgainst: number
  points: number
  form: FormResult[]
}

function TeamMark({ team }: { team: TournamentTeam }) {
  const logo = tournamentTeamLogo(team)
  return logo
    ? <img src={logo} alt="" loading="lazy" decoding="async" />
    : <span aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

function deriveTable(detail: TournamentDetailResponse, venue: StandingVenue): TableRow[] {
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
      points: 0,
      form: [],
    },
  ]))

  const finalFixtures = detail.fixtures
    .filter((fixture) => (
      FINAL_TOURNAMENT_STATUSES.has(fixture.status)
      && !isTournamentKnockout(fixture.stage)
    ))
    .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())

  const applyResult = (row: TableRow | undefined, goalsFor: number, goalsAgainst: number) => {
    if (!row) return
    row.played += 1
    row.goalsFor += goalsFor
    row.goalsAgainst += goalsAgainst
    if (goalsFor > goalsAgainst) {
      row.won += 1
      row.points += 3
      row.form.push('G')
    } else if (goalsFor === goalsAgainst) {
      row.drawn += 1
      row.points += 1
      row.form.push('E')
    } else {
      row.lost += 1
      row.form.push('P')
    }
  }

  for (const fixture of finalFixtures) {
    if (fixture.home_goals == null || fixture.away_goals == null) continue
    if (venue !== 'away') {
      applyResult(rows.get(fixture.home_team.id), fixture.home_goals, fixture.away_goals)
    }
    if (venue !== 'home') {
      applyResult(rows.get(fixture.away_team.id), fixture.away_goals, fixture.home_goals)
    }
  }

  const result = [...rows.values()]
  if (venue === 'all') {
    result.forEach((row) => { row.points = row.standing.points })
    return result.sort((a, b) => a.standing.position - b.standing.position)
  }
  return result.sort((a, b) => (
    b.points - a.points
    || (b.goalsFor - b.goalsAgainst) - (a.goalsFor - a.goalsAgainst)
    || b.goalsFor - a.goalsFor
    || a.standing.position - b.standing.position
  ))
}

function StandingsTable({ detail }: { detail: TournamentDetailResponse }) {
  const [venue, setVenue] = useState<StandingVenue>('all')
  const rows = useMemo(() => deriveTable(detail, venue), [detail, venue])
  if (rows.length === 0) {
    return <div className="trn-state trn-state--inline">La tabla todavia no esta disponible.</div>
  }
  return (
    <div className="trn-standings">
      <div className="trn-table-filters" role="group" aria-label="Clasificacion por localia">
        {([['all', 'Todos'], ['home', 'Local'], ['away', 'Visitante']] as const).map(([value, label]) => (
          <button type="button" className={venue === value ? 'is-active' : ''} onClick={() => setVenue(value)} key={value}>{label}</button>
        ))}
      </div>
      <div className="trn-table-wrap">
        <table className="trn-table">
          <thead><tr><th>#</th><th>Equipo</th><th>PJ</th><th>G</th><th>E</th><th>P</th><th>Goles</th><th>DG</th><th>Pts</th><th>Forma</th></tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.standing.team.id}>
                <td>{venue === 'all' ? row.standing.position : index + 1}</td>
                <th scope="row"><TeamMark team={row.standing.team} /><span>{row.standing.team.name}</span></th>
                <td>{row.played}</td>
                <td>{row.won}</td>
                <td>{row.drawn}</td>
                <td>{row.lost}</td>
                <td>{row.goalsFor}-{row.goalsAgainst}</td>
                <td>{row.goalsFor - row.goalsAgainst > 0 ? '+' : ''}{row.goalsFor - row.goalsAgainst}</td>
                <td><strong>{row.points}</strong></td>
                <td>
                  <span className="trn-form" aria-label={`Ultimos resultados: ${row.form.slice(-5).join(', ') || 'sin partidos'}`}>
                    {row.form.slice(-5).map((result, formIndex) => <i className={`is-${result.toLowerCase()}`} key={`${result}-${formIndex}`}>{result}</i>)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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

function Overview({ detail }: { detail: TournamentDetailResponse }) {
  const upcoming = detail.fixtures.filter((fixture) => !FINAL_TOURNAMENT_STATUSES.has(fixture.status)).slice(0, 8)
  return (
    <div className="trn-overview-grid">
      <section><header><span>Clasificacion</span><h2>Tabla actual</h2></header><StandingsTable detail={detail} /></section>
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
        {view === 'bracket' && <TournamentKnockoutBracket fixtures={detail.fixtures} champion={detail.champion} />}
      </div>
      <TournamentLeaders
        season={detail.competition.season}
        competitionId={detail.competition.id}
        contextLabel={detail.competition.name}
      />
    </main>
  )
}
