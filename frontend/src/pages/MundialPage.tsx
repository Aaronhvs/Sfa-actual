import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import type {
  WcFixture,
  WcFixturesResponse,
  WcStanding,
  WcStandingsResponse,
} from '../types'
import { fetchWcFixtures, fetchWcLive, fetchWcStandings } from '../api/client'
import { worldCupTeamName } from '../utils/worldCupTeams'

type MundialView = 'matches' | 'standings' | 'bracket'

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
      <div className="wm-match__stage">{fixture.stage.replace('Group Stage', 'Fase de grupos')}</div>

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
        <div className="wm-standing-row" key={row.team.external_id}>
          <span className="wm-standing-row__position">{row.position}</span>
          <TeamLogo team={row.team} className="wm-standing-row__logo" />
          <strong>{worldCupTeamName(row.team)}</strong>
          <span>{row.played}</span>
          <span>{row.goal_difference > 0 ? '+' : ''}{row.goal_difference}</span>
          <b>{row.points}</b>
        </div>
      ))}
    </section>
  )
}

export default function MundialPage() {
  const navigate = useNavigate()
  const [fixturesData, setFixturesData] = useState<WcFixturesResponse | null>(null)
  const [standingsData, setStandingsData] = useState<WcStandingsResponse | null>(null)
  const [view, setView] = useState<MundialView>('matches')
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
  }, [])

  useEffect(() => {
    function refreshLive() {
      fetchWcFixtures(true)
        .then(setFixturesData)
        .catch(() => {})
    }

    const timer = setInterval(refreshLive, 60_000)
    return () => clearInterval(timer)
  }, [])

  const fixtures = fixturesData?.fixtures ?? []
  const live = fixtures.filter((fixture) => fixture.is_live)
  const results = fixtures
    .filter((fixture) => FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
    .slice(0, 8)
  const upcoming = fixtures
    .filter((fixture) => !fixture.is_live && !FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())
    .slice(0, 8)
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
            {live.length > 0 && (
              <section className="wm-section wm-section--live">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Ahora</span>
                    <h2>En vivo</h2>
                  </div>
                  <span className="wm-section__live-count">{live.length} en juego</span>
                </header>
                <div className="wm-live-grid">
                  {live.map((fixture) => <FixtureCard fixture={fixture} key={fixture.id} />)}
                </div>
              </section>
            )}

            <div className="wm-match-columns">
              <section className="wm-section">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Marcadores</span>
                    <h2>Resultados</h2>
                  </div>
                </header>
                <div className="wm-match-list">
                  {results.map((fixture) => (
                    <FixtureCard fixture={fixture} compact key={fixture.id} />
                  ))}
                </div>
              </section>

              <section className="wm-section">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Calendario</span>
                    <h2>Próximos partidos</h2>
                  </div>
                </header>
                <div className="wm-match-list">
                  {upcoming.map((fixture) => (
                    <FixtureCard fixture={fixture} compact key={fixture.id} />
                  ))}
                </div>
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
