import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchLatestMvps, fetchRanking, fetchTournamentDashboard, fetchTournaments } from '../api/client'
import TournamentLeaders from '../components/tournaments/TournamentLeaders'
import { LatestMvpRail } from '../components/tournaments/MatchdayMvp'
import {
  ArrowIcon,
  CompetitionTile,
  Crest,
  isFinal,
  isLive,
  isUpcoming,
  liveLabel,
  matchPath,
  ScoreRow,
} from '../components/tournaments/MatchUI'
import type {
  RankedPlayer,
  TournamentCompetition,
  TournamentDashboardResponse,
  TournamentFixture,
  TournamentFixtureGroup,
} from '../types'
import {
  isFeaturedTournamentCompetition,
  sortTournamentCompetitions,
  tournamentCompetitionPriority,
  tournamentDateKey,
  tournamentStageLabel,
  tournamentStatusLabel,
  tournamentTeamLogo,
  tournamentTimeLabel,
} from '../utils/tournaments'
import './TournamentsPage.css'

type MatchFilter = 'all' | 'live' | 'upcoming' | 'results'
type DayCount = { total: number; live: number }

const STRIP_RADIUS = 3


function filterFixture(fixture: TournamentFixture, filter: MatchFilter) {
  if (filter === 'live') return isLive(fixture)
  if (filter === 'results') return isFinal(fixture)
  if (filter === 'upcoming') return isUpcoming(fixture)
  return true
}

function countFixtures(groups: TournamentFixtureGroup[]): DayCount {
  const fixtures = groups.flatMap((group) => group.fixtures)
  return { total: fixtures.length, live: fixtures.filter(isLive).length }
}

function shiftDate(key: string, days: number) {
  const date = new Date(`${key}T12:00:00`)
  date.setDate(date.getDate() + days)
  return tournamentDateKey(date)
}

function stripDates(selected: string) {
  return Array.from({ length: STRIP_RADIUS * 2 + 1 }, (_, index) => shiftDate(selected, index - STRIP_RADIUS))
}

function pickFeatured(groups: TournamentFixtureGroup[]) {
  const candidates = sortTournamentCompetitions(groups).flatMap((group) => (
    group.fixtures.map((fixture) => ({ fixture, competition: group.competition }))
  ))
  const byKickoff = (a: { fixture: TournamentFixture }, b: { fixture: TournamentFixture }) => (
    a.fixture.played_at.localeCompare(b.fixture.played_at)
  )
  const live = candidates.filter(({ fixture }) => isLive(fixture))
  if (live.length) return live[0]
  const upcoming = candidates.filter(({ fixture }) => isUpcoming(fixture))
  if (upcoming.length) {
    const topPriority = tournamentCompetitionPriority(upcoming[0].competition)
    return upcoming
      .filter(({ competition }) => tournamentCompetitionPriority(competition) === topPriority)
      .sort(byKickoff)[0]
  }
  return candidates[0] ?? null
}

function CompetitionRail({ competitions, groups, season, isToday }: {
  competitions: TournamentCompetition[]
  groups: TournamentFixtureGroup[]
  season: string
  isToday: boolean
}) {
  const sorted = competitions
    .filter(isFeaturedTournamentCompetition)
    .sort((a, b) => (
      tournamentCompetitionPriority(a) - tournamentCompetitionPriority(b)
      || a.name.localeCompare(b.name)
    ))
  const counts = new Map(groups.map((group) => [group.competition.id, countFixtures([group])]))

  return (
    <aside className="tp-rail" aria-label="Competiciones">
      <h2 className="tp-eyebrow">Competiciones</h2>
      <nav>
        {sorted.map((competition) => {
          const count = counts.get(competition.id)
          return (
            <Link to={`/torneos/${competition.id}?season=${season}`} key={competition.id}>
              <CompetitionTile competition={competition} />
              <span className="tp-rail__name">{competition.name}</span>
              {count && count.live > 0 && <small className="tp-rail__meta is-live">{count.live} en vivo</small>}
              {count && count.live === 0 && <small className="tp-rail__meta">{count.total} {isToday ? 'hoy' : 'partidos'}</small>}
            </Link>
          )
        })}
      </nav>
      <LatestMvpRail season={season} />
    </aside>
  )
}

