import type { CSSProperties, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { TournamentMatchDetail, TournamentMatchMomentumBucket, TournamentMatchStatistic, TournamentMatchTeam, TournamentMatchTeamLineup } from '../../../types'
import { formatLocalDateLong, formatLocalTime, localTimeZoneLabel } from '../../../utils/localTime'
import { isTournamentFinal, tournamentStatusLabel } from '../../../utils/tournaments'
import { levelBand, teamHref } from '../../../utils/teams'
import { FootballIcon } from '../../shared/FootballVisuals'
import {
  isGoalEvent,
  minuteLabel,
  playerPhoto,
  shortName,
  teamLogo,
  type MatchModel,
  type MatchPlayer,
  type Side,
} from './matchModel'

const points = (value: number) => Math.round(value).toLocaleString('es-ES')

function TeamCrest({ team, size = 28 }: { team: TournamentMatchTeam; size?: number }) {
  const logo = teamLogo(team)
  return logo
    ? <img className="mt-crest" src={logo} alt="" width={size} height={size} loading="lazy" decoding="async" />
    : <span className="mt-crest mt-crest--fallback" style={{ width: size, height: size }} aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

function Photo({ player, className }: { player: Pick<MatchPlayer, 'external_id' | 'name'>; className: string }) {
  const photo = playerPhoto(player.external_id)
  return (
    <span className={className}>
      {photo ? <img src={photo} alt="" loading="lazy" decoding="async" /> : <span aria-hidden="true">{player.name.slice(0, 2).toUpperCase()}</span>}
    </span>
  )
}

function Card({ red = false }: { red?: boolean }) {
  return <i className={`mt-card${red ? ' is-red' : ''}`} aria-label={red ? 'Tarjeta roja' : 'Tarjeta amarilla'} />
}

export type SelectPlayer = (player: MatchPlayer) => void

/** Opens the in-page player sheet when available; otherwise links to the full profile. */
function PlayerLink({ player, scope, className, children, onSelect }: { player: MatchPlayer; scope: string; className: string; children: ReactNode; onSelect?: SelectPlayer }) {
  if (onSelect) {
    return (
      <button type="button" className={`${className} mt-btn`} onClick={() => onSelect(player)} aria-label={`Ver ficha de ${player.name} en este partido`}>
        {children}
      </button>
    )
  }
  return player.player_id != null
    ? <Link className={className} to={`/player/${player.player_id}?scope=${scope}`}>{children}</Link>
    : <div className={className}>{children}</div>
}

/* ── Hero: scoreboard + SFA player of the match ─────────────────────────── */

function statusText(detail: TournamentMatchDetail) {
  const { fixture } = detail
  if (fixture.is_live) return fixture.elapsed != null ? `En vivo · ${fixture.elapsed}'` : 'En vivo'
  if (isTournamentFinal(fixture.status)) return fixture.status_label || 'Final'
  if (['NS', 'TBD'].includes(fixture.status)) return `${formatLocalTime(fixture.played_at)} · ${localTimeZoneLabel()}`
  return fixture.status_label || tournamentStatusLabel(fixture.status)
}

function Scorers({ model, side }: { model: MatchModel; side: Side }) {
  const goals = model.goals.filter((goal) => goal.side === side)
  const reds = model.events.filter((event) => (event.event_type === 'red_card' || event.event_type === 'yellow_red_card') && model.sideOf(event.team_external_id) === side)
  if (goals.length === 0 && reds.length === 0) return null
  return (
    <ul className="mt-scorers">
      {goals.map((goal, index) => (
        <li key={`g${index}`}>
          {goal.scorer ? shortName(goal.scorer.name) : shortName(goal.player_name)} {minuteLabel(goal)}
          {goal.event_type === 'penalty' && ' (p)'}
          {goal.event_type === 'own_goal' && ' (pp)'}
        </li>
      ))}
      {reds.map((event, index) => <li key={`r${index}`} className="is-red"><Card red />{displayName(event.actor, event.player_name)} {minuteLabel(event)}</li>)}
    </ul>
  )
}

export type TeamLevels = { home: number | null; away: number | null }

function TeamName({ team, level }: { team: TournamentMatchTeam; level: number | null }) {
  const href = teamHref(team.name, team.external_id)
  return (
    <>
      {href ? <Link to={href} className="mt-score__name">{team.name}</Link> : <strong className="mt-score__name">{team.name}</strong>}
      {level != null && <span className="mt-score__level" title="Fuerza del equipo en la escala del motor SFA (0–100), la que usa el multiplicador de rival">Nivel {Math.round(level)} · {levelBand(level)}</span>}
    </>
  )
}

export function MatchHero({ detail, model, scope, onSelect, levels }: { detail: TournamentMatchDetail; model: MatchModel; scope: string; onSelect?: SelectPlayer; levels?: TeamLevels }) {
  const { fixture } = detail
  const hasScore = fixture.home_goals != null && fixture.away_goals != null
  const best = model.ranked[0]
  const runnersUp = model.ranked.slice(1, 3)
  const homeLogo = teamLogo(fixture.home_team)
  const awayLogo = teamLogo(fixture.away_team)

  return (
    <div className={`mt-hero${best ? '' : ' is-solo'}`}>
      <section className={`mt-score${fixture.is_live ? ' is-live' : ''}`} aria-label="Marcador">
        <span className="mt-score__wash" aria-hidden="true">
          {homeLogo && <img src={homeLogo} alt="" />}
          {awayLogo && <img src={awayLogo} alt="" />}
        </span>
        <div className="mt-score__team">
          <TeamCrest team={fixture.home_team} size={84} />
          <TeamName team={fixture.home_team} level={levels?.home ?? null} />
          <Scorers model={model} side="home" />
        </div>
        <div className="mt-score__center">
          <span className="mt-score__status">{statusText(detail)}</span>
          {hasScore
            ? <span className="mt-score__result">{fixture.home_goals}<i aria-hidden="true">–</i>{fixture.away_goals}</span>
            : <span className="mt-score__result mt-score__result--time">{formatLocalTime(fixture.played_at)}</span>}
        </div>
        <div className="mt-score__team">
          <TeamCrest team={fixture.away_team} size={84} />
          <TeamName team={fixture.away_team} level={levels?.away ?? null} />
          <Scorers model={model} side="away" />
        </div>
        <p className="mt-score__meta">
          {formatLocalDateLong(fixture.played_at)}
          {detail.venue.name && <> · {detail.venue.name}</>}
          {detail.referee && <> · Árbitro: {detail.referee}</>}
        </p>
      </section>

      {best && (
        <section className="mt-motm" aria-label="Jugador SFA del partido">
          <Photo player={best} className="mt-motm__photo" />
          <div className="mt-motm__body">
            <span className="mt-motm__kicker">
              <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="m8 1.5 1.9 4.1 4.4.5-3.3 3 .9 4.4L8 11.3l-3.9 2.2.9-4.4-3.3-3 4.4-.5Z" fill="currentColor" /></svg>
              Jugador SFA del partido
            </span>
            <strong className="mt-motm__pts">{points(best.sfa_points ?? 0)}<small> pts SFA</small></strong>
            <PlayerLink player={best} scope={scope} className="mt-motm__name" onSelect={onSelect}>{best.name}</PlayerLink>
            <span className="mt-motm__team"><TeamCrest team={best.team} size={16} />{best.team.name}</span>
            <ul className="mt-motm__chips">
              {best.marks.goals > 0 && <li><b>{best.marks.goals}</b> {best.marks.goals === 1 ? 'Gol' : 'Goles'}</li>}
              {best.marks.assists > 0 && <li><b>{best.marks.assists}</b> {best.marks.assists === 1 ? 'Asistencia' : 'Asistencias'}</li>}
              {best.marks.off != null && <li>Jugó hasta el <b>{best.marks.off}'</b></li>}
            </ul>
            {runnersUp.length > 0 && (
              <ol className="mt-motm__next" start={2}>
                {runnersUp.map((player) => (
                  <li key={player.external_id ?? player.name}>
                    <span>{shortName(player.name)}</span>
                    <b>{points(player.sfa_points ?? 0)}</b>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

/* ── Lineups: both teams on one horizontal pitch ────────────────────────── */

function placeTeam(lineup: TournamentMatchTeamLineup, side: Side, model: MatchModel) {
  const starters = model.players.filter((player) => player.side === side && player.starter)
  const placed = starters.flatMap((player) => {
    const [row, column] = player.grid?.split(':').map(Number) ?? []
    return Number.isFinite(row) && Number.isFinite(column) ? [{ player, row, column }] : []
  })
  const maxRow = Math.max(...placed.map((item) => item.row), 2)
  return placed.map(({ player, row, column }) => {
    const rowSize = placed.filter((item) => item.row === row).length
    // Lines run from the goalkeeper (row 1) towards halfway; columns follow each team's own left-to-right.
    const depth = 5 + ((row - 1) / (maxRow - 1)) * 39
    const spread = column / (rowSize + 1)
    return {
      player,
      x: side === 'home' ? depth : 100 - depth,
      y: (side === 'home' ? spread : 1 - spread) * 100,
      key: `${lineup.team.id}-${player.external_id ?? player.name}`,
    }
  })
}

/** Substitution arrow: green up for coming on, red down for going off (the usual football convention). */
function SubArrow({ dir }: { dir: 'in' | 'out' }) {
  return (
    <svg className={`mt-subarrow is-${dir}`} viewBox="0 0 10 12" width="9" height="11" aria-hidden="true">
      <path d={dir === 'in' ? 'M5 11V2M1.5 5 5 1.5 8.5 5' : 'M5 1v9M1.5 7 5 10.5 8.5 7'} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PitchPlayer({ player, scope, top, onSelect }: { player: MatchPlayer; scope: string; top: boolean; onSelect?: SelectPlayer }) {
  const pts = player.sfa_points
  const tone = pts == null ? 'is-none' : top ? 'is-top' : pts < 0 ? 'is-neg' : ''
  return (
    <PlayerLink player={player} scope={scope} className="mt-pp" onSelect={onSelect}>
      <span className="mt-pp__badges">
        {player.marks.off != null && (
          <span className="mt-pp__off" title={`Sale en el ${player.marks.off}'${player.marks.swap ? `, entra ${player.marks.swap}` : ''}`}>
            <SubArrow dir="out" />{player.marks.off}'
          </span>
        )}
        {pts != null && <span className={`mt-pp__pts ${tone}`}>{points(pts)}</span>}
      </span>
      <Photo player={player} className="mt-pp__photo" />
      <span className="mt-pp__marks" aria-hidden="true">
        {Array.from({ length: player.marks.goals }, (_, index) => <FootballIcon kind="goal" key={index} />)}
        {player.marks.red ? <Card red /> : player.marks.yellow && <Card />}
      </span>
      <span className="mt-pp__name"><small>{player.number}</small>{shortName(player.name)}</span>
    </PlayerLink>
  )
}

function Bench({ model, side, scope, onSelect }: { model: MatchModel; side: Side; scope: string; onSelect?: SelectPlayer }) {
  const used = model.players
    .filter((player) => player.side === side && !player.starter && player.marks.on != null)
    .sort((a, b) => (a.marks.on ?? 0) - (b.marks.on ?? 0))
  if (used.length === 0) return <p className="mt-bench__empty">Sin cambios registrados</p>
  return (
    <ul className="mt-bench">
      {used.map((player) => {
        return (
          <li key={player.external_id ?? player.name}>
            <PlayerLink player={player} scope={scope} className="mt-bench__row" onSelect={onSelect}>
              <Photo player={player} className="mt-bench__photo" />
              <span className="mt-bench__who">
                <strong>{player.name}</strong>
                <small><SubArrow dir="in" />Entra en el {player.marks.on}'{player.marks.swap && ` por ${shortName(player.marks.swap)}`}</small>
              </span>
              {player.sfa_points != null && <b>{points(player.sfa_points)}</b>}
            </PlayerLink>
          </li>
        )
      })}
    </ul>
  )
}

export function MatchLineups({ detail, model, scope, onSelect }: { detail: TournamentMatchDetail; model: MatchModel; scope: string; onSelect?: SelectPlayer }) {
  const home = detail.lineups.find((lineup) => model.sideOf(lineup.team.external_id) === 'home')
  const away = detail.lineups.find((lineup) => model.sideOf(lineup.team.external_id) === 'away')
  if (!home && !away) return null
  const placed = [...(home ? placeTeam(home, 'home', model) : []), ...(away ? placeTeam(away, 'away', model) : [])]

  const head = (lineup: TournamentMatchTeamLineup | undefined, side: Side) => lineup && (
    <div className={`mt-lineups__team is-${side}`}>
      <TeamCrest team={lineup.team} size={24} />
      <strong>{lineup.team.name}</strong>
      <span>{lineup.formation ?? 'Formación por confirmar'}</span>
      {model.teamPoints[side] !== 0 && <b>{points(model.teamPoints[side])} pts</b>}
    </div>
  )

  return (
    <section className="mt-panel mt-lineups" aria-labelledby="mt-lineups-title">
      <header className="mt-panel__head">
        <h2 id="mt-lineups-title">Alineaciones</h2>
        <span className="mt-panel__hint">Puntos SFA de cada jugador en este partido</span>
      </header>
      <div className="mt-lineups__teams">{head(home, 'home')}{head(away, 'away')}</div>

      {placed.length > 0 ? (
        <div className="mt-pitch-scroll">
          <div className="mt-pitch">
            {placed.map(({ player, x, y, key }) => (
              <div className="mt-pitch__slot" style={{ '--x': `${x}%`, '--y': `${y}%` } as CSSProperties} key={key}>
                <PitchPlayer
                  player={player}
                  scope={scope}
                  top={model.topIds.has(player.external_id)}
                  onSelect={onSelect}
                />
              </div>
            ))}
          </div>
        </div>
      ) : <p className="mt-empty">La disposición táctica todavía no está disponible.</p>}

      {placed.some(({ player }) => player.marks.off != null) && (
        <p className="mt-sublegend">
          <span><SubArrow dir="out" /> Minuto en que fue sustituido</span>
          <span><SubArrow dir="in" /> Quién entró, en la lista de cambios</span>
        </p>
      )}

      <div className="mt-lineups__bench">
        <div><h3>Cambios · {home?.team.name}</h3><Bench model={model} side="home" scope={scope} onSelect={onSelect} /></div>
        <div><h3>Cambios · {away?.team.name}</h3><Bench model={model} side="away" scope={scope} onSelect={onSelect} /></div>
      </div>
      {(home?.coach_name || away?.coach_name) && (
        <p className="mt-lineups__coaches">
          DT {home?.team.name}: <b>{home?.coach_name ?? '—'}</b> · DT {away?.team.name}: <b>{away?.coach_name ?? '—'}</b>
        </p>
      )}
    </section>
  )
}

/* ── SFA momentum: who generated impact, minute by minute ───────────────── */

function smoothPath(points: Array<[number, number]>) {
  if (points.length === 0) return ''
  return points.reduce((path, [x, y], index) => {
    if (index === 0) return `M${x},${y}`
    const [px, py] = points[index - 1]
    const cx = (px + x) / 2
    return `${path} C${cx},${py} ${cx},${y} ${x},${y}`
  }, '')
}

function momentumInsights(buckets: TournamentMatchMomentumBucket[], homeName: string, awayName: string) {
  const home = buckets.reduce((sum, bucket) => sum + Math.max(bucket.home_points, 0), 0)
  const away = buckets.reduce((sum, bucket) => sum + Math.max(bucket.away_points, 0), 0)
  const total = home + away
  const insights: string[] = []
  if (total > 0) {
    const leader = home >= away ? homeName : awayName
    insights.push(`${leader} generó el ${Math.round((Math.max(home, away) / total) * 100)} % del impacto SFA`)
  }
  const bestBucket = (side: 'home_points' | 'away_points') => buckets.reduce((best, bucket) => (bucket[side] > best[side] ? bucket : best), buckets[0])
  const homeBest = bestBucket('home_points')
  const awayBest = bestBucket('away_points')
  if (homeBest.home_points > 0) insights.push(`Mejor tramo de ${homeName}: ${homeBest.minute_start}'–${homeBest.minute_end}'`)
  if (awayBest.away_points > 0) insights.push(`Mejor tramo de ${awayName}: ${awayBest.minute_start}'–${awayBest.minute_end}'`)
  return insights
}

export function MatchMomentum({ detail, model }: { detail: TournamentMatchDetail; model: MatchModel }) {
  const buckets = detail.sfa_momentum
  const { home_team: homeTeam, away_team: awayTeam } = detail.fixture
  if (buckets.length === 0) return null
  const end = Math.max(90, ...buckets.map((bucket) => bucket.minute_end))
  const max = Math.max(...buckets.flatMap((bucket) => [Math.abs(bucket.home_points), Math.abs(bucket.away_points)]), 1)
  const W = 1000
  const H = 200
  const mid = H / 2
  const x = (minute: number) => (minute / end) * W
  const homePts: Array<[number, number]> = [[0, mid], ...buckets.map((bucket): [number, number] => [x((bucket.minute_start + bucket.minute_end) / 2), mid - (Math.max(bucket.home_points, 0) / max) * (mid - 12)]), [W, mid]]
  const awayPts: Array<[number, number]> = [[0, mid], ...buckets.map((bucket): [number, number] => [x((bucket.minute_start + bucket.minute_end) / 2), mid + (Math.max(bucket.away_points, 0) / max) * (mid - 12)]), [W, mid]]
  const insights = momentumInsights(buckets, homeTeam.name, awayTeam.name)

  return (
    <section className="mt-panel mt-momentum" aria-labelledby="mt-momentum-title">
      <header className="mt-panel__head">
        <h2 id="mt-momentum-title">Impacto SFA del partido</h2>
        <span className="mt-legend">
          <span className="is-home"><TeamCrest team={homeTeam} size={16} />{homeTeam.name}</span>
          <span className="is-away"><TeamCrest team={awayTeam} size={16} />{awayTeam.name}</span>
        </span>
      </header>
      <div className="mt-momentum__chart">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`Puntos SFA generados cada cinco minutos: ${homeTeam.name} arriba, ${awayTeam.name} abajo`}>
          <path className="mt-momentum__area is-home" d={`${smoothPath(homePts)} Z`} />
          <path className="mt-momentum__area is-away" d={`${smoothPath(awayPts)} Z`} />
          <line className="mt-momentum__axis" x1="0" y1={mid} x2={W} y2={mid} />
          <line className="mt-momentum__half" x1={x(45)} y1="0" x2={x(45)} y2={H} />
        </svg>
        {model.goals.map((goal, index) => (
          <span
            key={index}
            className={`mt-momentum__goal is-${goal.side}`}
            style={{ '--x': `${(Math.min(goal.minute, end) / end) * 100}%` } as CSSProperties}
          >
            <FootballIcon kind="goal" />
            <small>{goal.scorer ? shortName(goal.scorer.name) : shortName(goal.player_name)} {minuteLabel(goal)}</small>
          </span>
        ))}
        <span className="mt-momentum__tick is-start">0'</span>
        <span className="mt-momentum__tick is-half">Descanso</span>
        <span className="mt-momentum__tick is-end">{end}'</span>
      </div>
      {insights.length > 0 && (
        <ul className="mt-momentum__insights">
          {insights.map((text) => <li key={text}>{text}</li>)}
        </ul>
      )}
    </section>
  )
}

/* ── Events: centred timeline, goals as highlighted cards ───────────────── */

/** Prefer the lineup's own name for an event actor (it is what the pitch and bench show). */
function displayName(player: MatchPlayer | null, fallback: string, short = true) {
  if (!player) return short ? shortName(fallback) : fallback
  return short ? shortName(player.name) : player.name
}

export function MatchEvents({ detail, model, scope }: { detail: TournamentMatchDetail; model: MatchModel; scope: string }) {
  if (model.events.length === 0) return null
  const { home_team: homeTeam, away_team: awayTeam } = detail.fixture
  const halftime = model.goals.filter((goal) => goal.minute <= 45)
  const htScore = halftime.length ? halftime[halftime.length - 1].score : [0, 0]
  let shownHalftime = false
  let goalIndex = 0

  return (
    <section className="mt-panel mt-events" aria-labelledby="mt-events-title">
      <header className="mt-events__head">
        <span><TeamCrest team={homeTeam} size={18} />{homeTeam.name}</span>
        <h2 id="mt-events-title">Eventos</h2>
        <span>{awayTeam.name}<TeamCrest team={awayTeam} size={18} /></span>
      </header>
      <ol className="mt-events__list">
        {model.events.map((event, index) => {
          const side = model.sideOf(event.team_external_id)
          const items: ReactNode[] = []
          if (!shownHalftime && event.minute > 45) {
            shownHalftime = true
            items.push(<li className="mt-events__divider" key="ht"><span>Descanso · {htScore[0]}–{htScore[1]}</span></li>)
          }
          if (isGoalEvent(event)) {
            const goal = model.goals[goalIndex++]
            const scorer = goal?.scorer
            items.push(
              <li className={`mt-ev is-${goal?.side ?? side} is-goal`} key={index}>
                <time>{minuteLabel(event)}</time>
                <div className="mt-ev__goal">
                  {scorer ? <Photo player={scorer} className="mt-ev__photo" /> : <span className="mt-ev__photo" />}
                  <span className="mt-ev__who">
                    <strong>
                      {scorer ? (scorer.player_id != null ? <Link to={`/player/${scorer.player_id}?scope=${scope}`}>{scorer.name}</Link> : scorer.name) : event.player_name}
                      <FootballIcon kind="goal" />
                    </strong>
                    <small>
                      {event.event_type === 'penalty' ? 'De penal' : event.event_type === 'own_goal' ? 'En propia puerta' : event.assist_name ? `Asist. ${event.assist_name}` : 'Sin asistencia'}
                    </small>
                  </span>
                  {goal && <b className="mt-ev__score">{goal.score[0]}–{goal.score[1]}</b>}
                </div>
              </li>,
            )
          } else {
            const isSub = event.event_type === 'substitution'
            const isRed = event.event_type === 'red_card' || event.event_type === 'yellow_red_card'
            items.push(
              <li className={`mt-ev is-${side}`} key={index}>
                <time>{minuteLabel(event)}</time>
                <div className="mt-ev__line">
                  {isSub ? (
                    <>
                      <span className="mt-ev__sub" aria-hidden="true"><i className="is-in" /><i className="is-out" /></span>
                      <span><b>{event.assist_name ? displayName(event.secondary, event.assist_name) : 'Cambio'}</b> entra por {displayName(event.actor, event.player_name)}</span>
                    </>
                  ) : (
                    <>
                      {event.event_type.includes('card') ? <Card red={isRed} /> : <span className="mt-ev__dot" />}
                      <b>{displayName(event.actor, event.player_name, false)}</b>
                      {event.event_type === 'missed_penalty' && <span> · penal fallado</span>}
                    </>
                  )}
                </div>
              </li>,
            )
          }
          return items
        })}
      </ol>
    </section>
  )
}

/* ── Statistics: mirrored bars, the side that leads is highlighted ──────── */

const STAT_ORDER: Array<[string, string]> = [
  ['Ball Possession', 'Posesión'],
  ['expected_goals', 'Goles esperados (xG)'],
  ['Total Shots', 'Remates'],
  ['Shots on Goal', 'Remates a puerta'],
  ['Shots insidebox', 'Remates dentro del área'],
  ['Total passes', 'Pases'],
  ['Passes accurate', 'Pases completados'],
  ['Corner Kicks', 'Córners'],
  ['Goalkeeper Saves', 'Paradas'],
  ['Fouls', 'Faltas'],
  ['Offsides', 'Fueras de juego'],
  ['Yellow Cards', 'Tarjetas amarillas'],
  ['Red Cards', 'Tarjetas rojas'],
]

export function MatchStats({ statistics, homeTeam, awayTeam }: { statistics: TournamentMatchStatistic[]; homeTeam: TournamentMatchTeam; awayTeam: TournamentMatchTeam }) {
  const byLabel = new Map(statistics.map((stat) => [stat.label, stat]))
  const rows = STAT_ORDER.flatMap(([key, label]) => {
    const stat = byLabel.get(key)
    return stat ? [{ stat, label }] : []
  })
  if (rows.length === 0) return null

  return (
    <section className="mt-panel mt-stats" aria-labelledby="mt-stats-title">
      <header className="mt-events__head">
        <span><TeamCrest team={homeTeam} size={18} />{homeTeam.name}</span>
        <h2 id="mt-stats-title">Estadísticas</h2>
        <span>{awayTeam.name}<TeamCrest team={awayTeam} size={18} /></span>
      </header>
      <ul className="mt-stats__list">
        {rows.map(({ stat, label }) => {
          const home = Math.max(stat.home_numeric ?? 0, 0)
          const away = Math.max(stat.away_numeric ?? 0, 0)
          const total = home + away || 1
          const lead = home === away ? 'none' : home > away ? 'home' : 'away'
          return (
            <li key={stat.label} className={`is-lead-${lead}`}>
              <b>{stat.home_value ?? '–'}</b>
              <span>{label}</span>
              <b>{stat.away_value ?? '–'}</b>
              <span className="mt-stats__bar" aria-hidden="true">
                <i className="is-home" style={{ '--w': `${(home / total) * 100}%` } as CSSProperties} />
                <i className="is-away" style={{ '--w': `${(away / total) * 100}%` } as CSSProperties} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
