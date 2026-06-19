import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchWcFixtures, fetchWcStandings, fetchWcTeamProfile } from '../api/client'
import type { WcFixture, WcFixturesResponse, WcStanding, WcStandingsResponse, WcTeam, WcTeamProfileResponse, WcTopPlayer } from '../types'
import { worldCupTeamName, worldCupTeamNameFromString } from '../utils/worldCupTeams'

const TEAM_LOGO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/teams/${externalId}.png` : null

const FINISHED_STATUSES = new Set(['FT', 'AET', 'PEN'])

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fixtureIncludesTeam(fixture: WcFixture, teamId: number): boolean {
  return fixture.home_team.external_id === teamId || fixture.away_team.external_id === teamId
}

function TeamFixtureRow({ fixture, teamId }: { fixture: WcFixture; teamId: number }) {
  const homeName = worldCupTeamName(fixture.home_team)
  const awayName = worldCupTeamName(fixture.away_team)
  const isHome = fixture.home_team.external_id === teamId
  const opponent = isHome ? fixture.away_team : fixture.home_team
  const opponentLogo = TEAM_LOGO(opponent.external_id)
  const hasScore = fixture.home_goals != null && fixture.away_goals != null
  const finished = FINISHED_STATUSES.has(fixture.status)

  return (
    <Link to={`/mundial/partido/${fixture.external_id}`} className="wmt-fixture">
      <span className="wmt-fixture__stage">{fixture.stage.replace('Group Stage', 'Fase de grupos')}</span>
      <span className="wmt-fixture__opponent">
        {opponentLogo && <img src={opponentLogo} alt="" loading="lazy" decoding="async" />}
        <strong>{worldCupTeamName(opponent)}</strong>
      </span>
      <span className="wmt-fixture__score">
        {hasScore ? `${fixture.home_goals} - ${fixture.away_goals}` : 'vs'}
        <small>{finished ? 'Final' : fixture.is_live ? `${fixture.elapsed ?? ''}'` : formatDate(fixture.played_at)}</small>
      </span>
      <span className="wmt-fixture__full">{homeName} vs {awayName}</span>
    </Link>
  )
}

function TeamPlayerRow({ player }: { player: WcTopPlayer }) {
  return (
    <Link to={`/player/${player.player_id}?season=2026`} className="wmt-player">
      <span className="wmt-player__rank">{String(player.rank).padStart(2, '0')}</span>
      {player.photo_url && <img src={player.photo_url} alt="" loading="lazy" decoding="async" />}
      <span>
        <strong>{player.player_name}</strong>
        <small>{player.position} · {player.goals} G · {player.assists} A</small>
      </span>
      <b>{Math.round(player.total_pts).toLocaleString('es-ES')} pts</b>
    </Link>
  )
}