function FeaturedMatch({ fixture, competition, season }: {
  fixture: TournamentFixture
  competition: TournamentCompetition
  season: string
}) {
  const live = isLive(fixture)
  const finished = isFinal(fixture)
  const homeLogo = tournamentTeamLogo(fixture.home_team)
  const awayLogo = tournamentTeamLogo(fixture.away_team)
  const status = live
    ? `En vivo · ${liveLabel(fixture.status)}`
    : finished ? tournamentStatusLabel(fixture.status) : tournamentTimeLabel(fixture.played_at)

  return (
    <Link className={`tp-hero${live ? ' is-live' : ''}`} to={matchPath(fixture, season)}>
      <span className="tp-hero__wash" aria-hidden="true">
        {homeLogo && <img src={homeLogo} alt="" />}
        {awayLogo && <img src={awayLogo} alt="" />}
      </span>
      <span className="tp-hero__tag">
        <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="m8 1.5 1.9 4.1 4.4.5-3.3 3 .9 4.4L8 11.3l-3.9 2.2.9-4.4-3.3-3 4.4-.5Z" fill="currentColor" /></svg>
        {live ? 'Partido del momento' : finished ? 'Resultado destacado' : 'Próximo destacado'}
      </span>
      <span className="tp-hero__competition">
        <CompetitionTile competition={competition} />
        {competition.name} · {tournamentStageLabel(fixture.stage, fixture.matchday)}
      </span>

      <span className="tp-hero__team">
        <Crest team={fixture.home_team} size="xl" />
        <strong>{fixture.home_team.name}</strong>
      </span>
      <span className="tp-hero__center">
        <span className="tp-hero__status">{status}</span>
        {live || finished ? (
          <span className="tp-hero__score" aria-label={`${fixture.home_goals ?? 0} a ${fixture.away_goals ?? 0}`}>
            {fixture.home_goals ?? 0}<i aria-hidden="true">–</i>{fixture.away_goals ?? 0}
          </span>
        ) : (
          <span className="tp-hero__score tp-hero__score--time">{tournamentTimeLabel(fixture.played_at)}</span>
        )}
      </span>
      <span className="tp-hero__team">
        <Crest team={fixture.away_team} size="xl" />
        <strong>{fixture.away_team.name}</strong>
      </span>
    </Link>
  )
}

function DateStrip({ selected, today, counts, loading, previous, next, onSelect }: {
  selected: string
  today: string
  counts: Record<string, DayCount>
  loading: boolean
  previous: string | null
  next: string | null
  onSelect: (date?: string) => void
}) {
  const weekday = new Intl.DateTimeFormat('es-ES', { weekday: 'short' })
  return (
    <div className="tp-dates">
      <button type="button" className="tp-dates__step" onClick={() => previous && onSelect(previous)} disabled={!previous || loading} aria-label="Fecha anterior con partidos">
        <ArrowIcon direction="left" />
      </button>
      <ol>
        {stripDates(selected).map((key) => {
          const date = new Date(`${key}T12:00:00`)
          const count = counts[key]
          const active = key === selected
          return (
            <li key={key}>
              <button
                type="button"
                className={`tp-day${active ? ' is-active' : ''}${count?.total === 0 ? ' is-empty' : ''}`}
                onClick={() => !active && onSelect(key)}
                disabled={loading && !active}
                aria-pressed={active}
              >
                <span>{key === today ? 'Hoy' : weekday.format(date).replace('.', '')}</span>
                <strong>{date.getDate()}</strong>
                <small>
                  {count == null ? ' ' : count.live > 0 ? <b>{count.live} en vivo</b> : `${count.total} partidos`}
                </small>
              </button>
            </li>
          )
        })}
      </ol>
      <button type="button" className="tp-dates__step" onClick={() => next && onSelect(next)} disabled={!next || loading} aria-label="Siguiente fecha con partidos">
        <ArrowIcon />
      </button>
    </div>
  )
}

const GROUP_PREVIEW = 8

function MatchGroup({ group, season }: { group: TournamentFixtureGroup; season: string }) {
  const [expanded, setExpanded] = useState(false)
  const first = group.fixtures[0]
  const stage = first && (first.matchday != null || first.stage.toLowerCase() !== 'regular')
    ? tournamentStageLabel(first.stage, first.matchday)
    : null
  const hidden = group.fixtures.length - GROUP_PREVIEW
  const fixtures = expanded || hidden <= 0
    ? group.fixtures
    : [...group.fixtures.filter(isLive), ...group.fixtures.filter((fixture) => !isLive(fixture))].slice(0, GROUP_PREVIEW)

  return (
    <section className="tp-group" aria-label={group.competition.name}>
      <header>
        <CompetitionTile competition={group.competition} />
        <h3>{group.competition.name}</h3>
        {stage && <span>{stage}</span>}
        <Link to={`/torneos/${group.competition.id}?season=${season}`}>
          Tabla y calendario <ArrowIcon />
        </Link>
      </header>
      <div>{fixtures.map((fixture) => <ScoreRow fixture={fixture} season={season} key={fixture.id} />)}</div>
      {hidden > 0 && (
        <button type="button" className="tp-group__more" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
          {expanded ? 'Ver menos' : `Ver ${hidden} partidos más`}
        </button>
      )}
    </section>
  )
}

