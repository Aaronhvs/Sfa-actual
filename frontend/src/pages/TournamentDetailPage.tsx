import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchTournament, fetchTournaments } from '../api/client'
import TournamentKnockoutBracket from '../components/tournaments/TournamentKnockoutBracket'
import TournamentLeaders from '../components/tournaments/TournamentLeaders'
import { ArrowIcon, Crest, ScoreRow } from '../components/tournaments/MatchUI'
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
} from '../utils/tournaments'
import { teamHref } from '../utils/teams'
import './TournamentDetailPage.css'

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

function StandingsTable({ detail, compact = false }: { detail: TournamentDetailResponse; compact?: boolean }) {
  const [venue, setVenue] = useState<StandingVenue>('all')
  const rows = useMemo(() => deriveTable(detail, venue), [detail, venue])
  if (rows.length === 0) {
    return <div className="cd-empty">La tabla todavía no está disponible.</div>
  }
  return (
    <div className={`cd-table${compact ? ' is-compact' : ''}`}>
      <div className="cd-table__tools">
        <div className="tp-segment" role="group" aria-label="Clasificación por localía">
          {([['all', 'Todos'], ['home', 'Local'], ['away', 'Visitante']] as const).map(([value, label]) => (
            <button type="button" className={venue === value ? 'is-active' : undefined} aria-pressed={venue === value} onClick={() => setVenue(value)} key={value}>{label}</button>
          ))}
        </div>
      </div>
      <div className="cd-table__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">#</th><th scope="col" className="is-team">Equipo</th><th scope="col">PJ</th><th scope="col" className="is-narrow-hide">G</th><th scope="col" className="is-narrow-hide">E</th><th scope="col" className="is-narrow-hide">P</th>
              <th scope="col" className="is-wide">Goles</th><th scope="col">DG</th><th scope="col">Pts</th><th scope="col" className="is-wide">Últimos 5</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const position = venue === 'all' ? row.standing.position : index + 1
              const href = teamHref(row.standing.team.name, row.standing.team.external_id)
              const dg = row.goalsFor - row.goalsAgainst
              return (
                <tr key={row.standing.team.id} className={position === 1 ? 'is-leader' : undefined}>
                  <td className="cd-pos">{position}</td>
                  <th scope="row" className="is-team">
                    {href
                      ? <Link to={href}><Crest team={row.standing.team} /><span>{row.standing.team.name}</span></Link>
                      : <span className="cd-team"><Crest team={row.standing.team} /><span>{row.standing.team.name}</span></span>}
                  </th>
                  <td>{row.played}</td>
                  <td className="is-narrow-hide">{row.won}</td>
                  <td className="is-narrow-hide">{row.drawn}</td>
                  <td className="is-narrow-hide">{row.lost}</td>
                  <td className="is-wide">{row.goalsFor}–{row.goalsAgainst}</td>
                  <td className={dg > 0 ? 'is-pos' : dg < 0 ? 'is-neg' : undefined}>{dg > 0 ? '+' : ''}{dg}</td>
                  <td className="cd-pts">{row.points}</td>
                  <td className="is-wide">
                    <span className="cd-form" aria-label={`Últimos resultados: ${row.form.slice(-5).join(', ') || 'sin partidos'}`}>
                      {row.form.slice(-5).map((result, formIndex) => <i className={`is-${result.toLowerCase()}`} key={`${result}-${formIndex}`}>{result}</i>)}
                    </span>
                  </td>
                </tr>
              )
            })}
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

function FixtureDateGroups({ fixtures, season }: { fixtures: TournamentFixture[]; season: string }) {
  const groups = groupFixturesByDate(fixtures)
  if (groups.size === 0) return <div className="cd-empty">No hay partidos para este filtro.</div>
  return (
    <div className="cd-days">
      {[...groups.entries()].map(([date, items]) => (
        <section className="tp-group cd-day" key={date}>
          <header><h3>{tournamentDateLabel(date)}</h3><span>{items.length} {items.length === 1 ? 'partido' : 'partidos'}</span></header>
          <div>{items.map((fixture) => <ScoreRow fixture={fixture} season={season} key={fixture.id} />)}</div>
        </section>
      ))}
    </div>
  )
}

