import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { fetchPlayerSeasonStats, fetchRanking } from '../../api/client'
import { Link } from 'react-router-dom'
import type { PlayerCompetitionAchievement, PlayerDetail, PlayerEvent, PlayerFixture, PlayerIndividualHonor, PlayerSeasonStats } from '../../types'
import { competitionLabel, phaseBadge, phaseLabel } from '../../utils/footballLabels'
import { seasonLabel } from '../../utils/season'
import { tournamentCompetitionLogoByName } from '../../utils/tournaments'
import { externalIdFromLogo, teamHref } from '../../utils/teams'
import PlayerPortrait from '../shared/PlayerPortrait'

const POSITION: Record<string, string> = {
  GK: 'Portero', DC: 'Defensa central', LAT: 'Lateral', MC: 'Centrocampista', MCO: 'Mediapunta', EXT: 'Extremo', DEL: 'Delantero',
}

const pts = (value: number) => Math.round(value).toLocaleString('es-ES')
const one = (value: number) => value.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const shortDate = (iso: string) => new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(new Date(iso)).replace('.', '')

const goalsIn = (fixture: PlayerFixture) => (fixture.breakdown?.goal?.count ?? 0) + (fixture.breakdown?.goal_penalty?.count ?? 0)
const assistsIn = (fixture: PlayerFixture) => fixture.breakdown?.assist?.count ?? 0

/** Who the player faced in a fixture, from his own side. */
export function rivalOf(fixture: PlayerFixture, fallbackTeam: string) {
  const team = fixture.player_team ?? fallbackTeam
  const home = fixture.home_team === team
  return {
    home,
    name: home ? fixture.away_team : fixture.home_team,
    logo: home ? fixture.away_team_logo : fixture.home_team_logo,
  }
}

export function matchHref(fixture: PlayerFixture, season: string) {
  return fixture.fixture_external_id ? `/torneos/partido/${fixture.fixture_external_id}?season=${season}` : null
}

/** Home/away marker used across the profile: green L for home, outlined V for away. */
export function Venue({ home }: { home: boolean }) {
  return <i className={`pf-venue ${home ? 'is-home' : 'is-away'}`} title={home ? 'Local' : 'Visitante'}>{home ? 'L' : 'V'}</i>
}

function Crest({ src, name, size = 22 }: { src: string | null; name: string; size?: number }) {
  return src
    ? <img className="pf-crest" src={src} alt="" title={name} width={size} height={size} loading="lazy" decoding="async" />
    : <span className="pf-crest pf-crest--fallback" style={{ width: size, height: size }} aria-hidden="true">{name.slice(0, 2).toUpperCase()}</span>
}

function MaybeLink({ to, className, children, label }: { to: string | null; className: string; children: ReactNode; label?: string }) {
  return to ? <Link to={to} className={className} aria-label={label}>{children}</Link> : <div className={className}>{children}</div>
}

/* ── Hero ───────────────────────────────────────────────────────────────── */

/** Size of the ranked field for the selected period (filters already applied by the API). */
function useRankedTotal(scope: string) {
  const [total, setTotal] = useState<number | null>(null)
  useEffect(() => {
    let active = true
    setTotal(null)
    if (!scope) return undefined
    fetchRanking({ ...(scope === 'all' ? { season: 'all' } : { scope }), limit: 1 })
      .then((r) => { if (active) setTotal(r.total) })
      .catch(() => undefined)
    return () => { active = false }
  }, [scope])
  return total
}

function RankBadge({ player, scope }: { player: PlayerDetail; scope: string }) {
  const total = useRankedTotal(scope)
  if (player.global_rank <= 0) return null
  const podium = player.global_rank <= 3 ? ` is-p${player.global_rank}` : ''
  return (
    <div className={`pf-rank${podium}`}>
      <span className="pf-rank__num" aria-label={`Puesto ${player.global_rank} del ranking SFA`}><small>#</small>{player.global_rank}</span>
      <span className="pf-rank__copy">
        <span className="pf-eyebrow">Ranking SFA</span>
        {total != null && <small>de {total.toLocaleString('es-ES')} jugadores</small>}
      </span>
    </div>
  )
}

/** Desktop points card: the player's top match of the period, linking to the match page. */
function BestMatch({ fixture, team, season }: { fixture: PlayerFixture; team: string; season: string }) {
  const rival = rivalOf(fixture, team)
  const href = matchHref(fixture, season)
  const goals = goalsIn(fixture)
  const assists = assistsIn(fixture)
  const contributions = [
    goals > 0 && `${goals} ${goals === 1 ? 'gol' : 'goles'}`,
    assists > 0 && `${assists} ${assists === 1 ? 'asistencia' : 'asistencias'}`,
  ].filter(Boolean).join(' y ')
  const body = (
    <>
      <span className="pf-best__label">Su mejor partido</span>
      <span className="pf-best__row">
        <Crest src={rival.logo} name={rival.name} size={34} />
        <span className="pf-best__copy">
          <strong>
            <Venue home={rival.home} />
            {rival.name}
          </strong>
          <small>{shortDate(fixture.played_at)} · {competitionLabel(fixture.competition)}</small>
          {contributions && <small className="pf-best__hits">{contributions}</small>}
        </span>
        <b className="pf-best__pts">{pts(fixture.sfa_pts)}<em>pts</em></b>
      </span>
    </>
  )
  return href ? <Link to={href} className="pf-best">{body}</Link> : <div className="pf-best">{body}</div>
}