function ExplorePromos() {
  return (
    <>
      <h2 className="tp-eyebrow">Explora</h2>
      <Link className="tp-promo tp-promo--compare" to="/compare">
        <span className="tp-promo__kicker">Comparador</span>
        <strong>Cara a cara</strong>
        <span>Enfrenta a dos jugadores con su impacto SFA, rival a rival.</span>
        <i aria-hidden="true"><ArrowIcon /></i>
      </Link>
      <Link className="tp-promo tp-promo--method" to="/metodologia">
        <span className="tp-promo__kicker">Metodología</span>
        <strong>Cómo puntúa SFA</strong>
        <span>Rival, competición y momento del partido: qué pesa en cada acción.</span>
        <i aria-hidden="true"><ArrowIcon /></i>
      </Link>
    </>
  )
}

function SidePanel({ players, season }: { players: RankedPlayer[]; season: string }) {
  return (
    <aside className="tp-side" aria-label="Rendimiento SFA">
      <section className="tp-top">
        <h2>Top SFA de la temporada</h2>
        <p>Los jugadores con más puntos SFA en todas las competiciones.</p>
        {players.length === 0
          ? <p className="tp-top__empty">El ranking aparecerá cuando haya puntos calculados.</p>
          : (
            <ol>
              {players.map((player, index) => (
                <li key={player.id}>
                  <Link to={`/player/${player.id}?scope=season-${season}`}>
                    <b>{index + 1}</b>
                    <span className="tp-top__photo">
                      {player.photo_url && <img src={player.photo_url} alt="" loading="lazy" />}
                    </span>
                    <span className="tp-top__who"><strong>{player.name}</strong><small>{player.team}</small></span>
                    <em>{Math.round(player.sfa_pts).toLocaleString('es-ES')}</em>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        <Link className="tp-top__cta" to="/ranking">Ver ranking completo <ArrowIcon /></Link>
      </section>

      <ExplorePromos />
    </aside>
  )
}

function LoadingState() {
  return (
    <main className="tp-page" aria-busy="true">
      <span className="sr-only" role="status">Cargando partidos</span>
      <div className="tp-layout">
        <div className="tp-skel tp-skel--rail" />
        <div className="tp-main">
          <div className="tp-skel tp-skel--hero" />
          <div className="tp-skel tp-skel--strip" />
          <div className="tp-skel tp-skel--group" />
        </div>
        <div className="tp-skel tp-skel--side" />
      </div>
    </main>
  )
}

export default function TournamentsPage() {
  const [competitions, setCompetitions] = useState<TournamentCompetition[]>([])
  const [dashboard, setDashboard] = useState<TournamentDashboardResponse | null>(null)
  const [topPlayers, setTopPlayers] = useState<RankedPlayer[]>([])
  const [hasMvps, setHasMvps] = useState(false)
  const [dayCounts, setDayCounts] = useState<Record<string, DayCount>>({})
  const [filter, setFilter] = useState<MatchFilter>('all')
  const [loading, setLoading] = useState(true)
  const [matchesLoading, setMatchesLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const today = tournamentDateKey(new Date())

  useEffect(() => {
    Promise.all([fetchTournaments(), fetchTournamentDashboard()])
      .then(([catalog, result]) => {
        setCompetitions(catalog.competitions)
        setDashboard(result)
        return fetchRanking({ scope: `season-${result.season}`, limit: 3 })
          .then((ranking) => setTopPlayers(ranking.ranking))
          .catch(() => setTopPlayers([]))
      })
      .catch(() => setError('No se pudo cargar el centro de torneos.'))
      .finally(() => setLoading(false))
  }, [])

  const season = dashboard?.season ?? ''
  const selected = dashboard?.selected_date ?? null

  useEffect(() => {
    let active = true
    setHasMvps(false)
    if (season) fetchLatestMvps(season).then((response) => { if (active) setHasMvps(Boolean(response?.items.length)) })
    return () => { active = false }
  }, [season])

  useEffect(() => {
    if (!dashboard || !selected) return
    setDayCounts((current) => ({ ...current, [selected]: countFixtures(dashboard.groups) }))
    let cancelled = false
    stripDates(selected)
      .filter((key) => key !== selected)
      .forEach((key) => {
        fetchTournamentDashboard(season, key)
          .then((result) => {
            if (!cancelled) setDayCounts((current) => ({ ...current, [key]: countFixtures(result.groups) }))
          })
          .catch(() => undefined)
      })
    return () => { cancelled = true }
  }, [dashboard, selected, season])

  const loadDate = (date?: string) => {
    if (!dashboard) return
    setMatchesLoading(true)
    setError(null)
    fetchTournamentDashboard(dashboard.season, date)
      .then(setDashboard)
      .catch(() => setError('No se pudieron cargar los partidos de esta fecha.'))
      .finally(() => setMatchesLoading(false))
  }

  const allGroups = useMemo(() => (dashboard ? sortTournamentCompetitions(dashboard.groups) : []), [dashboard])
  const totals = useMemo(() => countFixtures(allGroups), [allGroups])
  const featured = useMemo(() => pickFeatured(allGroups), [allGroups])
  const visibleGroups = useMemo(() => (
    allGroups
      .map((group) => ({ ...group, fixtures: group.fixtures.filter((fixture) => filterFixture(fixture, filter)) }))
      .filter((group) => group.fixtures.length > 0)
  ), [allGroups, filter])

  if (loading) return <LoadingState />

  const filters: Array<[MatchFilter, string]> = [
    ['all', 'Todos'],
    ['live', `En vivo · ${totals.live}`],
    ['upcoming', 'Próximos'],
    ['results', 'Resultados'],
  ]

  return (
    <main className="tp-page">
      <h1 className="sr-only">Torneos y partidos</h1>
      <div className="tp-layout">
        <CompetitionRail competitions={competitions} groups={allGroups} season={season} isToday={selected === today} />

        <div className="tp-main">
          {error && <div className="tp-alert" role="alert">{error}</div>}
          {featured && <FeaturedMatch fixture={featured.fixture} competition={featured.competition} season={season} />}

          <section className="tp-matches" aria-labelledby="tp-matches-title">
            <header className="tp-matches__head">
              <div>
                <h2 id="tp-matches-title">Partidos</h2>
                <p>
                  {totals.total} partidos
                  {totals.live > 0 && <> · <b>{totals.live} en vivo</b></>}
                </p>
              </div>
              <div className="tp-matches__tools">
                <div className="tp-segment" role="group" aria-label="Filtrar partidos">
                  {filters.map(([value, label]) => (
                    <button
                      type="button"
                      className={`${filter === value ? 'is-active' : ''}${value === 'live' && totals.live > 0 ? ' has-live' : ''}`}
                      aria-pressed={filter === value}
                      onClick={() => setFilter(value)}
                      key={value}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <button type="button" className="tp-today" onClick={() => loadDate()} disabled={matchesLoading} aria-label="Ir a hoy o a la próxima fecha con partidos" title="Hoy o próxima fecha">
                  <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                    <rect x="2" y="3" width="12" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
                    <path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            </header>

            {selected && (
              <DateStrip
                selected={selected}
                today={today}
                counts={dayCounts}
                loading={matchesLoading}
                previous={dashboard?.previous_date ?? null}
                next={dashboard?.next_date ?? null}
                onSelect={loadDate}
              />
            )}

            <div className={`tp-groups${matchesLoading ? ' is-loading' : ''}`}>
              {visibleGroups.map((group) => <MatchGroup group={group} season={season} key={group.competition.id} />)}
              {visibleGroups.length === 0 && (
                <div className="tp-empty">
                  <strong>{filter === 'live' ? 'Ningún partido en juego ahora' : 'Sin partidos para este filtro'}</strong>
                  <span>Cambia de día en el calendario o vuelve a ver todos los partidos.</span>
                  {filter !== 'all' && <button type="button" onClick={() => setFilter('all')}>Ver todos</button>}
                </div>
              )}
            </div>
          </section>
        </div>

        <SidePanel players={topPlayers} season={season} />
      </div>

      {dashboard && (
        <div className="tp-leaders">
          <TournamentLeaders
            season={dashboard.season}
            contextLabel="la temporada"
            hubBoards={[
              // The round tab only exists when there are MVPs to show (the endpoint may not be live yet).
              ...(hasMvps ? [{ key: 'round', label: 'Jornada', title: 'MVP de la jornada', unit: 'Pts', node: <LatestMvpRail season={dashboard.season} /> }] : []),
              { key: 'season', label: 'Temporada', title: 'Top SFA de la temporada', unit: 'Pts', players: topPlayers },
            ]}
          />
        </div>
      )}

      {/* Phones only: the side column is hidden there, so the promos close the page after the player hub */}
      <nav className="tp-explore-mobile" aria-label="Explora">
        <ExplorePromos />
      </nav>
    </main>
  )
}
