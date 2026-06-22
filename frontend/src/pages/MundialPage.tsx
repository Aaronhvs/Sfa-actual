import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import type {
  WcFixture,
  WcFixturesResponse,
  WcStanding,
  WcStandingsResponse,
  WcTeamSFARankingItem,
} from '../types'
import { fetchWcFixtures, fetchWcLive, fetchWcStandings, fetchWcTeamSFARanking } from '../api/client'
import { worldCupTeamName, worldCupStageLabel } from '../utils/worldCupTeams'

type MundialView = 'matches' | 'standings' | 'bracket' | 'teams'
type MatchTone = 'live' | 'result' | 'upcoming'

const FINISHED_STATUSES = new Set(['FT', 'AET', 'PEN'])
const KNOCKOUT_MARKERS = [
  'round of 32',
  'round of 16',
  'last 16',
  'quarter',
  'semi',
  'final',
  '3rd place',
]

const TEAM_LOGO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/teams/${externalId}.png` : null

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function dateKey(iso: string): string {
  const date = new Date(iso)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function compactDateLabel(key: string): string {
  return new Date(`${key}T12:00:00`).toLocaleDateString('es-ES', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function uniqueDateOptions(fixtures: WcFixture[], direction: 'asc' | 'desc') {
  const keys = Array.from(new Set(fixtures.map((fixture) => dateKey(fixture.played_at))))
  return keys
    .sort((a, b) => direction === 'asc' ? a.localeCompare(b) : b.localeCompare(a))
    .map((key) => ({ key, label: compactDateLabel(key) }))
}

function isKnockout(fixture: WcFixture): boolean {
  const stage = fixture.stage.toLowerCase()
  return KNOCKOUT_MARKERS.some((marker) => stage.includes(marker))
}

function TeamLogo({ team, className }: {
  team: WcFixture['home_team']
  className: string
}) {
  const logo = TEAM_LOGO(team.external_id)
  const displayName = worldCupTeamName(team)
  if (!logo) return <span className={`${className} wm-team-fallback`}>{displayName.slice(0, 2)}</span>

  return (
    <img
      src={logo}
      alt=""
      className={className}
      loading="lazy"
      onError={(event) => {
        event.currentTarget.style.visibility = 'hidden'
      }}
    />
  )
}

function FixtureCard({ fixture, compact = false }: {
  fixture: WcFixture
  compact?: boolean
}) {
  const finished = FINISHED_STATUSES.has(fixture.status)
  const hasScore = fixture.home_goals != null && fixture.away_goals != null

  return (
    <Link
      to={`/mundial/partido/${fixture.external_id}`}
      className={[
        'wm-match',
        fixture.is_live ? 'wm-match--live' : '',
        finished ? 'wm-match--finished' : '',
        compact ? 'wm-match--compact' : '',
      ].filter(Boolean).join(' ')}
      aria-label={`Ver ${worldCupTeamName(fixture.home_team)} contra ${worldCupTeamName(fixture.away_team)}`}
    >
      <div className="wm-match__stage">{worldCupStageLabel(fixture.stage)}</div>

      <div className="wm-match__teams">
        <div className="wm-match__team">
          <TeamLogo team={fixture.home_team} className="wm-match__logo" />
          <span>{worldCupTeamName(fixture.home_team)}</span>
        </div>

        <div className="wm-match__score" aria-label={
          hasScore
            ? `${fixture.home_goals} a ${fixture.away_goals}`
            : `${formatDate(fixture.played_at)} a las ${formatTime(fixture.played_at)}`
        }>
          {fixture.is_live ? (
            <>
              <strong>{fixture.home_goals ?? 0} - {fixture.away_goals ?? 0}</strong>
              <small className="wm-match__live">
                <i aria-hidden="true" />
                {fixture.status === 'HT' ? 'Descanso' : `${fixture.elapsed ?? ''}' En vivo`}
              </small>
            </>
          ) : finished && hasScore ? (
            <>
              <strong>{fixture.home_goals} - {fixture.away_goals}</strong>
              <small>Final</small>
            </>
          ) : (
            <>
              <strong>{formatTime(fixture.played_at)}</strong>
              <small>{formatDate(fixture.played_at)}</small>
            </>
          )}
        </div>

        <div className="wm-match__team wm-match__team--away">
          <TeamLogo team={fixture.away_team} className="wm-match__logo" />
          <span>{worldCupTeamName(fixture.away_team)}</span>
        </div>
      </div>
    </Link>
  )
}