function MatchExplorer({ fixtures, season }: { fixtures: TournamentFixture[]; season: string }) {
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
  const [matchday, setMatchday] = useState(() => {
    const upcoming = fixtures.find((fixture) => !FINAL_TOURNAMENT_STATUSES.has(fixture.status) && fixture.matchday != null)
    return upcoming?.matchday ?? matchdays[matchdays.length - 1] ?? 0
  })
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
  const matchdayIndex = matchdays.indexOf(matchday)

  return (
    <section className="cd-explorer">
      <div className="cd-explorer__bar">
        <div className="tp-segment" role="group" aria-label="Modo de filtrado">
          {([['date', 'Por fecha'], ['matchday', 'Por jornada'], ['team', 'Por equipo']] as const).map(([value, label]) => (
            <button type="button" className={mode === value ? 'is-active' : undefined} aria-pressed={mode === value} onClick={() => setMode(value)} key={value}>{label}</button>
          ))}
        </div>
        <div className="cd-stepper">
          {mode === 'date' && (
            <>
              <button type="button" onClick={() => setDate(dates[dateIndex - 1])} disabled={dateIndex <= 0} aria-label="Fecha anterior"><ArrowIcon direction="left" /></button>
              <strong>{date ? tournamentDateLabel(date, false) : 'Sin fecha'}</strong>
              <button type="button" onClick={() => setDate(dates[dateIndex + 1])} disabled={dateIndex < 0 || dateIndex >= dates.length - 1} aria-label="Fecha siguiente"><ArrowIcon /></button>
            </>
          )}
          {mode === 'matchday' && (
            <>
              <button type="button" onClick={() => setMatchday(matchdays[matchdayIndex - 1])} disabled={matchdayIndex <= 0} aria-label="Jornada anterior"><ArrowIcon direction="left" /></button>
              <strong>Jornada {matchday}</strong>
              <button type="button" onClick={() => setMatchday(matchdays[matchdayIndex + 1])} disabled={matchdayIndex < 0 || matchdayIndex >= matchdays.length - 1} aria-label="Jornada siguiente"><ArrowIcon /></button>
            </>
          )}
          {mode === 'team' && (
            <select value={teamId} onChange={(event) => setTeamId(Number(event.target.value))} aria-label="Equipo">
              {teams.map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}
            </select>
          )}
        </div>
      </div>
      <FixtureDateGroups fixtures={filtered} season={season} />
    </section>
  )
}

