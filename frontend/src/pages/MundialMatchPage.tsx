import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchWcFixtureDetail } from '../api/client'
import type {
  WcFixture,
  WcFixtureDetailResponse,
  WcLineupPlayer,
  WcStatistic,
  WcTeam,
  WcTeamLineup,
} from '../types'
import { worldCupTeamName } from '../utils/worldCupTeams'

type DetailTab = 'lineups' | 'statistics'

const TEAM_LOGO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/teams/${externalId}.png` : null

const PLAYER_PHOTO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/players/${externalId}.png` : null

const FINISHED_STATUSES = new Set(['FT', 'AET', 'PEN'])

const STAT_LABELS_ES: Record<string, string> = {
  'Ball Possession': 'Posesión',
  'Total Shots': 'Remates',
  'Shots on Goal': 'Remates al arco',
  'Shots off Goal': 'Remates fuera',
  'Blocked Shots': 'Remates bloqueados',
  'Corner Kicks': 'Tiros de esquina',
  Fouls: 'Faltas',
  Offsides: 'Fuera de juego',
  'Yellow Cards': 'Tarjetas amarillas',
  'Red Cards': 'Tarjetas rojas',
  'Goalkeeper Saves': 'Atajadas',
  'Total passes': 'Pases',
  'Passes accurate': 'Pases completados',
  'Passes %': 'Precisión de pase',
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function TeamIdentity({ team }: { team: WcTeam }) {
  const logo = TEAM_LOGO(team.external_id)
  return (
    <div className="wmd-team">
      {logo && <img src={logo} alt="" className="wmd-team__logo" />}
      <strong>{worldCupTeamName(team)}</strong>
    </div>
  )
}

function matchStatus(fixture: WcFixture): string {
  if (fixture.is_live) {
    return fixture.status === 'HT' ? 'Descanso' : `${fixture.elapsed ?? ''}' En vivo`
  }
  if (FINISHED_STATUSES.has(fixture.status)) return 'Finalizado'
  return `${formatDate(fixture.played_at)} · ${formatTime(fixture.played_at)}`
}

function PlayerRow({ player }: { player: WcLineupPlayer }) {
  const content = (
    <>
      <span className="wmd-player__number">{player.number ?? '—'}</span>
      <span className="wmd-player__name">{player.name}</span>
      {player.sfa_points != null ? (
        <strong className="wmd-player__points">
          {Math.round(player.sfa_points).toLocaleString('es-ES')} pts
        </strong>
      ) : player.position ? <small>{player.position}</small> : null}
    </>
  )

  if (player.player_id != null) {
    return (
      <Link className="wmd-player wmd-player--link" to={`/player/${player.player_id}?season=2026`}>
        {content}
      </Link>
    )
  }

  return (
    <div className="wmd-player">
      {content}
    </div>
  )
}

function playerGridPosition(
  player: WcLineupPlayer,
  players: WcLineupPlayer[],
  side: 'home' | 'away',
) {
  const parsed = players
    .map((item) => item.grid?.split(':').map(Number))
    .filter((value): value is number[] => Boolean(
      value && value.length === 2 && value.every(Number.isFinite),
    ))
  const current = player.grid?.split(':').map(Number)
  if (!current || current.length !== 2 || !current.every(Number.isFinite)) return null

  const maxRow = Math.max(...parsed.map(([row]) => row), 1)
  const rowPlayers = parsed.filter(([row]) => row === current[0])
  const maxColumn = Math.max(...rowPlayers.map(([, column]) => column), 1)
  const progress = (current[0] - 1) / Math.max(maxRow - 1, 1)
  return {
    left: `${side === 'home' ? 7 + progress * 39 : 93 - progress * 39}%`,
    top: `${(current[1] / (maxColumn + 1)) * 100}%`,
  }
}

function shortPlayerName(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts.length > 1 ? parts[parts.length - 1] : name
}

function teamColor(externalId: number | null): string {
  const colors = ['#d33f49', '#2878d0', '#15965b', '#d39b20', '#7b57c7', '#b64b86']
  return colors[Math.abs(externalId ?? 0) % colors.length]
}

function PitchPlayer({
  player,
  players,
  side,
  teamColorValue,
  index,
}: {
  player: WcLineupPlayer
  players: WcLineupPlayer[]
  side: 'home' | 'away'
  teamColorValue: string
  index: number
}) {
  const position = playerGridPosition(player, players, side)
  if (!position) return null
  const photo = PLAYER_PHOTO(player.external_id)
  const node = (
    <>
      <span
        className="wmd-pitch-player__portrait"
        style={{ '--team-color': teamColorValue } as CSSProperties}
      >
        {photo && (
          <img
            src={photo}
            alt=""
            onError={(event) => {
              event.currentTarget.style.display = 'none'
            }}
          />
        )}
        <b>{player.number ?? index + 1}</b>
      </span>
      <small>{player.number ?? index + 1} {shortPlayerName(player.name)}</small>
      {player.sfa_points != null && (
        <strong>{Math.round(player.sfa_points).toLocaleString('es-ES')}</strong>
      )}
    </>
  )

  return player.player_id != null ? (
    <Link
      to={`/player/${player.player_id}?season=2026`}
      className="wmd-pitch-player wmd-pitch-player--link"
      style={position}
    >
      {node}
    </Link>
  ) : (
    <div className="wmd-pitch-player" style={position}>
      {node}
    </div>
  )
}

function CombinedTacticalPitch({
  homeLineup,
  awayLineup,
}: {
  homeLineup: WcTeamLineup
  awayLineup: WcTeamLineup
}) {
  const homeColor = teamColor(homeLineup.team.external_id)
  const awayColor = teamColor(awayLineup.team.external_id)

  return (
    <section className="wmd-combined-tactical">
      <header className="wmd-formation-bar">
        <div>
          <span style={{ backgroundColor: homeColor }} />
          <strong>{homeLineup.formation ?? '—'}</strong>
          <small>{worldCupTeamName(homeLineup.team)}</small>
        </div>
        <b>Formación</b>
        <div>
          <small>{worldCupTeamName(awayLineup.team)}</small>
          <strong>{awayLineup.formation ?? '—'}</strong>
          <span style={{ backgroundColor: awayColor }} />
        </div>
      </header>
      <div className="wmd-pitch wmd-pitch--combined">
        <div className="wmd-pitch__markings" aria-hidden="true">
          <i className="wmd-pitch__halfway" />
          <i className="wmd-pitch__circle" />
          <i className="wmd-pitch__box wmd-pitch__box--left" />
          <i className="wmd-pitch__box wmd-pitch__box--right" />
        </div>
        {homeLineup.start_xi.map((player, index) => (
          <PitchPlayer
            player={player}
            players={homeLineup.start_xi}
            side="home"
            teamColorValue={homeColor}
            index={index}
            key={`home-${player.external_id ?? player.name}-${index}`}
          />
        ))}
        {awayLineup.start_xi.map((player, index) => (
          <PitchPlayer
            player={player}
            players={awayLineup.start_xi}
            side="away"
            teamColorValue={awayColor}
            index={index}
            key={`away-${player.external_id ?? player.name}-${index}`}
          />
        ))}
      </div>
    </section>
  )
}

function LineupColumn({ lineup }: { lineup: WcTeamLineup }) {
  return (
    <section className="wmd-lineup">
      <header className="wmd-lineup__header">
        <TeamIdentity team={lineup.team} />
        <div>
          <span>{lineup.formation ?? 'Formación pendiente'}</span>
          <small>{lineup.coach_name ? `DT · ${lineup.coach_name}` : 'Entrenador pendiente'}</small>
        </div>
      </header>
      <h3>Titulares</h3>
      <div className="wmd-player-list">
        {lineup.start_xi.map((player, index) => (
          <PlayerRow player={player} key={`${player.external_id ?? player.name}-${index}`} />
        ))}
      </div>
      {lineup.substitutes.length > 0 && (
        <>
          <h3>Suplentes</h3>
          <div className="wmd-player-list wmd-player-list--subs">
            {lineup.substitutes.map((player, index) => (
              <PlayerRow player={player} key={`${player.external_id ?? player.name}-${index}`} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

function StatisticRow({ statistic }: { statistic: WcStatistic }) {
  const home = statistic.home_numeric ?? 0
  const away = statistic.away_numeric ?? 0
  const total = home + away
  const homeWidth = total > 0 ? (home / total) * 100 : 50

  return (
    <div className="wmd-stat">
      <div className="wmd-stat__values">
        <strong>{statistic.home_value ?? '—'}</strong>
        <span>{STAT_LABELS_ES[statistic.label] ?? statistic.label}</span>
        <strong>{statistic.away_value ?? '—'}</strong>
      </div>
      <div className="wmd-stat__track">
        <i style={{ width: `${homeWidth}%` }} />
      </div>
    </div>
  )
}

export default function MundialMatchPage() {
  const navigate = useNavigate()
  const { fixtureId } = useParams<{ fixtureId: string }>()
  const [detail, setDetail] = useState<WcFixtureDetailResponse | null>(null)
  const [tab, setTab] = useState<DetailTab>('lineups')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

  useEffect(() => {
    const id = Number(fixtureId)
    if (!Number.isFinite(id)) {
      setError('Partido no válido.')
      setLoading(false)
      return
    }
    fetchWcFixtureDetail(id)
      .then(setDetail)
      .catch((requestError) => setError(requestError.message ?? 'No se pudo cargar el partido.'))
      .finally(() => setLoading(false))
  }, [fixtureId])

  const lineupByTeam = useMemo(() => {
    const result = new Map<number, WcTeamLineup>()
    for (const lineup of detail?.lineups ?? []) result.set(lineup.team.external_id ?? lineup.team.id, lineup)
    return result
  }, [detail])

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
      <div className="wmd-page">
        <div className="skeleton wmd-skeleton" />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="wmd-page">
        <button type="button" className="wm-hero__back" onClick={goBack}>
          <span aria-hidden="true">←</span> Volver al Mundial
        </button>
        <div className="empty-state">{error ?? 'Partido no encontrado.'}</div>
      </div>
    )
  }

  const { fixture } = detail
  const homeLineup = lineupByTeam.get(fixture.home_team.external_id ?? fixture.home_team.id)
  const awayLineup = lineupByTeam.get(fixture.away_team.external_id ?? fixture.away_team.id)
  const venueText = [detail.venue.name, detail.venue.city].filter(Boolean).join(' · ')

  return (
    <div className="wmd-page">
      <button type="button" className="wm-hero__back wmd-back" onClick={goBack}>
        <span aria-hidden="true">←</span> Volver al Mundial
      </button>

      <header className="wmd-scoreboard">
        <div className="wmd-scoreboard__spectrum" />
        <span className="wmd-scoreboard__stage">{fixture.stage.replace('Group Stage', 'Fase de grupos')}</span>
        <div className="wmd-scoreboard__match">
          <TeamIdentity team={fixture.home_team} />
          <div className="wmd-scoreboard__score">
            <strong>
              {fixture.home_goals ?? '—'} <span>:</span> {fixture.away_goals ?? '—'}
            </strong>
            <small className={fixture.is_live ? 'wmd-scoreboard__live' : ''}>{matchStatus(fixture)}</small>
          </div>
          <TeamIdentity team={fixture.away_team} />
        </div>
        <div className="wmd-scoreboard__meta">
          <span>{venueText || 'Estadio por confirmar'}</span>
          <span>{detail.referee ? `Árbitro · ${detail.referee}` : 'Árbitro por confirmar'}</span>
        </div>
      </header>

      <nav className="wmd-tabs" aria-label="Detalle del partido">
        {([
          ['lineups', 'Alineaciones'],
          ['statistics', 'Estadísticas'],
        ] as const).map(([id, label]) => (
          <button
            type="button"
            key={id}
            className={`wmd-tab${tab === id ? ' wmd-tab--active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="wmd-content">
        {tab === 'lineups' && (
          detail.lineups.length > 0 ? (
            <>
              {homeLineup && awayLineup && (
                <CombinedTacticalPitch homeLineup={homeLineup} awayLineup={awayLineup} />
              )}
              <div className="wmd-lineups-heading">
                <span>Alineaciones completas</span>
                <small>Los puntos SFA aparecen cuando el partido ya fue procesado.</small>
              </div>
              <div className="wmd-lineups-grid">
                {homeLineup && <LineupColumn lineup={homeLineup} />}
                {awayLineup && <LineupColumn lineup={awayLineup} />}
              </div>
            </>
          ) : <div className="empty-state">Las alineaciones todavía no fueron publicadas.</div>
        )}

        {tab === 'statistics' && (
          detail.statistics.length > 0 ? (
            <section className="wmd-panel wmd-statistics">
              <div className="wmd-statistics__teams">
                <strong>{worldCupTeamName(fixture.home_team)}</strong>
                <span>Comparación</span>
                <strong>{worldCupTeamName(fixture.away_team)}</strong>
              </div>
              {detail.statistics.map((statistic) => (
                <StatisticRow statistic={statistic} key={statistic.label} />
              ))}
            </section>
          ) : <div className="empty-state">Las estadísticas estarán disponibles cuando comience el partido.</div>
        )}
      </main>
    </div>
  )
}