function DateRail({
  label,
  dates,
  value,
  onChange,
}: {
  label: string
  dates: Array<{ key: string; label: string }>
  value: string
  onChange: (key: string) => void
}) {
  if (dates.length === 0) return null

  return (
    <div className="wm-date-rail" aria-label={label}>
      {dates.map((date) => (
        <button
          type="button"
          key={date.key}
          className={`wm-date-rail__button${date.key === value ? ' wm-date-rail__button--active' : ''}`}
          onClick={() => onChange(date.key)}
          aria-pressed={date.key === value}
        >
          {date.label}
        </button>
      ))}
    </div>
  )
}

function ScorePill({ fixture, tone }: { fixture: WcFixture; tone: MatchTone }) {
  const finished = FINISHED_STATUSES.has(fixture.status)
  const hasScore = fixture.home_goals != null && fixture.away_goals != null
  const homeName = worldCupTeamName(fixture.home_team)
  const awayName = worldCupTeamName(fixture.away_team)
  const statusLabel = tone === 'live'
    ? fixture.status === 'HT' ? 'Descanso' : `${fixture.elapsed ?? ''}'`
    : finished
      ? 'Final'
      : formatTime(fixture.played_at)

  return (
    <Link
      to={`/mundial/partido/${fixture.external_id}`}
      className={`wm-score-pill wm-score-pill--${tone}`}
      aria-label={`Ver ${homeName} contra ${awayName}`}
    >
      <span className="wm-score-pill__stage">
        {worldCupStageLabel(fixture.stage)}
      </span>
      <span className="wm-score-pill__line">
        <span className="wm-score-pill__team">
          <TeamLogo team={fixture.home_team} className="wm-score-pill__flag" />
          <strong>{homeName}</strong>
        </span>
        <span className="wm-score-pill__score">
          {hasScore ? `${fixture.home_goals} - ${fixture.away_goals}` : 'vs'}
        </span>
        <span className="wm-score-pill__team wm-score-pill__team--away">
          <TeamLogo team={fixture.away_team} className="wm-score-pill__flag" />
          <strong>{awayName}</strong>
        </span>
      </span>
      <span className="wm-score-pill__meta">
        <i aria-hidden="true" />
        {statusLabel}
      </span>
    </Link>
  )
}

function SpotlightMatch({ fixture }: { fixture: WcFixture }) {
  const tone: MatchTone = fixture.is_live
    ? 'live'
    : FINISHED_STATUSES.has(fixture.status)
      ? 'result'
      : 'upcoming'
  const title = tone === 'live' ? 'Partido en vivo' : tone === 'result' ? 'Último resultado' : 'Próximo partido'

  return (
    <section className={`wm-now-strip wm-now-strip--${tone}`} aria-label={title}>
      <div className="wm-now-strip__label">
        <i aria-hidden="true" />
        <span>{title}</span>
      </div>
      <ScorePill fixture={fixture} tone={tone} />
    </section>
  )
}

function StandingsGroup({ group, rows }: { group: string; rows: WcStanding[] }) {
  return (
    <section className="wm-group">
      <header className="wm-group__header">
        <span>{group.replace('Group', 'Grupo')}</span>
        <small>Pts</small>
      </header>
      <div className="wm-group__labels" aria-hidden="true">
        <span>Pos. Selección</span>
        <span>PJ</span>
        <span>DG</span>
        <span>Pts</span>
      </div>
      {rows.map((row) => (
        <Link
          to={row.team.external_id != null ? `/mundial/seleccion/${row.team.external_id}` : '#'}
          className="wm-standing-row wm-standing-row--link"
          key={row.team.external_id}
        >
          <span className="wm-standing-row__position">{row.position}</span>
          <TeamLogo team={row.team} className="wm-standing-row__logo" />
          <strong>{worldCupTeamName(row.team)}</strong>
          <span>{row.played}</span>
          <span>{row.goal_difference > 0 ? '+' : ''}{row.goal_difference}</span>
          <b>{row.points}</b>
        </Link>
      ))}
    </section>
  )
}