export default function MundialTeamPage() {
  const navigate = useNavigate()
  const { teamId } = useParams<{ teamId: string }>()
  const numericTeamId = Number(teamId)
  const [fixturesData, setFixturesData] = useState<WcFixturesResponse | null>(null)
  const [standingsData, setStandingsData] = useState<WcStandingsResponse | null>(null)
  const [teamProfile, setTeamProfile] = useState<WcTeamProfileResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

  useEffect(() => {
    if (!Number.isFinite(numericTeamId)) {
      setError('Selección no válida.')
      setLoading(false)
      return
    }

    Promise.all([
      fetchWcFixtures(),
      fetchWcStandings(),
      fetchWcTeamProfile(numericTeamId).catch(() => null),
    ])
      .then(([fixtures, standings, profile]) => {
        setFixturesData(fixtures)
        setStandingsData(standings)
        setTeamProfile(profile)
      })
      .catch((requestError) => setError(requestError.message ?? 'No se pudo cargar la selección.'))
      .finally(() => setLoading(false))
  }, [numericTeamId])

  const team = useMemo<WcTeam | null>(() => {
    if (!Number.isFinite(numericTeamId)) return null
    for (const fixture of fixturesData?.fixtures ?? []) {
      if (fixture.home_team.external_id === numericTeamId) return fixture.home_team
      if (fixture.away_team.external_id === numericTeamId) return fixture.away_team
    }
    const standingTeam = standingsData?.standings.find((standing) => standing.team.external_id === numericTeamId)?.team
    return standingTeam ?? null
  }, [fixturesData, numericTeamId, standingsData])

  const teamName = team ? worldCupTeamName(team) : 'Selección'
  const normalizedTeamName = worldCupTeamNameFromString(teamName).toLowerCase()
  const teamFixtures = (fixturesData?.fixtures ?? [])
    .filter((fixture) => fixtureIncludesTeam(fixture, numericTeamId))
    .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())
  const upcoming = teamFixtures.filter((fixture) => !fixture.is_live && !FINISHED_STATUSES.has(fixture.status)).slice(0, 4)
  const results = teamFixtures.filter((fixture) => FINISHED_STATUSES.has(fixture.status)).slice(-4).reverse()
  const standing = standingsData?.standings.find((row) => row.team.external_id === numericTeamId) ?? null
  const bestPlayers = teamProfile?.top_players.slice(0, 8) ?? []
  const logo = TEAM_LOGO(team?.external_id ?? null)

  function goBack() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1)
      return
    }
    navigate('/mundial')
  }

  if (loading) {
    return (
      <div className="wmt-page">
        <div className="skeleton wmd-skeleton" />
      </div>
    )
  }

  if (error || !team) {
    return (
      <div className="wmt-page">
        <button type="button" className="wm-hero__back wmd-back" onClick={goBack}>
          <span aria-hidden="true">←</span> Volver al Mundial
        </button>
        <div className="empty-state">{error ?? 'Selección no encontrada.'}</div>
      </div>
    )
  }

  return (
    <div className="wmt-page">
      <button type="button" className="wm-hero__back wmd-back" onClick={goBack}>
        <span aria-hidden="true">←</span> Volver al Mundial
      </button>

      <header className="wmt-hero">
        <div className="wmt-hero__spectrum" />
        {logo && <img src={logo} alt="" className="wmt-hero__logo" decoding="async" />}
        <div>
          <span>SFA · Edición Mundial</span>
          <h1>{teamName}</h1>
          <p>Perfil de selección: calendario, clasificación y mejores jugadores por puntos SFA.</p>
        </div>
        {standing && (
          <dl className="wmt-hero__standing">
            <div><dt>Grupo</dt><dd>{standing.group.replace('Group', 'Grupo')}</dd></div>
            <div><dt>Pos.</dt><dd>{standing.position}</dd></div>
            <div><dt>Pts</dt><dd>{standing.points}</dd></div>
          </dl>
        )}
      </header>

      <main className="wmt-grid">
        <section className="wmt-panel">
          <header><span>Calendario</span><h2>Próximos partidos</h2></header>
          <div className="wmt-list">
            {upcoming.length > 0
              ? upcoming.map((fixture) => <TeamFixtureRow fixture={fixture} teamId={numericTeamId} key={fixture.id} />)
              : <div className="wmt-empty">Sin próximos partidos publicados.</div>}
          </div>
        </section>

        <section className="wmt-panel">
          <header><span>Marcadores</span><h2>Resultados</h2></header>
          <div className="wmt-list">
            {results.length > 0
              ? results.map((fixture) => <TeamFixtureRow fixture={fixture} teamId={numericTeamId} key={fixture.id} />)
              : <div className="wmt-empty">Todavía no hay resultados.</div>}
          </div>
        </section>

        <section className="wmt-panel wmt-panel--players">
          <header><span>Rendimiento</span><h2>Mejores jugadores SFA</h2></header>
          <div className="wmt-list">
            {bestPlayers.length > 0
              ? bestPlayers.map((player) => <TeamPlayerRow player={player} key={player.player_id} />)
              : <div className="wmt-empty">Los jugadores aparecerán cuando el ranking del Mundial tenga datos de esta selección.</div>}
          </div>
        </section>
      </main>
    </div>
  )
}