export function ProfileHero({ player, fixtures, stats, seasonLabel, seasonPicker, scope }: {
  player: PlayerDetail
  fixtures: PlayerFixture[]
  stats: PlayerSeasonStats | null
  seasonLabel: string
  seasonPicker: ReactNode
  scope: string
}) {
  const minutes = stats?.minutes ?? fixtures.reduce((sum, fixture) => sum + fixture.minutes, 0)
  const perMatch = player.matches > 0 ? player.sfa_pts / player.matches : 0
  // Best match of the period; on a tie the most recent one wins.
  const best = fixtures.reduce<PlayerFixture | null>((top, fixture) => (
    !top || fixture.sfa_pts > top.sfa_pts || (fixture.sfa_pts === top.sfa_pts && fixture.played_at > top.played_at) ? fixture : top
  ), null)
  const teamLogo = fixtures.find((fixture) => fixture.player_team_logo)?.player_team_logo ?? null

  return (
    <div className="pf-hero">
      <section className="pf-id" aria-label="Jugador">
        <span className="pf-id__rank" aria-hidden="true">{player.global_rank}</span>
        <div className="pf-id__copy">
          {/* Phones only: the rank leads the card, like the rating corner of a player card. */}
          {player.global_rank > 0 && (
            <p className={`pf-id__pos${player.global_rank <= 3 ? ` is-p${player.global_rank}` : ''}`} aria-label={`Puesto ${player.global_rank} del ranking SFA`}>
              <b><small>#</small>{player.global_rank}</b>
            </p>
          )}
          <h1>{player.name}</h1>
          <p className="pf-id__meta">
            {(() => {
              const href = teamHref(player.team, externalIdFromLogo(teamLogo))
              const body = <><Crest src={teamLogo} name={player.team} size={18} /><span className="pf-id__club-name">{player.team}</span></>
              return href ? <Link to={href} className="pf-id__club">{body}</Link> : <span>{body}</span>
            })()}
            <span>{POSITION[player.position] ?? player.position}</span>
          </p>
          <ul className="pf-id__chips">
            <li className="is-gold pf-id__rankchip">#{player.global_rank} del ranking SFA</li>
            {player.b1_bonus_label && <li>{player.b1_bonus_label}{player.b1_bonus_pts > 0 && ` · +${pts(player.b1_bonus_pts)} pts`}</li>}
            <li>{seasonLabel}</li>
          </ul>
        </div>
        {/* Phones only: points close the card as a footer (the points card is hidden there). */}
        <div className="pf-id__score" aria-hidden="true">
          <span className="pf-id__pts">{pts(player.sfa_pts)}<em>pts SFA</em></span>
        </div>
        <PlayerPortrait player={player} className="pf-id__photo" eager allowArtwork />
      </section>

      <section className="pf-total" aria-label="Puntos SFA de la temporada">
        <RankBadge player={player} scope={scope} />
        <span className="pf-eyebrow pf-eyebrow--gold">Puntos SFA · {seasonLabel}</span>
        <strong className="pf-total__value">{pts(player.sfa_pts)}</strong>
        <span className="pf-total__sub">en {player.matches} partidos y {minutes.toLocaleString('es-ES')} minutos · {pts(perMatch)} de media</span>
        {best && <BestMatch fixture={best} team={player.team} season={player.season} />}
        {seasonPicker}
      </section>
    </div>
  )
}

/* ── KPI row ────────────────────────────────────────────────────────────── */

export function ProfileKpis({ player, stats, fixtures }: { player: PlayerDetail; stats: PlayerSeasonStats | null; fixtures: PlayerFixture[] }) {
  const minutes = stats?.minutes ?? fixtures.reduce((sum, fixture) => sum + fixture.minutes, 0)
  const goals = player.total_goals
  const assists = player.total_assists
  const kpis = [
    { label: 'Partidos', value: player.matches, sub: stats?.rating_avg != null ? `Nota media ${one(stats.rating_avg)}` : `${minutes.toLocaleString('es-ES')} minutos` },
    { label: 'Goles', value: goals, sub: goals > 0 ? `1 cada ${Math.round(minutes / goals)} minutos` : 'Sin goles todavía' },
    { label: 'Asistencias', value: assists, sub: `${goals + assists} participaciones de gol` },
    { label: 'Remates', value: stats?.shots_total ?? '—', sub: stats ? `${stats.shots_on} a puerta` : '' },
  ]
  return (
    <ul className="pf-kpis">
      {kpis.map((kpi) => (
        <li key={kpi.label}>
          <span className="pf-eyebrow">{kpi.label}</span>
          <b>{kpi.value}</b>
          <small>{kpi.sub}</small>
        </li>
      ))}
    </ul>
  )
}

/* ── Match by match: every fixture of the period, fitted to width ────────── */

const TREND_WINDOW = 5
const CRESTS_UP_TO = 16