function TeamSFARankingView({ teams }: { teams: WcTeamSFARankingItem[] }) {
  if (teams.length === 0) {
    return <div className="wm-teams-empty">No hay datos de selecciones disponibles todavía.</div>
  }
  return (
    <div className="wm-teams-ranking">
      <div className="wm-teams-ranking__header" aria-hidden="true">
        <span>Pos.</span>
        <span>Selección</span>
        <span>Goles</span>
        <span>Jugadores</span>
        <span>Pts SFA</span>
      </div>
      {teams.map((team) => {
        const fakeTeam = { name: team.team_name, external_id: team.team_external_id }
        const displayName = worldCupTeamName(fakeTeam as WcFixture['home_team'])
        const logo = `https://media.api-sports.io/football/teams/${team.team_external_id}.png`
        return (
          <Link
            key={team.team_external_id}
            to={`/mundial/seleccion/${team.team_external_id}`}
            className={`wm-teams-ranking__row${team.rank <= 3 ? ` wm-teams-ranking__row--top${team.rank}` : ''}`}
          >
            <span className="wm-teams-ranking__rank">{team.rank}</span>
            <span className="wm-teams-ranking__team">
              <img
                src={logo}
                alt=""
                className="wm-teams-ranking__logo"
                loading="lazy"
                onError={(e) => { e.currentTarget.style.visibility = 'hidden' }}
              />
              <span>{displayName}</span>
            </span>
            <span className="wm-teams-ranking__goals">{team.total_goals}</span>
            <span className="wm-teams-ranking__players">{team.player_count}</span>
            <span className="wm-teams-ranking__pts">
              {team.total_sfa_pts.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
              <small>pts</small>
            </span>
          </Link>
        )
      })}
    </div>
  )
}

export default function MundialPage() {
  const navigate = useNavigate()
  const [fixturesData, setFixturesData] = useState<WcFixturesResponse | null>(null)
  const [standingsData, setStandingsData] = useState<WcStandingsResponse | null>(null)
  const [teamsRanking, setTeamsRanking] = useState<WcTeamSFARankingItem[]>([])
  const [view, setView] = useState<MundialView>('matches')
  const [resultDate, setResultDate] = useState<string | null>(null)
  const [upcomingDate, setUpcomingDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

  useEffect(() => {
    Promise.all([fetchWcFixtures(), fetchWcStandings()])
      .then(([fixtures, standings]) => {
        setFixturesData(fixtures)
        setStandingsData(standings)
      })
      .catch((requestError) => setError(requestError.message ?? 'Error al cargar el Mundial'))
      .finally(() => setLoading(false))

    fetchWcTeamSFARanking()
      .then((teamsData) => setTeamsRanking(teamsData.rankings))
      .catch(() => setTeamsRanking([]))
  }, [])

  useEffect(() => {
    function refreshLive() {
      fetchWcFixtures(true)
        .then(setFixturesData)
        .catch(() => {})
    }

    const timer = setInterval(refreshLive, 120_000)
    return () => clearInterval(timer)
  }, [])

  const fixtures = fixturesData?.fixtures ?? []
  const live = fixtures.filter((fixture) => fixture.is_live)
  const allResults = fixtures
    .filter((fixture) => FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
  const allUpcoming = fixtures
    .filter((fixture) => !fixture.is_live && !FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())
  const resultDates = uniqueDateOptions(allResults, 'desc')
  const upcomingDates = uniqueDateOptions(allUpcoming, 'asc')
  const selectedResultDate = resultDate ?? resultDates[0]?.key ?? ''
  const selectedUpcomingDate = upcomingDate ?? upcomingDates[0]?.key ?? ''
  const results = allResults
    .filter((fixture) => dateKey(fixture.played_at) === selectedResultDate)
    .slice(0, 10)
  const upcoming = allUpcoming
    .filter((fixture) => dateKey(fixture.played_at) === selectedUpcomingDate)
    .slice(0, 10)
  const spotlightFixture = live[0] ?? allUpcoming[0] ?? allResults[0] ?? null
  const knockoutFixtures = fixtures.filter(isKnockout)

  const standingsByGroup = useMemo(() => {
    const groups = new Map<string, WcStanding[]>()
    for (const standing of standingsData?.standings ?? []) {
      const group = groups.get(standing.group) ?? []
      group.push(standing)
      groups.set(standing.group, group)
    }
    for (const rows of groups.values()) rows.sort((a, b) => a.position - b.position)
    return groups
  }, [standingsData])

  function goBack() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1)
      return
    }
    navigate('/ranking?season=2026')
  }

  return (
    <div className="mundial-page">
      <header className="wm-hero">
        <div className="wm-hero__pattern" aria-hidden="true" />
        <div className="wm-hero__content">
          <div>
            <button type="button" className="wm-hero__back" onClick={goBack}>
              <span aria-hidden="true">←</span>
              Volver
            </button>
            <span className="wm-hero__eyebrow">Stats Football Award · Edición Mundial</span>
            <h1><span>Mundial</span> <strong>2026</strong></h1>
            <p className="wm-hero__description">
              Sigue los partidos, la clasificación y el camino hacia la final.
              SFA mide qué jugadores generan mayor impacto real durante el torneo.
            </p>
            <div className="wm-hero__actions">
              <Link to="/ranking" className="wm-hero__ranking-link">
                Ver ranking de jugadores
                <span aria-hidden="true">→</span>
              </Link>
              <span>Ranking independiente · Todos comienzan en cero</span>
            </div>
          </div>
        </div>
      </header>

      <nav className="wm-tabs" aria-label="Secciones del Mundial">
        {([
          ['matches', 'Partidos'],
          ['standings', 'Grupos'],
          ['bracket', 'Cruces'],
          ['teams', 'Selecciones'],
        ] as const).map(([id, label]) => (
          <button
            type="button"
            key={id}
            className={`wm-tab${view === id ? ' wm-tab--active' : ''}`}
            onClick={() => setView(id)}
            aria-pressed={view === id}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="wm-dashboard">
        {loading && (
          <div className="wm-dashboard__loading">
            {Array.from({ length: 6 }).map((_, index) => (
              <div className="skeleton wm-match-skeleton" key={index} />
            ))}
          </div>
        )}

        {!loading && error && <div className="empty-state">{error}</div>}

        {!loading && !error && view === 'matches' && (
          <>
            {spotlightFixture && <SpotlightMatch fixture={spotlightFixture} />}

            <div className="wm-scoreboard-layout">
              <section className="wm-section wm-scoreboard-panel">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Marcadores</span>
                    <h2>Resultados</h2>
                  </div>
                </header>
                <DateRail
                  label="Elegir fecha de resultados"
                  dates={resultDates}
                  value={selectedResultDate}
                  onChange={setResultDate}
                />
                {results.length > 0 ? (
                  <div className="wm-score-stack">
                    {results.map((fixture) => (
                      <ScorePill fixture={fixture} tone="result" key={fixture.id} />
                    ))}
                  </div>
                ) : (
                  <div className="wm-score-empty">No hay resultados para esta fecha.</div>
                )}
              </section>

              <section className="wm-section wm-scoreboard-panel">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Calendario</span>
                    <h2>Próximos partidos</h2>
                  </div>
                </header>
                <DateRail
                  label="Elegir fecha de próximos partidos"
                  dates={upcomingDates}
                  value={selectedUpcomingDate}
                  onChange={setUpcomingDate}
                />
                {upcoming.length > 0 ? (
                  <div className="wm-score-stack">
                    {upcoming.map((fixture) => (
                      <ScorePill fixture={fixture} tone="upcoming" key={fixture.id} />
                    ))}
                  </div>
                ) : (
                  <div className="wm-score-empty">No hay partidos programados para esta fecha.</div>
                )}
              </section>
            </div>
          </>
        )}

        {!loading && !error && view === 'standings' && (
          <div className="wm-groups">
            {Array.from(standingsByGroup.entries()).map(([group, rows]) => (
              <StandingsGroup group={group} rows={rows} key={group} />
            ))}
          </div>
        )}

        {!loading && !error && view === 'teams' && (
          <section className="wm-section">
            <header className="wm-section__header">
              <div>
                <span className="wm-section__eyebrow">Stats Football Award</span>
                <h2>Ranking por selección</h2>
              </div>
            </header>
            <TeamSFARankingView teams={teamsRanking} />
          </section>
        )}

        {!loading && !error && view === 'bracket' && (
          knockoutFixtures.length > 0 ? (
            <div className="wm-bracket">
              {knockoutFixtures.map((fixture) => (
                <FixtureCard fixture={fixture} key={fixture.id} />
              ))}
            </div>
          ) : (
            <div className="wm-bracket-empty">
              <span>Fase eliminatoria</span>
              <h2>Los cruces todavía no están definidos</h2>
              <p>
                El cuadro aparecerá aquí cuando se publiquen los clasificados y los
                partidos de dieciseisavos.
              </p>
            </div>
          )
        )}
      </main>
    </div>
  )
}
