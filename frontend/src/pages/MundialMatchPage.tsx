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
import MatchTimeline from '../components/mundial/MatchTimeline'
import { worldCupTeamName } from '../utils/worldCupTeams'

type DetailTab = 'lineups' | 'statistics' | 'performance'

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

function TeamIdentity({ team, asLink = false }: { team: WcTeam; asLink?: boolean }) {
  const logo = TEAM_LOGO(team.external_id)
  const content = (
    <>
      {logo && (
        <img
          src={logo}
          alt=""
          className="wmd-team__logo"
          decoding="async"
        />
      )}
      <strong>{worldCupTeamName(team)}</strong>
    </>
  )

  if (asLink && team.external_id != null) {
    return (
      <Link className="wmd-team wmd-team--link" to={`/mundial/seleccion/${team.external_id}`}>
        {content}
      </Link>
    )
  }

  return (
    <div className="wmd-team">
      {content}
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

function PlayerRow({ player, color }: { player: WcLineupPlayer; color: string }) {
  const photo = PLAYER_PHOTO(player.external_id)
  const style = { '--team-color': color } as React.CSSProperties
  const content = (
    <>
      <span className="wmd-player__avatar">
        {photo && (
          <img
            src={photo}
            alt=""
            loading="lazy"
            decoding="async"
            onError={(event) => {
              event.currentTarget.style.display = 'none'
            }}
          />
        )}
        <b className="wmd-player__number">{player.number ?? '-'}</b>
      </span>
      <span className="wmd-player__name">{player.name}</span>
      {player.sfa_points != null ? (
        <strong className="wmd-player__points">
          {Math.round(player.sfa_points).toLocaleString('es-ES')} pts
        </strong>
      ) : (
        <strong className="wmd-player__points">Pend.</strong>
      )}
    </>
  )

  if (player.player_id != null) {
    return (
      <Link className="wmd-player wmd-player--link" style={style} to={`/player/${player.player_id}?season=2026`}>
        {content}
      </Link>
    )
  }

  return (
    <div className="wmd-player" style={style}>
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

const NATIONAL_COLORS: Record<string, string> = {
  'argentina': '#75AADB',
  'brasil': '#009C3B',
  'brazil': '#009C3B',
  'alemania': '#CC0000',
  'germany': '#CC0000',
  'francia': '#002395',
  'france': '#002395',
  'españa': '#AA151B',
  'spain': '#AA151B',
  'inglaterra': '#CF081F',
  'england': '#CF081F',
  'países bajos': '#FF6B00',
  'holanda': '#FF6B00',
  'netherlands': '#FF6B00',
  'portugal': '#006600',
  'estados unidos': '#002868',
  'usa': '#002868',
  'méxico': '#006847',
  'mexico': '#006847',
  'suiza': '#DA291C',
  'switzerland': '#DA291C',
  'bosnia y herzegovina': '#003DA5',
  'bosnia': '#003DA5',
  'canadá': '#FF0000',
  'canada': '#FF0000',
  'japón': '#BC002D',
  'japan': '#BC002D',
  'marruecos': '#C1272D',
  'morocco': '#C1272D',
  'senegal': '#00853F',
  'ghana': '#FCD116',
  'panamá': '#DA121A',
  'panama': '#DA121A',
  'colombia': '#FCD116',
  'ecuador': '#002D62',
  'chile': '#D52B1E',
  'uruguay': '#75AADB',
  'bélgica': '#EF3340',
  'belgium': '#EF3340',
  'croacia': '#FF0000',
  'croatia': '#FF0000',
  'dinamarca': '#C60C30',
  'denmark': '#C60C30',
  'austria': '#ED2939',
  'australia': '#00843D',
  'corea del sur': '#CD2E3A',
  'irán': '#239F40',
  'iran': '#239F40',
  'qatar': '#8D1B3D',
  'arabia saudita': '#006C35',
  'arabia saudí': '#006C35',
  'venezuela': '#CF142B',
  'paraguay': '#D52B1E',
  'honduras': '#0073CF',
  'costa rica': '#002B7F',
  'nigeria': '#008751',
  'camerún': '#007A5E',
  'costa de marfil': '#F77F00',
  'egipto': '#CE1126',
  'turquía': '#E30A17',
  'turkey': '#E30A17',
  'ucrania': '#005BBB',
  'ukraine': '#005BBB',
  'serbia': '#C6363C',
  'rumania': '#002B7F',
  'eslovaquia': '#0B4EA2',
  'georgia': '#DA291C',
  'escocia': '#003380',
  'scotland': '#003380',
  'indonesia': '#CE1126',
  'irak': '#007A3D',
  'iraq': '#007A3D',
  'nueva zelanda': '#00247D',
  'new zealand': '#00247D',
}

function teamColor(name: string | null, externalId: number | null): string {
  if (name) {
    const key = name.toLowerCase().trim()
    const mapped = NATIONAL_COLORS[key]
    if (mapped) return mapped
  }
  const fallback = ['#d33f49', '#2878d0', '#15965b', '#d39b20', '#7b57c7', '#b64b86']
  return fallback[Math.abs(externalId ?? 0) % fallback.length]
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
      <span className="wmd-pitch-player__portrait">
        {photo && (
          <img
            src={photo}
            alt=""
            loading="lazy"
            decoding="async"
            onError={(event) => {
              event.currentTarget.style.display = 'none'
            }}
          />
        )}
      </span>
      <b className="wmd-pitch-player__num">{player.number ?? index + 1}</b>
      <small>{shortPlayerName(player.name)}</small>
      {player.sfa_points != null && (
        <strong>{Math.round(player.sfa_points).toLocaleString('es-ES')}</strong>
      )}
    </>
  )

  const playerStyle = { ...position, '--team-color': teamColorValue } as CSSProperties

  return player.player_id != null ? (
    <Link
      to={`/player/${player.player_id}?season=2026`}
      className="wmd-pitch-player wmd-pitch-player--link"
      style={playerStyle}
    >
      {node}
    </Link>
  ) : (
    <div className="wmd-pitch-player" style={playerStyle}>
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
  const homeColor = teamColor(homeLineup.team.name, homeLineup.team.external_id)
  const awayColor = teamColor(awayLineup.team.name, awayLineup.team.external_id)

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

function LineupColumn({ lineup, color }: { lineup: WcTeamLineup; color: string }) {
  return (
    <section className="wmd-lineup">
      <header className="wmd-lineup__header">
        <TeamIdentity team={lineup.team} asLink />
        <div>
          <span>{lineup.formation ?? 'Formación pendiente'}</span>
          <small>{lineup.coach_name ? `DT · ${lineup.coach_name}` : 'Entrenador pendiente'}</small>
        </div>
      </header>
      <h3>Titulares</h3>
      <div className="wmd-player-list">
        {lineup.start_xi.map((player, index) => (
          <PlayerRow player={player} color={color} key={`${player.external_id ?? player.name}-${index}`} />
        ))}
      </div>
      {lineup.substitutes.length > 0 && (
        <>
          <h3>Suplentes</h3>
          <div className="wmd-player-list wmd-player-list--subs">
            {lineup.substitutes.map((player, index) => (
              <PlayerRow player={player} color={color} key={`${player.external_id ?? player.name}-${index}`} />
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

function PlayerPerformancePanel({ lineups }: { lineups: WcTeamLineup[] }) {
  const players = lineups
    .flatMap((lineup) => (
      [...lineup.start_xi, ...lineup.substitutes].map((player) => ({
        player,
        team: lineup.team,
        isStarter: lineup.start_xi.includes(player),
      }))
    ))
    .sort((a, b) => (b.player.sfa_points ?? -1) - (a.player.sfa_points ?? -1))

  if (players.length === 0) {
    return <div className="empty-state">Todavia no hay rendimiento individual disponible.</div>
  }

  return (
    <section className="wmd-panel wmd-performance">
      <header className="wmd-performance__header">
        <div>
          <span>Rendimiento SFA</span>
          <h2>Jugadores del partido</h2>
        </div>
        <small>Puntos calculados por impacto real</small>
      </header>
      <div className="wmd-performance__list">
        {players.map(({ player, team, isStarter }, index) => {
          const photo = PLAYER_PHOTO(player.external_id)
          const teamLogo = TEAM_LOGO(team.external_id)
          const content = (
            <>
              <span className="wmd-performance__rank">{String(index + 1).padStart(2, '0')}</span>
              <span className="wmd-performance__photo">
                {photo && (
                  <img
                    src={photo}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    onError={(event) => {
                      event.currentTarget.style.display = 'none'
                    }}
                  />
                )}
              </span>
              <span className="wmd-performance__identity">
                <strong>{player.name}</strong>
                <small>
                  {teamLogo && <img src={teamLogo} alt="" loading="lazy" decoding="async" />}
                  {worldCupTeamName(team)}
                  {player.position ? ` - ${player.position}` : ''}
                  {isStarter ? '' : ' - Suplente'}
                </small>
              </span>
              <b>{player.sfa_points != null ? `${Math.round(player.sfa_points).toLocaleString('es-ES')} pts` : 'Pend.'}</b>
            </>
          )

          return player.player_id != null ? (
            <Link
              to={`/player/${player.player_id}?season=2026`}
              className="wmd-performance__row"
              key={`${player.external_id ?? player.name}-${index}`}
            >
              {content}
            </Link>
          ) : (
            <div className="wmd-performance__row" key={`${player.external_id ?? player.name}-${index}`}>
              {content}
            </div>
          )
        })}
      </div>
    </section>
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
          <TeamIdentity team={fixture.home_team} asLink />
          <div className="wmd-scoreboard__score">
            <strong>
              {fixture.home_goals ?? '—'} <span>:</span> {fixture.away_goals ?? '—'}
            </strong>
            <small className={fixture.is_live ? 'wmd-scoreboard__live' : ''}>{matchStatus(fixture)}</small>
          </div>
          <TeamIdentity team={fixture.away_team} asLink />
        </div>
        <div className="wmd-scoreboard__meta">
          <span>{venueText || 'Estadio por confirmar'}</span>
          <span>{detail.referee ? `Árbitro · ${detail.referee}` : 'Árbitro por confirmar'}</span>
        </div>
      </header>

      <nav className="wmd-tabs" aria-label="Detalle del partido" role="tablist">
        {([
          ['lineups', 'Alineaciones'],
          ['performance', 'Rendimiento SFA'],
          ['statistics', 'Estadísticas'],
        ] as const).map(([id, label]) => (
          <button
            type="button"
            key={id}
            id={`wmd-tab-${id}`}
            className={`wmd-tab${tab === id ? ' wmd-tab--active' : ''}`}
            onClick={() => setTab(id)}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`wmd-panel-${id}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <main
        id={`wmd-panel-${tab}`}
        className="wmd-content"
        role="tabpanel"
        aria-labelledby={`wmd-tab-${tab}`}
      >
        {tab === 'lineups' && (
          detail.lineups.length > 0 ? (
            <>
              <MatchTimeline
                events={detail.events ?? []}
                homeTeamExternalId={fixture.home_team.external_id ?? fixture.home_team.id}
              />
              {homeLineup && awayLineup && (
                <CombinedTacticalPitch homeLineup={homeLineup} awayLineup={awayLineup} />
              )}
              <div className="wmd-lineups-heading">
                <span>Alineaciones completas</span>
                <small>Los puntos SFA aparecen cuando el partido ya fue procesado.</small>
              </div>
              <div className="wmd-lineups-grid">
                {homeLineup && <LineupColumn lineup={homeLineup} color={teamColor(homeLineup.team.name, homeLineup.team.external_id)} />}
                {awayLineup && <LineupColumn lineup={awayLineup} color={teamColor(awayLineup.team.name, awayLineup.team.external_id)} />}
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
        {tab === 'performance' && (
          <PlayerPerformancePanel lineups={detail.lineups} />
        )}
      </main>
    </div>
  )
}