function Overview({ detail }: { detail: TournamentDetailResponse }) {
  const upcoming = detail.fixtures
    .filter((fixture) => !FINAL_TOURNAMENT_STATUSES.has(fixture.status))
    .sort((a, b) => a.played_at.localeCompare(b.played_at))
    .slice(0, 8)
  const recent = detail.fixtures
    .filter((fixture) => FINAL_TOURNAMENT_STATUSES.has(fixture.status))
    .sort((a, b) => b.played_at.localeCompare(a.played_at))
    .slice(0, 5)
  return (
    <div className="cd-overview">
      <section className="pf-panel" aria-labelledby="cd-table-title">
        <header className="pf-panel__head"><div><h2 id="cd-table-title">Clasificación</h2><p>Pulsa un equipo para ver su página</p></div></header>
        <StandingsTable detail={detail} compact />
      </section>
      <div className="cd-side">
        <section aria-labelledby="cd-next-title">
          <h2 id="cd-next-title" className="tp-eyebrow">Próximos partidos</h2>
          <FixtureDateGroups fixtures={upcoming} season={detail.competition.season} />
        </section>
        {recent.length > 0 && (
          <section aria-labelledby="cd-last-title">
            <h2 id="cd-last-title" className="tp-eyebrow">Últimos resultados</h2>
            <div className="tp-group">{recent.map((fixture) => <ScoreRow fixture={fixture} season={detail.competition.season} key={fixture.id} />)}</div>
          </section>
        )}
      </div>
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
      setError('Competición no válida.')
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
      .catch(() => setError('No se pudo cargar esta competición.'))
      .finally(() => setLoading(false))
  }, [competitionId, requestedSeason])

  if (loading) {
    return (
      <main className="cd-page" aria-busy="true">
        <span className="sr-only" role="status">Cargando competición</span>
        <div className="cd-skel cd-skel--hero" />
        <div className="cd-skel cd-skel--body" />
      </main>
    )
  }
  if (error || !detail) {
    return (
      <main className="cd-page">
        <Link className="pf-back" to="/torneos"><ArrowIcon direction="left" /> Todos los torneos</Link>
        <div className="cd-empty" role="alert">{error ?? 'Competición no disponible.'}</div>
      </main>
    )
  }

  const { competition, fixtures } = detail
  const played = fixtures.filter((fixture) => FINAL_TOURNAMENT_STATUSES.has(fixture.status)).length
  const goals = fixtures.reduce((sum, fixture) => sum + (FINAL_TOURNAMENT_STATUSES.has(fixture.status) ? (fixture.home_goals ?? 0) + (fixture.away_goals ?? 0) : 0), 0)
  const leader = [...detail.standings].sort((a, b) => a.position - b.position)[0]
  const nextMatchday = fixtures.find((fixture) => !FINAL_TOURNAMENT_STATUSES.has(fixture.status) && fixture.matchday != null)?.matchday
  const hasKnockout = fixtures.some((fixture) => isTournamentKnockout(fixture.stage))
  const logo = tournamentCompetitionLogo(competition)
  const tabs = ([['overview', 'Resumen'], ['standings', 'Tabla'], ['matches', 'Partidos'], ['bracket', 'Cruces']] as const)
    .filter(([value]) => value !== 'bracket' || hasKnockout)

  return (
    <main className="cd-page">
      <nav className="cd-crumbs" aria-label="Ruta">
        <Link className="pf-back" to="/torneos"><ArrowIcon direction="left" /> Todos los torneos</Link>
      </nav>

      <header className="cd-hero">
        {logo && <img className="cd-hero__wash" src={logo} alt="" aria-hidden="true" />}
        <span className="cd-hero__logo">{logo ? <img src={logo} alt="" /> : competition.name.slice(0, 2).toUpperCase()}</span>
        <div className="cd-hero__copy">
          <p className="tp-eyebrow">{competition.country} · Temporada {tournamentSeasonLabel(competition.season)}</p>
          <h1>{competition.name}</h1>
          <ul className="cd-hero__facts">
            {leader && <li><span>Líder</span><b>{leader.team.name}</b><small>{leader.points} pts</small></li>}
            <li><span>Jugados</span><b>{played}</b><small>de {fixtures.length} partidos</small></li>
            {nextMatchday != null && <li><span>Próxima</span><b>Jornada {nextMatchday}</b></li>}
            <li><span>Goles</span><b>{goals}</b><small>{played ? `${(goals / played).toLocaleString('es-ES', { maximumFractionDigits: 1 })} por partido` : ''}</small></li>
          </ul>
        </div>
      </header>

      <div className="cd-tabs">
        <div className="tp-segment" role="group" aria-label="Secciones de la competición">
          {tabs.map(([value, label]) => (
            <button type="button" className={view === value ? 'is-active' : undefined} aria-pressed={view === value} onClick={() => setView(value)} key={value}>{label}</button>
          ))}
        </div>
      </div>

      <div className="cd-content">
        {view === 'overview' && <Overview detail={detail} />}
        {view === 'standings' && <section className="pf-panel"><StandingsTable detail={detail} /></section>}
        {view === 'matches' && <MatchExplorer fixtures={fixtures} season={competition.season} />}
        {view === 'bracket' && <div className="cd-bracket"><TournamentKnockoutBracket fixtures={fixtures} champion={detail.champion} /></div>}
      </div>

      <div className="tp-leaders cd-leaders">
        <TournamentLeaders season={competition.season} competitionId={competition.id} contextLabel={competition.name} />
      </div>
    </main>
  )
}