export function ProfileMatchBars({ fixtures, team, season }: { fixtures: PlayerFixture[]; team: string; season: string }) {
  const [active, setActive] = useState<number | null>(null)
  const plotRef = useRef<HTMLDivElement>(null)
  const ordered = [...fixtures].sort((a, b) => a.played_at.localeCompare(b.played_at))
  if (ordered.length === 0) return null

  const n = ordered.length
  const values = ordered.map((fixture) => fixture.sfa_pts)
  const max = Math.max(...values, 1)
  const min = Math.min(0, ...values)
  const avg = values.reduce((sum, value) => sum + value, 0) / n
  const bestIndex = values.indexOf(Math.max(...values))
  const dense = n > CRESTS_UP_TO

  // Plot box in percent of the chart: room above for the best label, below for the axis.
  const xOf = (index: number) => (n === 1 ? 50 : 2 + (index / (n - 1)) * 96)
  const yOf = (value: number) => 10 + (1 - (value - min) / (max - min || 1)) * 74
  const raw = ordered.map((fixture, index) => [xOf(index), yOf(fixture.sfa_pts)] as const)
  // Rolling mean of the last TREND_WINDOW matches: the shape of the season, not one-off spikes.
  const trend = values.map((_, index) => {
    const slice = values.slice(Math.max(0, index - TREND_WINDOW + 1), index + 1)
    return [xOf(index), yOf(slice.reduce((sum, value) => sum + value, 0) / slice.length)] as const
  })
  const smooth = (points: ReadonlyArray<readonly [number, number]>) => points.reduce((path, [x, y], index) => {
    if (index === 0) return `M${x},${y}`
    const [px, py] = points[index - 1]
    const cx = (px + x) / 2
    return `${path} C${cx},${py} ${cx},${y} ${x},${y}`
  }, '')
  const trendPath = smooth(trend)
  const rawPath = raw.map(([x, y], index) => `${index ? 'L' : 'M'}${x},${y}`).join(' ')
  const area = `${trendPath} L${trend[n - 1][0]},84 L${trend[0][0]},84 Z`
  const avgY = yOf(avg)

  // Month ticks for dense periods: first match of each month.
  const monthFmt = new Intl.DateTimeFormat('es-ES', { month: 'short' })
  const yearFmt = new Intl.DateTimeFormat('es-ES', { year: '2-digit' })
  const ticks = dense
    ? ordered.flatMap((fixture, index) => {
        const month = fixture.played_at.slice(0, 7)
        if (index > 0 && ordered[index - 1].played_at.slice(0, 7) === month) return []
        const date = new Date(fixture.played_at)
        const label = month.endsWith('-01') || index === 0 ? `${monthFmt.format(date).replace('.', '')} '${yearFmt.format(date)}` : monthFmt.format(date).replace('.', '')
        return [{ index, label }]
      })
        // Skip labels that would sit on top of the previous one (months with few matches).
        .filter((tick, position, all) => position === 0 || xOf(tick.index) - xOf(all[position - 1].index) >= 4.5)
    : []

  const pick = (clientX: number) => {
    const box = plotRef.current?.getBoundingClientRect()
    if (!box || n === 0) return
    const pct = ((clientX - box.left) / box.width) * 100
    const index = Math.round(((pct - 2) / 96) * (n - 1))
    setActive(Math.min(Math.max(index, 0), n - 1))
  }

  const current = active != null ? ordered[active] : null
  const currentRival = current ? rivalOf(current, team) : null
  const lastTrend = (trend[n - 1] ? values.slice(-TREND_WINDOW).reduce((sum, value) => sum + value, 0) / Math.min(TREND_WINDOW, n) : 0)
  // A 10 % band around the season average reads as "in his level", not up or down.
  const form = n < 3 ? 'is-flat' : lastTrend >= avg * 1.1 ? 'is-up' : lastTrend <= avg * 0.9 ? 'is-down' : 'is-flat'

  return (
    <section className="pf-panel" aria-labelledby="pf-bars-title">
      <header className="pf-panel__head pf-trend-head">
        <div>
          <h2 id="pf-bars-title">Su racha partido a partido</h2>
          <p>Cada punto es un partido y su altura, los puntos SFA que sumó. La línea dorada marca su nivel: si sube, está jugando cada vez mejor.</p>
        </div>
        <span className={`pf-trend-verdict ${form}`}>
          <b>{form === 'is-up' ? 'Viene en racha' : form === 'is-down' ? 'Por debajo de su nivel' : 'En su nivel'}</b>
          <small>Últimos {Math.min(TREND_WINDOW, n)}: {pts(lastTrend)} pts de media · temporada: {pts(avg)}</small>
        </span>
      </header>
      <div className="pf-legend pf-trend-legend">
        <span><i className="is-trend" />Su nivel (media de los últimos 5)</span>
        <span><i className="is-elite" />Partido por encima de lo habitual</span>
      </div>
      <div
        className={`pf-trend${dense ? ' is-dense' : ''}`}
        ref={plotRef}
        onPointerMove={(event) => pick(event.clientX)}
        onPointerLeave={() => setActive(null)}
      >
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="pf-trend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#C9A84C" stopOpacity="0.34" />
              <stop offset="1" stopColor="#C9A84C" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path className="pf-trend__area" d={area} />
          <line className="pf-trend__avg" x1="0" x2="100" y1={avgY} y2={avgY} />
          <path className="pf-trend__raw" d={rawPath} />
          <path className="pf-trend__line" d={trendPath} />
          {active != null && <line className="pf-trend__guide" x1={raw[active][0]} x2={raw[active][0]} y1="4" y2="84" />}
        </svg>
        <span className="pf-trend__avg-label" style={{ top: `${avgY}%` }}>media {pts(avg)}</span>

        {ordered.map((fixture, index) => {
          const rival = rivalOf(fixture, team)
          const [x, y] = raw[index]
          return (
            <MaybeLink
              key={fixture.fixture_id}
              to={matchHref(fixture, season)}
              className={`pf-trend__pt${fixture.sfa_pts >= avg ? ' is-elite' : ''}${index === bestIndex ? ' is-best' : ''}${index === active ? ' is-active' : ''}`}
              label={`${rival.name} (${rival.home ? 'local' : 'visitante'}), ${shortDate(fixture.played_at)}: ${pts(fixture.sfa_pts)} puntos SFA`}
            >
              <span className="pf-trend__dot" style={{ left: `${x}%`, top: `${y}%` }} onFocus={() => setActive(index)} onBlur={() => setActive(null)}>
                {index === bestIndex && <b>{pts(fixture.sfa_pts)}</b>}
                <i aria-hidden="true" />
              </span>
              {!dense && (
                <span className="pf-trend__axis" style={{ left: `${x}%` }} aria-hidden="true">
                  <Crest src={rival.logo} name={rival.name} size={18} />
                  <small>{shortDate(fixture.played_at)}</small>
                </span>
              )}
            </MaybeLink>
          )
        })}

        {dense && ticks.map((tick) => (
          <span key={tick.index} className="pf-trend__tick" style={{ left: `${xOf(tick.index)}%` }} aria-hidden="true">{tick.label}</span>
        ))}

        {current && currentRival && active != null && (
          <div className={`pf-tip${raw[active][0] > 70 ? ' is-left' : ''}`} style={{ left: `${raw[active][0]}%` }} role="status">
            <span className="pf-tip__head">
              <Crest src={currentRival.logo} name={currentRival.name} size={20} />
              <strong><Venue home={currentRival.home} /> {currentRival.name}</strong>
            </span>
            <small>{shortDate(current.played_at)} · {competitionLabel(current.competition)} · {current.minutes}'</small>
            <b>{pts(current.sfa_pts)} <em>pts SFA</em></b>
            {(goalsIn(current) > 0 || assistsIn(current) > 0) && (
              <span className="pf-tip__marks">
                {goalsIn(current) > 0 && <em>{goalsIn(current)} {goalsIn(current) === 1 ? 'gol' : 'goles'}</em>}
                {assistsIn(current) > 0 && <em>{assistsIn(current)} {assistsIn(current) === 1 ? 'asistencia' : 'asistencias'}</em>}
              </span>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

/* ── Where the points come from + in which context ──────────────────────── */

const SOURCE_LABELS: Record<string, string> = {
  stats: 'Juego (pases, duelos, regates…)',
  goal: 'Goles',
  goal_penalty: 'Goles de penal',
  assist: 'Asistencias',
}

export function ProfilePointsSources({ player }: { player: PlayerDetail }) {
  const entries = Object.entries(player.breakdown ?? {}).filter(([, entry]) => entry.pts > 0).sort((a, b) => b[1].pts - a[1].pts)
  const bonus = player.b1_bonus_pts > 0 ? player.b1_bonus_pts : 0
  const total = entries.reduce((sum, [, entry]) => sum + entry.pts, 0) + bonus || 1
  const rows = [...entries.map(([key, entry]) => ({ key, label: SOURCE_LABELS[key] ?? key, count: key === 'stats' ? null : entry.count, value: entry.pts })),
    ...(bonus ? [{ key: 'bonus', label: `Bonus ${player.b1_bonus_label ?? ''}`.trim(), count: null, value: bonus }] : [])]
  if (rows.length === 0) return null

  return (
    <section className="pf-panel" aria-labelledby="pf-sources-title">
      <header className="pf-panel__head"><div><h2 id="pf-sources-title">De dónde salen sus puntos</h2><p>{pts(player.sfa_pts)} pts en total</p></div></header>
      <div className="pf-stack" aria-hidden="true">
        {rows.map((row) => <i key={row.key} className={`is-${row.key}`} style={{ flexGrow: row.value }} />)}
      </div>
      <ul className="pf-sources">
        {rows.map((row) => (
          <li key={row.key}>
            <i className={`is-${row.key}`} aria-hidden="true" />
            <span>{row.label}{row.count != null && <small> · {row.count}</small>}</span>
            <b>{pts(row.value)}</b>
            <em>{Math.round((row.value / total) * 100)} %</em>
          </li>
        ))}
      </ul>
    </section>
  )
}

type ContextStat = { key: string; title: string; hint: string; hits: number; total: number; share: number }

export function ProfileContext({ events, fixtures, team }: { events: PlayerEvent[]; fixtures: PlayerFixture[]; team: string }) {
  const actions = events.filter((event) => event.event_type !== 'stats')
  if (actions.length === 0) return null
  const byFixture = new Map(fixtures.map((fixture) => [fixture.fixture_id, fixture]))
  const totalPts = actions.reduce((sum, action) => sum + action.pts, 0) || 1

  const levelOrBehind = (action: PlayerEvent) => {
    const fixture = byFixture.get(action.fixture_id)
    const own = fixture?.player_team ?? team
    const [home = 0, away = 0] = (action.score_before ?? '0:0').split(':').map(Number)
    const diff = action.home_team === own ? home - away : away - home
    return diff <= 0
  }

  const build = (key: string, title: string, hint: string, test: (action: PlayerEvent) => boolean): ContextStat => {
    const hit = actions.filter(test)
    return { key, title, hint, hits: hit.length, total: actions.length, share: hit.reduce((sum, action) => sum + action.pts, 0) / totalPts }
  }

  const stats: ContextStat[] = [
    build('tight', 'Con el partido igualado o en contra', 'Goles y asistencias cuando su equipo no ganaba', levelOrBehind),
    build('pressure', 'En momentos de presión', 'Multiplicador de momento por encima de ×1: minutos finales o marcador apretado', (action) => action.m3 > 1),
    build('away', 'Lejos de casa', 'Acciones jugando de visitante', (action) => action.mvisit > 1),
    build('stage', 'En fases de peso', 'Acciones en Champions, finales o eliminatorias', (action) => action.m2 > 1),
  ]

  return (
    <section className="pf-panel" aria-labelledby="pf-context-title">
      <header className="pf-panel__head">
        <div><h2 id="pf-context-title">En qué contexto suma</h2><p>Sus {actions.length} goles y asistencias, según el momento y el rival</p></div>
      </header>
      <ul className="pf-context">
        {stats.map((stat) => {
          const pct = stat.total > 0 ? stat.hits / stat.total : 0
          return (
            <li key={stat.key}>
              <span className="pf-ring" style={{ '--p': pct } as CSSProperties} aria-hidden="true"><b>{Math.round(pct * 100)}%</b></span>
              <span className="pf-context__copy">
                <strong>{stat.title}</strong>
                <small>{stat.hits} de {stat.total} acciones · {Math.round(stat.share * 100)} % de esos puntos</small>
                <em>{stat.hint}</em>
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/* ── By competition ─────────────────────────────────────────────────────── */

export function ProfileCompetitions({ fixtures }: { fixtures: PlayerFixture[] }) {
  const groups = new Map<string, { matches: number; goals: number; assists: number; minutes: number; points: number }>()
  for (const fixture of fixtures) {
    const group = groups.get(fixture.competition) ?? { matches: 0, goals: 0, assists: 0, minutes: 0, points: 0 }
    group.matches += 1
    group.goals += goalsIn(fixture)
    group.assists += assistsIn(fixture)
    group.minutes += fixture.minutes
    group.points += fixture.sfa_pts
    groups.set(fixture.competition, group)
  }
  const rows = [...groups.entries()].sort((a, b) => b[1].points - a[1].points)
  if (rows.length === 0) return null
  const total = rows.reduce((sum, [, group]) => sum + Math.max(group.points, 0), 0) || 1

  return (
    <section className="pf-panel" aria-labelledby="pf-comp-title">
      <header className="pf-panel__head"><div><h2 id="pf-comp-title">Por competición</h2><p>Dónde ha sumado esta temporada</p></div></header>
      <ul className="pf-comps">
        {rows.map(([name, group]) => {
          const logo = tournamentCompetitionLogoByName(name)
          return (
            <li key={name}>
              <span className="pf-comps__name">
                <span className="tp-tile">{logo ? <img src={logo} alt="" /> : competitionLabel(name).slice(0, 2).toUpperCase()}</span>
                <strong>{competitionLabel(name)}</strong>
                <b>{pts(group.points)} pts</b>
              </span>
              <span className="pf-comps__nums">
                <span><b>{group.matches}</b> partidos</span>
                <span><b>{group.goals}</b> goles</span>
                <span><b>{group.assists}</b> asist.</span>
                <span><b>{pts(group.matches ? group.points / group.matches : 0)}</b> pts/partido</span>
              </span>
              <i className="pf-comps__bar" aria-hidden="true"><em style={{ width: `${(Math.max(group.points, 0) / total) * 100}%` }} /></i>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/* ── Su perfil: per-90 radar vs previous season + three focused cards ──── */

type Axis = { key: string; label: string; elite: number; value: (stats: PlayerSeasonStats) => number; format: (stats: PlayerSeasonStats) => string }

const per90 = (value: number, stats: PlayerSeasonStats) => (stats.minutes > 0 ? (value / stats.minutes) * 90 : 0)
const two = (value: number) => value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// "Elite" = what a top season looks like per 90 minutes; each axis fills up to that line.
const AXES: Axis[] = [
  { key: 'goals', label: 'Goles', elite: 0.9, value: (s) => per90(s.goals, s), format: (s) => `${two(per90(s.goals, s))} por 90'` },
  { key: 'assists', label: 'Asistencias', elite: 0.6, value: (s) => per90(s.assists, s), format: (s) => `${two(per90(s.assists, s))} por 90'` },
  { key: 'key', label: 'Pases clave', elite: 3, value: (s) => per90(s.passes_key, s), format: (s) => `${one(per90(s.passes_key, s))} por 90'` },
  { key: 'dribbles', label: 'Regates', elite: 4, value: (s) => per90(s.dribbles_won, s), format: (s) => s.dribble_success_rate != null ? `${Math.round(s.dribble_success_rate * 100)} % de éxito` : `${one(per90(s.dribbles_won, s))} por 90'` },
  { key: 'shots', label: 'Remate', elite: 2, value: (s) => per90(s.shots_on, s), format: (s) => (s.shots_total ? `${Math.round((s.shots_on / s.shots_total) * 100)} % a puerta` : '—') },
  { key: 'duels', label: 'Duelos', elite: 9, value: (s) => per90(s.duels_won, s), format: (s) => s.duel_win_rate != null ? `${Math.round(s.duel_win_rate * 100)} % ganados` : `${one(per90(s.duels_won, s))} por 90'` },
  { key: 'defense', label: 'Defensa', elite: 4, value: (s) => per90(s.tackles_won + s.interceptions + s.blocks, s), format: (s) => `${one(per90(s.tackles_won + s.interceptions + s.blocks, s))} acciones por 90'` },
  { key: 'pass', label: 'Pase', elite: 92, value: (s) => s.passes_accuracy_avg, format: (s) => `${Math.round(s.passes_accuracy_avg)} % de acierto` },
]

const COUNTS: Record<string, (s: PlayerSeasonStats) => number> = {
  goals: (s) => s.goals,
  assists: (s) => s.assists,
  key: (s) => s.passes_key,
  dribbles: (s) => s.dribbles_won,
  shots: (s) => s.shots_on,
  duels: (s) => s.duels_won,
}

function previousSeasonScope(scope: string, available: string[]) {
  const match = /^season-(\d{4})$/.exec(scope)
  if (!match) return null
  const target = `season-${Number(match[1]) - 1}`
  return available.includes(target) ? target : null
}

function Radar({ current, previous }: { current: PlayerSeasonStats; previous: PlayerSeasonStats | null }) {
  const size = 260
  const center = size / 2
  const radius = 92
  const angle = (index: number) => (Math.PI * 2 * index) / AXES.length - Math.PI / 2
  const point = (index: number, ratio: number) => {
    const r = radius * Math.min(Math.max(ratio, 0), 1.08)
    return `${center + Math.cos(angle(index)) * r},${center + Math.sin(angle(index)) * r}`
  }
  const shape = (stats: PlayerSeasonStats) => AXES.map((axis, index) => point(index, axis.value(stats) / axis.elite)).join(' ')

  return (
    <svg className="pf-radar" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Perfil por 90 minutos frente a una temporada de élite">
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon key={ring} className="pf-radar__ring" points={AXES.map((_, index) => point(index, ring)).join(' ')} />
      ))}
      {AXES.map((axis, index) => (
        <line key={axis.key} className="pf-radar__spoke" x1={center} y1={center} x2={center + Math.cos(angle(index)) * radius} y2={center + Math.sin(angle(index)) * radius} />
      ))}
      {previous && <polygon className="pf-radar__prev" points={shape(previous)} />}
      <polygon className="pf-radar__now" points={shape(current)} />
      {AXES.map((axis, index) => {
        const x = center + Math.cos(angle(index)) * (radius + 20)
        const y = center + Math.sin(angle(index)) * (radius + 20)
        const anchor = Math.abs(x - center) < 6 ? 'middle' : x > center ? 'start' : 'end'
        return <text key={axis.key} className="pf-radar__label" x={x} y={y} textAnchor={anchor} dominantBaseline="middle">{axis.label}</text>
      })}
    </svg>
  )
}

export function ProfileStyle({ playerId, scope, available, stats, matches }: {
  playerId: number
  scope: string
  available: string[]
  stats: PlayerSeasonStats | null
  matches: number
}) {
  const [previous, setPrevious] = useState<PlayerSeasonStats | null>(null)
  const prevScope = previousSeasonScope(scope, available)

  useEffect(() => {
    let cancelled = false
    setPrevious(null)
    if (!prevScope) return undefined
    fetchPlayerSeasonStats(playerId, undefined, prevScope)
      .then((result) => { if (!cancelled && result && result.minutes > 0) setPrevious(result) })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [playerId, prevScope])

  if (!stats || stats.minutes === 0) return null
  const s = stats
  const shotsPerGoal = s.goals > 0 ? s.shots_total / s.goals : null
  const funnelMax = Math.max(s.shots_total, 1)
  const creation = [
    { label: 'Pases clave', value: s.passes_key },
    { label: 'Regates', value: s.dribbles_won },
    { label: 'Faltas recibidas', value: s.fouls_drawn },
    { label: 'Asistencias', value: s.assists },
  ]
  const creationMax = Math.max(...creation.map((item) => item.value), 1)
  const duelPct = s.duel_win_rate != null ? Math.round(s.duel_win_rate * 100) : s.duels_total ? Math.round((s.duels_won / s.duels_total) * 100) : 0
  const passPct = Math.round(s.passes_accuracy_avg)
  const currentLabel = scope.startsWith('season-') ? seasonLabel(scope.slice(7)) : 'Periodo actual'

  return (
    <section className="pf-style" aria-labelledby="pf-style-title">
      <div className="pf-panel pf-style__main">
        <header className="pf-panel__head">
          <div><h2 id="pf-style-title">Su perfil</h2><p>Por cada 90 minutos jugados, comparado con una temporada de élite</p></div>
          <span className="pf-legend">
            <span><i className="is-now" />{currentLabel}</span>
            {previous && prevScope && <span><i className="is-prev" />{seasonLabel(prevScope.slice(7))}</span>}
          </span>
        </header>
        <div className="pf-style__grid">
          <Radar current={s} previous={previous} />
          <ul className="pf-axes">
            {AXES.filter((axis) => axis.key !== 'pass' && axis.key !== 'defense').map((axis) => {
              const ratio = Math.min(axis.value(s) / axis.elite, 1)
              const prevRatio = previous ? Math.min(axis.value(previous) / axis.elite, 1) : null
              return (
                <li key={axis.key}>
                  <span className="pf-axes__label">{axis.label}</span>
                  <small>{axis.format(s)}</small>
                  <b>{COUNTS[axis.key]?.(s) ?? ''}</b>
                  <i aria-hidden="true">
                    <em style={{ width: `${ratio * 100}%` }} />
                    {prevRatio != null && <u style={{ left: `${prevRatio * 100}%` }} />}
                  </i>
                </li>
              )
            })}
          </ul>
        </div>
      </div>

      <div className="pf-style__cards">
        <article className="pf-panel pf-focus">
          <span className="pf-eyebrow">Remate</span>
          <h3>{shotsPerGoal ? `Un gol cada ${one(shotsPerGoal)} tiros` : `${s.shots_total} tiros sin gol`}</h3>
          <ul className="pf-funnel">
            <li style={{ '--w': 1 } as CSSProperties}><b>{s.shots_total}</b> tiros</li>
            <li className="is-mid" style={{ '--w': s.shots_on / funnelMax } as CSSProperties}><b>{s.shots_on}</b> a puerta</li>
            <li className="is-top" style={{ '--w': Math.max(s.goals / funnelMax, 0.18) } as CSSProperties}><b>{s.goals}</b> goles</li>
          </ul>
          <small>{s.goals > 0 ? `Un gol cada ${Math.round(s.minutes / s.goals)} minutos` : 'Todavía sin goles'}</small>
        </article>

        <article className="pf-panel pf-focus">
          <span className="pf-eyebrow">Creación</span>
          <h3>{one(per90(s.passes_key, s))} pases clave cada 90'</h3>
          <ul className="pf-mini-bars">
            {creation.map((item) => (
              <li key={item.label}>
                <span>{item.label}</span>
                <i aria-hidden="true"><em style={{ width: `${(item.value / creationMax) * 100}%` }} /></i>
                <b>{item.value}</b>
              </li>
            ))}
          </ul>
          <small>{s.assists} asistencias en {matches} partidos</small>
        </article>

        <article className="pf-panel pf-focus">
          <span className="pf-eyebrow">Con balón</span>
          <h3>{Math.round(per90(s.passes_total, s))} pases cada 90'</h3>
          <div className="pf-dials">
            <span className="pf-dial" style={{ '--p': passPct / 100 } as CSSProperties}><b>{passPct}%</b><small>pases buenos</small></span>
            <span className="pf-dial is-blue" style={{ '--p': duelPct / 100 } as CSSProperties}><b>{duelPct}%</b><small>duelos ganados</small></span>
          </div>
          <small>{s.passes_total.toLocaleString('es-ES')} pases · {s.duels_total} duelos · {s.tackles_won} entradas · {s.interceptions} intercepciones</small>
        </article>
      </div>
    </section>
  )
}

/* ── Fixture table: sort, filter by competition, expandable points summary ── */

const TABLE_PREVIEW = 8

type FixtureSort = 'recent' | 'best'

const ACTION_NAMES: Record<string, string> = {
  goal: 'Gol', goal_penalty: 'Gol de penal', assist: 'Asistencia', corner_assist: 'Córner asistido',
}

/** Plain-language reasons behind an action's value (no raw multipliers). */
export function actionReasons(event: PlayerEvent, ownTeam: string) {
  const reasons: Array<{ text: string; up: boolean }> = []
  // Without a recorded score the game state is unknown: say "Momento decisivo" rather than guess a draw.
  const diff = event.score_before ? (() => {
    const [home = 0, away = 0] = event.score_before.split(':').map(Number)
    return event.home_team === ownTeam ? home - away : away - home
  })() : null
  if (event.m3 > 1) reasons.push({ text: diff == null || diff > 0 ? 'Momento decisivo' : diff < 0 ? 'Perdiendo' : 'Empate', up: true })
  else if (event.m3 < 1) reasons.push({ text: 'Partido resuelto', up: false })
  if (event.m2 > 1) reasons.push({ text: 'Fase de peso', up: true })
  if (event.m1 >= 1) reasons.push({ text: 'Rival de nivel', up: true })
  else if (event.m1 < 0.75) reasons.push({ text: 'Rival menor', up: false })
  if (event.mvisit > 1) reasons.push({ text: 'Fuera de casa', up: true })
  if (event.m4 > 1) reasons.push({ text: 'Remate difícil', up: true })
  return reasons
}

function FixtureSummary({ fixture, events, team }: { fixture: PlayerFixture; events: PlayerEvent[]; team: string }) {
  const ownTeam = fixture.player_team ?? team
  const actions = events
    .filter((event) => event.fixture_id === fixture.fixture_id && event.event_type !== 'stats' && event.pts > 0)
    .sort((a, b) => a.minute - b.minute)
  const parts = [
    { key: 'stats', label: 'Juego', value: fixture.breakdown?.stats?.pts ?? 0 },
    { key: 'goal', label: 'Goles', value: (fixture.breakdown?.goal?.pts ?? 0) + (fixture.breakdown?.goal_penalty?.pts ?? 0) },
    { key: 'assist', label: 'Asistencias', value: (fixture.breakdown?.assist?.pts ?? 0) + (fixture.breakdown?.corner_assist?.pts ?? 0) },
  ].filter((part) => part.value !== 0)
  const positive = parts.reduce((sum, part) => sum + Math.max(part.value, 0), 0) || 1
  const passPct = fixture.passes_total > 0 ? Math.round((fixture.passes_accurate / fixture.passes_total) * 100) : null
  const stats = [
    { label: 'Remates', value: `${fixture.shots_total} (${fixture.shots_on} a puerta)` },
    { label: 'Pases', value: `${fixture.passes_accurate}/${fixture.passes_total}${passPct != null ? ` · ${passPct} %` : ''}` },
    { label: 'Pases clave', value: fixture.passes_key },
    { label: 'Regates', value: fixture.dribbles_won },
    { label: 'Duelos ganados', value: fixture.duels_won },
    { label: 'Entradas + intercep.', value: fixture.tackles_won + fixture.interceptions },
  ]

  return (
    <div className="pf-fxsum">
      <div className="pf-fxsum__col">
        <span className="pf-eyebrow">De dónde salen sus {pts(fixture.sfa_pts)} pts</span>
        <div className="pf-fxsum__stack" aria-hidden="true">
          {parts.map((part) => part.value > 0 && <i key={part.key} className={`is-${part.key}`} style={{ flexGrow: part.value }} />)}
        </div>
        <ul className="pf-fxsum__parts">
          {parts.map((part) => (
            <li key={part.key}>
              <i className={`is-${part.key}`} aria-hidden="true" />
              <span>{part.label}</span>
              <b>{pts(part.value)}</b>
              <em>{part.value > 0 ? `${Math.round((part.value / positive) * 100)} %` : ''}</em>
            </li>
          ))}
        </ul>
      </div>

      <div className="pf-fxsum__col">
        <span className="pf-eyebrow">{actions.length ? 'Acciones decisivas' : 'Su partido'}</span>
        {actions.length > 0 ? (
          <ul className="pf-fxsum__actions">
            {actions.map((action) => (
              <li key={action.id}>
                <span className="pf-fxsum__min">{action.minute}'</span>
                <span className="pf-fxsum__what">
                  <strong>{ACTION_NAMES[action.event_type] ?? action.event_type}</strong>
                  <span className="pf-fxsum__tags">
                    {actionReasons(action, ownTeam).map((reason) => <em key={reason.text} className={reason.up ? 'is-up' : 'is-down'}>{reason.text}</em>)}
                  </span>
                </span>
                <b>+{pts(action.pts)}</b>
              </li>
            ))}
          </ul>
        ) : (
          <p className="pf-fxsum__note">Sin goles ni asistencias: todos sus puntos salen del juego.</p>
        )}
        <dl className="pf-fxsum__stats">
          {stats.map((stat) => <div key={stat.label}><dt>{stat.label}</dt><dd>{stat.value}</dd></div>)}
        </dl>
      </div>
    </div>
  )
}

export function ProfileFixtures({ fixtures, events, team, season }: { fixtures: PlayerFixture[]; events: PlayerEvent[]; team: string; season: string }) {
  const [showAll, setShowAll] = useState(false)
  const [sort, setSort] = useState<FixtureSort>('recent')
  const [competition, setCompetition] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  if (fixtures.length === 0) return null

  const competitions = [...new Set(fixtures.map((fixture) => fixture.competition))]
    .sort((a, b) => fixtures.filter((f) => f.competition === b).length - fixtures.filter((f) => f.competition === a).length)
  const filtered = fixtures
    .filter((fixture) => !competition || fixture.competition === competition)
    .sort((a, b) => (sort === 'best' ? b.sfa_pts - a.sfa_pts : b.played_at.localeCompare(a.played_at)))
  const visible = showAll ? filtered : filtered.slice(0, TABLE_PREVIEW)

  return (
    <section className="pf-panel" aria-labelledby="pf-fx-title">
      <header className="pf-panel__head">
        <div><h2 id="pf-fx-title">Partidos</h2><p>{filtered.length} partidos con puntos SFA · pulsa uno para ver su resumen</p></div>
      </header>

      <div className="pf-fx-tools">
        <div className="tp-segment" role="group" aria-label="Ordenar partidos">
          <button type="button" className={sort === 'recent' ? 'is-active' : undefined} aria-pressed={sort === 'recent'} onClick={() => setSort('recent')}>Recientes</button>
          <button type="button" className={sort === 'best' ? 'is-active' : undefined} aria-pressed={sort === 'best'} onClick={() => setSort('best')}>Mejores</button>
        </div>
        {competitions.length > 1 && (
          <div className="tp-segment pf-fx-comps" role="group" aria-label="Filtrar por competición">
            <button type="button" className={!competition ? 'is-active' : undefined} aria-pressed={!competition} onClick={() => setCompetition('')}>Todas</button>
            {competitions.map((name) => {
              const logo = tournamentCompetitionLogoByName(name)
              return (
                <button type="button" key={name} className={competition === name ? 'is-active' : undefined} aria-pressed={competition === name} onClick={() => setCompetition(name)}>
                  {logo && <span className="tp-tile"><img src={logo} alt="" /></span>}
                  {competitionLabel(name)}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="pf-table" role="table" aria-label="Partidos de la temporada">
        <div className="pf-table__head" role="row">
          <span role="columnheader">Fecha</span><span role="columnheader">Rival</span><span role="columnheader">Min</span>
          <span role="columnheader">G</span><span role="columnheader">A</span><span role="columnheader">Nota</span><span role="columnheader">Pts SFA</span>
        </div>
        {visible.map((fixture, index) => {
          const rival = rivalOf(fixture, team)
          const isOpen = open === fixture.fixture_id
          const href = matchHref(fixture, season)
          return (
            <div key={fixture.fixture_id} className={`pf-fx${isOpen ? ' is-open' : ''}`}>
              <button
                type="button"
                className="pf-table__row"
                onClick={() => setOpen(isOpen ? null : fixture.fixture_id)}
                aria-expanded={isOpen}
                aria-controls={`pf-fxsum-${fixture.fixture_id}`}
              >
                <span className="pf-table__date">
                  {sort === 'best' && <i className="pf-fx__rank">{index + 1}</i>}
                  <b>{shortDate(fixture.played_at)}</b><small>{competitionLabel(fixture.competition)}</small>
                </span>
                <span className="pf-table__rival"><small className={rival.home ? 'is-home' : 'is-away'} title={rival.home ? 'Local: jugó en casa' : 'Visitante: jugó fuera de casa'} aria-label={rival.home ? 'Local' : 'Visitante'}>{rival.home ? 'L' : 'V'}</small><Crest src={rival.logo} name={rival.name} size={20} /><span>{rival.name}</span></span>
                <span>{fixture.minutes}'</span>
                <span className={goalsIn(fixture) ? 'is-hit' : undefined}>{goalsIn(fixture)}</span>
                <span className={assistsIn(fixture) ? 'is-hit' : undefined}>{assistsIn(fixture)}</span>
                <span>{fixture.rating != null ? one(fixture.rating) : '—'}</span>
                <b className="pf-table__pts">{pts(fixture.sfa_pts)}<svg className="pf-fx__chev" viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></b>
              </button>
              {isOpen && (
                <div className="pf-fx__body" id={`pf-fxsum-${fixture.fixture_id}`}>
                  <FixtureSummary fixture={fixture} events={events} team={team} />
                  {href && <Link to={href} className="pf-fx__link">Ver el partido completo →</Link>}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {filtered.length > TABLE_PREVIEW && (
        <button type="button" className="pf-more" onClick={() => setShowAll((value) => !value)} aria-expanded={showAll}>
          {showAll ? 'Ver menos' : `Ver los ${filtered.length} partidos`}
        </button>
      )}
    </section>
  )
}

/* ── Honours: a trophy cabinet, then best runs and individual awards ────── */

const HONOR_LABELS: Record<string, string> = {
  top_scorer: 'Bota de oro',
  top_assister: 'Máximo asistidor',
  best_dribbler: 'Mejor regateador',
  duel_king: 'Rey de los duelos',
}

// Optional trophy artwork in /public/images/trophies/<slug>.png; a drawn cup is used until it exists.
const TROPHY_SLUGS: Array<[string, string]> = [
  ['mundial', 'world-cup'], ['copa del mundo', 'world-cup'],
  ['champions', 'champions-league'], ['europa league', 'europa-league'], ['conference', 'conference-league'],
  ['supercopa de europa', 'uefa-super-cup'], ['uefa super', 'uefa-super-cup'],
  ['la liga', 'laliga'], ['premier', 'premier-league'], ['serie a', 'serie-a'], ['bundesliga', 'bundesliga'], ['ligue 1', 'ligue-1'],
  ['copa del rey', 'copa-del-rey'], ['supercopa de espa', 'supercopa-espana'], ['fa cup', 'fa-cup'], ['efl', 'efl-cup'],
  ['community', 'community-shield'], ['coppa italia', 'coppa-italia'], ['supercoppa', 'supercoppa-italiana'],
  ['dfb', 'dfb-pokal'], ['dfl', 'dfl-supercup'], ['coupe de france', 'coupe-de-france'], ['troph', 'trophee-des-champions'],
  ['eurocopa', 'euro'], ['euro', 'euro'], ['copa am', 'copa-america'], ['libertadores', 'libertadores'],
]

/** Short, readable badge for a phase reached ("SF" beats the source's "4"). */
function phaseShort(phase: string) {
  const label = phaseLabel(phase).toLowerCase()
  if (label.includes('semi')) return 'SF'
  if (label.includes('cuartos')) return 'CF'
  if (label.includes('octavos')) return 'OF'
  if (label.includes('dieciseisavos')) return '1/16'
  if (label.startsWith('final')) return 'F'
  if (label.includes('grupo') || label.includes('liga')) return 'FG'
  return phaseBadge(phase)
}

function trophySlug(name: string) {
  const key = name.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  return TROPHY_SLUGS.find(([match]) => key.includes(match))?.[1] ?? null
}

function CupIcon({ size = 66 }: { size?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
      <defs>
        <linearGradient id="pf-cup" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f3dc8b" />
          <stop offset="0.55" stopColor="#C9A84C" />
          <stop offset="1" stopColor="#7d6327" />
        </linearGradient>
      </defs>
      <path fill="url(#pf-cup)" d="M14 6h20v9c0 7-4.4 12-10 12S14 22 14 15V6Z" />
      <path fill="none" stroke="url(#pf-cup)" strokeWidth="3" strokeLinecap="round" d="M14 10H8v3c0 5 3 8 7.5 8M34 10h6v3c0 5-3 8-7.5 8" />
      <path fill="url(#pf-cup)" d="M21 26.5h6V33h-6zM16 33h16l2 7H14z" />
      <rect x="12" y="39" width="24" height="4" rx="1.5" fill="#5c4a1f" />
    </svg>
  )
}

function Trophy({ name }: { name: string }) {
  const [failed, setFailed] = useState(false)
  const slug = trophySlug(name)
  return slug && !failed
    ? <img src={`/images/trophies/${slug}.png`} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
    : <CupIcon />
}

export function ProfileHonors({ achievements, honors }: { achievements: PlayerCompetitionAchievement[]; honors: PlayerIndividualHonor[] }) {
  const titles = new Map<string, { count: number; seasons: string[]; points: number }>()
  for (const item of achievements.filter((entry) => entry.title_count > 0)) {
    const key = competitionLabel(item.competition_name)
    const group = titles.get(key) ?? { count: 0, seasons: [], points: 0 }
    group.count += item.title_count
    group.points += item.bonus_pts
    if (!group.seasons.includes(item.season)) group.seasons.push(item.season)
    titles.set(key, group)
  }
  const cabinet = [...titles.entries()]
    .map(([name, group]) => ({ name, ...group, seasons: group.seasons.sort().reverse() }))
    .sort((a, b) => b.seasons[0].localeCompare(a.seasons[0]) || b.count - a.count)
  const runs = achievements
    .filter((entry) => entry.title_count === 0)
    .sort((a, b) => b.season.localeCompare(a.season) || b.bonus_pts - a.bonus_pts)
    .slice(0, 4)
  const totalTitles = cabinet.reduce((sum, item) => sum + item.count, 0)
  if (cabinet.length === 0 && runs.length === 0 && honors.length === 0) return null

  return (
    <section className="pf-panel pf-honors" aria-labelledby="pf-honors-title">
      <header className="pf-panel__head">
        <div>
          <h2 id="pf-honors-title">
            Palmarés
            {totalTitles > 0 && <span className="pf-honors__count">{totalTitles} {totalTitles === 1 ? 'título' : 'títulos'}</span>}
          </h2>
          <p>Cada título y cada fase alcanzada suman puntos SFA</p>
        </div>
      </header>

      {cabinet.length > 0 && (
        <ul className="pf-cabinet">
          {cabinet.map((item) => (
            <li key={item.name}>
              <span className="pf-cabinet__trophy"><Trophy name={item.name} /></span>
              {item.count > 1 && <span className="pf-cabinet__times">×{item.count}</span>}
              <strong>{item.name}</strong>
              <small>{item.seasons.map((season) => seasonLabel(season)).join(' · ')}</small>
              {item.points > 0 && <b>+{pts(item.points)} pts</b>}
            </li>
          ))}
        </ul>
      )}

      {(runs.length > 0 || honors.length > 0) && (
        <div className="pf-honors__cols">
          {runs.length > 0 && (
            <div className="pf-runs">
              <span className="pf-eyebrow">Mejores fases</span>
              <ul>
                {runs.map((run) => (
                  <li key={run.achievement_id}>
                    <span className="pf-runs__badge" aria-hidden="true">{phaseShort(run.phase)}</span>
                    <span className="pf-runs__copy">
                      <strong>{phaseLabel(run.phase)} · {competitionLabel(run.competition_name)}</strong>
                      <small>{seasonLabel(run.season)}</small>
                    </span>
                    {run.bonus_pts > 0 && <b>+{pts(run.bonus_pts)}</b>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {honors.length > 0 && (
            <div className="pf-runs">
              <span className="pf-eyebrow">Distinciones individuales</span>
              <ul>
                {honors.map((honor) => (
                  <li key={honor.honor_id}>
                    <span className="pf-runs__badge is-award" aria-hidden="true">★</span>
                    <span className="pf-runs__copy">
                      <strong>{HONOR_LABELS[honor.honor_type] ?? honor.honor_type}</strong>
                      <small>{honor.context_label} · {honor.scope_label} · {honorEvidence(honor)}</small>
                    </span>
                    {honor.bonus_pts > 0 && <b>+{pts(honor.bonus_pts)}</b>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function honorEvidence(honor: PlayerIndividualHonor) {
  const value = Math.round(honor.metric_value).toLocaleString('es-ES')
  if (honor.honor_type === 'top_scorer') return `${value} goles`
  if (honor.honor_type === 'top_assister') return `${value} asistencias`
  const rate = honor.metric_rate != null ? ` · ${Math.round(honor.metric_rate * 100)} %` : ''
  return honor.honor_type === 'best_dribbler' ? `${value} regates${rate}` : `${value} duelos${rate}`
}
