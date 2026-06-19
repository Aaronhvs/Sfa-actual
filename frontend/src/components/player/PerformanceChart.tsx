import { useMemo, useState } from 'react'
import type { PlayerFixture } from '../../types'

interface Props {
  fixtures: PlayerFixture[]
  playerTeam: string
}

const W = 1000
const H = 200
const PL = 46   // left pad — Y labels
const PR = 16   // right pad
const PT = 14   // top pad
const PB = 28   // bottom pad — X labels
const IW = W - PL - PR
const IH = H - PT - PB

type Kind = 'hat' | 'elite' | 'goal' | 'assist' | null

function detectKind(f: PlayerFixture): Kind {
  const g = (f.breakdown?.['goal']?.count ?? 0) + (f.breakdown?.['goal_penalty']?.count ?? 0)
  if (g >= 3) return 'hat'
  if (f.sfa_pts >= 2500) return 'elite'
  if (g >= 1) return 'goal'
  if ((f.breakdown?.['assist']?.count ?? 0) > 0) return 'assist'
  return null
}

function fmtK(n: number) {
  if (n === 0) return '0'
  return n >= 1000 ? `${n / 1000}k` : String(n)
}

function fmtPts(n: number) { return Math.round(n).toLocaleString('es-ES') }

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })
}

const ACTION_LABELS: Record<string, [string, string]> = {
  goal: ['gol', 'goles'],
  goal_penalty: ['gol de penal', 'goles de penal'],
  assist: ['asistencia', 'asistencias'],
  corner_assist: ['asistencia de córner', 'asistencias de córner'],
  key_pass: ['pase clave', 'pases clave'],
  shots_on: ['disparo a puerta', 'disparos a puerta'],
  dribbles_won: ['regate ganado', 'regates ganados'],
  duels_won: ['duelo ganado', 'duelos ganados'],
  tackles_won: ['tackle ganado', 'tackles ganados'],
  interceptions: ['intercepción', 'intercepciones'],
  blocks: ['bloqueo', 'bloqueos'],
  clearances: ['despeje', 'despejes'],
  fouls_drawn: ['falta recibida', 'faltas recibidas'],
  stats: ['rendimiento técnico', 'rendimientos técnicos'],
}

function formatAction(action: string, count: number): string {
  const labels = ACTION_LABELS[action]
  if (!labels) return `${count} ${action.replace(/_/g, ' ')}`
  return `${count} ${count === 1 ? labels[0] : labels[1]}`
}

interface Pt {
  x: number; y: number
  trendY: number
  logoY: number
  fx: PlayerFixture
  kind: Kind
  season: string
  goals: number; assists: number
  opponent: string
  oppLogo: string | null
}

function fixtureSeason(iso: string): string {
  const date = new Date(iso)
  const year = date.getUTCFullYear()
  return String(date.getUTCMonth() >= 6 ? year : year - 1)
}

function smoothPath(points: { x: number; y: number }[]): string {
  let path = `M${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    const cx = ((a.x + b.x) / 2).toFixed(1)
    path += ` C${cx} ${a.y.toFixed(1)},${cx} ${b.y.toFixed(1)},${b.x.toFixed(1)} ${b.y.toFixed(1)}`
  }
  return path
}

export default function PerformanceChart({ fixtures, playerTeam }: Props) {
  const [hovered, setHovered] = useState<Pt | null>(null)
  const [selected, setSelected] = useState<Pt | null>(null)

  const chart = useMemo(() => {
    if (fixtures.length < 3) return null

    const sorted = [...fixtures].sort(
      (a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime()
    )

    const maxRaw = Math.max(...sorted.map(f => f.sfa_pts))
    const maxY = Math.max(Math.ceil(maxRaw / 1000) * 1000, 1000)

    const toY = (v: number) => PT + IH - (v / maxY) * IH
    const seasons = sorted.map((fixture) => fixtureSeason(fixture.played_at))
    const seasonBreaks = seasons.reduce<number[]>((breaks, currentSeason, index) => {
      if (index > 0 && currentSeason !== seasons[index - 1]) breaks.push(index)
      return breaks
    }, [])
    const gapUnits = 2.5
    const totalUnits = Math.max(sorted.length - 1 + seasonBreaks.length * gapUnits, 1)
    const xUnits = sorted.map((_, index) => {
      const priorBreaks = seasonBreaks.filter((breakIndex) => breakIndex <= index).length
      return index + priorBreaks * gapUnits
    })
    const rolling = sorted.map((_, index) => {
      let seasonStart = index
      while (seasonStart > 0 && seasons[seasonStart - 1] === seasons[index]) {
        seasonStart -= 1
      }
      const window = sorted.slice(Math.max(seasonStart, index - 4), index + 1)
      return window.reduce((sum, fixture) => sum + fixture.sfa_pts, 0) / window.length
    })

    const pts: Pt[] = sorted.map((f, index) => {
      const fixturePlayerTeam = f.player_team ?? playerTeam
      const isHome = f.home_team === fixturePlayerTeam
      const isAway = f.away_team === fixturePlayerTeam
      const fallbackIsHome = f.home_team === playerTeam
      return {
        x: PL + (xUnits[index] / totalUnits) * IW,
        y: toY(f.sfa_pts),
        trendY: toY(rolling[index]),
        logoY: toY(f.sfa_pts),
        fx: f,
        kind: detectKind(f),
        season: seasons[index],
        goals: (f.breakdown?.['goal']?.count ?? 0) + (f.breakdown?.['goal_penalty']?.count ?? 0),
        assists: f.breakdown?.['assist']?.count ?? 0,
        opponent: isHome ? f.away_team : isAway ? f.home_team : fallbackIsHome ? f.away_team : f.home_team,
        oppLogo: isHome
          ? f.away_team_logo
          : isAway
            ? f.home_team_logo
            : fallbackIsHome
              ? f.away_team_logo
              : f.home_team_logo,
      }
    })
    const logoOffsets = [0, -14, 14, -26, 26]
    for (let index = 0; index < pts.length; index++) {
      const point = pts[index]
      const nearby = pts.slice(Math.max(0, index - 6), index)
        .filter((candidate) => point.x - candidate.x < 22)
      const offset = logoOffsets.find((candidateOffset) => {
        const candidateY = Math.max(PT + 8, Math.min(PT + IH - 8, point.y + candidateOffset))
        return nearby.every((candidate) =>
          Math.abs(candidate.logoY - candidateY) >= 16
          || Math.abs(candidate.x - point.x) >= 18
        )
      }) ?? logoOffsets[index % logoOffsets.length]
      point.logoY = Math.max(PT + 8, Math.min(PT + IH - 8, point.y + offset))
    }

    const bY = (PT + IH).toFixed(1)
    const seasonGroups = pts.reduce<Pt[][]>((groups, point) => {
      const current = groups[groups.length - 1]
      if (!current || current[0].season !== point.season) groups.push([point])
      else current.push(point)
      return groups
    }, [])
    const lineSegments = seasonGroups.map((group) => smoothPath(group))
    const trendSegments = seasonGroups.map((group) =>
      smoothPath(group.map((point) => ({ x: point.x, y: point.trendY }))),
    )
    const areaSegments = trendSegments.map((trend, index) => {
      const group = seasonGroups[index]
      return `${trend} L${group[group.length - 1].x.toFixed(1)} ${bY} L${group[0].x.toFixed(1)} ${bY}Z`
    })

    // Y grid ticks
    const yTicks: { y: number; label: string }[] = []
    for (let v = 0; v <= maxY; v += 1000) yTicks.push({ y: toY(v), label: fmtK(v) })

    const xTicks: { x: number; label: string }[] = []
    let lastM = ''
    for (const [index, p] of pts.entries()) {
      const m = new Date(p.fx.played_at).toLocaleDateString('es-ES', { month: 'short' })
      if (m !== lastM && (index === 0 || index === pts.length - 1 || index % 4 === 0)) {
        xTicks.push({ x: p.x, label: m })
      }
      lastM = m
    }

    const best = sorted.reduce((b, f) => f.sfa_pts > b.sfa_pts ? f : b, sorted[0])
    const recent = rolling[rolling.length - 1]
    const currentSeasonFixtures = sorted.filter(
      (fixture) => fixtureSeason(fixture.played_at) === seasons[seasons.length - 1],
    )
    const previousFixtures = currentSeasonFixtures.slice(-10, -5)
    const previous = previousFixtures.length > 0
      ? previousFixtures.reduce((sum, fixture) => sum + fixture.sfa_pts, 0) / previousFixtures.length
      : recent
    const trendDelta = previous > 0 ? ((recent - previous) / previous) * 100 : 0
    const featuredThreshold = [...sorted]
      .map((fixture) => fixture.sfa_pts)
      .sort((a, b) => a - b)[Math.floor(sorted.length * 0.85)] ?? maxRaw
    const separators = seasonBreaks.map((index) => ({
      x: (pts[index - 1].x + pts[index].x) / 2,
      nextSeason: seasons[index],
    }))

    return {
      pts, lineSegments, trendSegments, areaSegments, yTicks, xTicks, best,
      recent, trendDelta, featuredThreshold, separators,
    }
  }, [fixtures, playerTeam])

  if (!chart) return null

  const {
    pts, lineSegments, trendSegments, areaSegments, yTicks, xTicks, best,
    recent, trendDelta, featuredThreshold, separators,
  } = chart
  const featured = pts.filter((p) =>
    p.goals >= 2 || p.kind === 'hat' || p.fx.sfa_pts >= featuredThreshold
  )
  const featuredIds = new Set(featured.map((point) => point.fx.fixture_id))

  const active = selected ?? hovered
  const ttX = active ? (active.x / W) * 100 : 0
  const ttY = active ? (active.logoY / H) * 100 : 0
  const flipLeft = active ? active.x / W > 0.7 : false
  const breakdown = active
    ? Object.entries(active.fx.breakdown ?? {})
        .filter(([, item]) => item.count > 0 || item.pts !== 0)
        .sort(([, a], [, b]) => Math.abs(b.pts) - Math.abs(a.pts))
    : []
  const technicalContext = active ? [
    active.fx.rating != null ? `Rating ${active.fx.rating.toFixed(1)}` : null,
    active.fx.shots_on > 0 ? `${active.fx.shots_on} a puerta` : null,
    active.fx.dribbles_won > 0 ? `${active.fx.dribbles_won} regates` : null,
    active.fx.duels_won > 0 ? `${active.fx.duels_won} duelos` : null,
    active.fx.tackles_won + active.fx.interceptions > 0
      ? `${active.fx.tackles_won + active.fx.interceptions} recuperaciones`
      : null,
  ].filter((item): item is string => item !== null) : []

  return (
    <div className="perf-chart">

      {/* Header — mirrors Transfermarkt style */}
      <div className="perf-chart__head">
        <div className="perf-chart__head-left">
          <span className="perf-chart__eyebrow">Rendimiento por partido</span>
          <p className="perf-chart__peak">
            Mejor:{' '}
            <strong>{fmtPts(best.sfa_pts)} pts</strong>
            <span className="perf-chart__peak-ctx">
              {' '}· {best.home_team} vs {best.away_team} · {fmtDate(best.played_at)}
            </span>
          </p>
          <div className="perf-chart__legend" aria-label="Leyenda del gráfico">
            <span><i className="is-trend" /> Tendencia de 5 partidos</span>
            <span><i className="is-match" /> Resultado por partido</span>
          </div>
        </div>
        <div className="perf-chart__avg-block">
          <span className="perf-chart__avg-num">{fmtPts(recent)}</span>
          <span className="perf-chart__avg-lbl">media últimos 5</span>
          <span className={`perf-chart__trend${trendDelta >= 0 ? ' is-up' : ' is-down'}`}>
            {trendDelta >= 0 ? '↑' : '↓'} {Math.abs(Math.round(trendDelta))}% tendencia
          </span>
        </div>
      </div>

      {/* Double-bezel container */}
      <div className="perf-chart__shell">
        <div className="perf-chart__bezel">
          <div className="perf-chart__stage">

            <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
              <defs>
                <linearGradient id="pc-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#C9A84C" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#C9A84C" stopOpacity="0.01" />
                </linearGradient>
                <filter id="pc-glow" x="-20%" y="-80%" width="140%" height="260%">
                  <feGaussianBlur stdDeviation="1.5" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {/* Horizontal grid lines + Y labels */}
              {yTicks.map(({ y, label }) => (
                <g key={label}>
                  <line
                    x1={PL} y1={y} x2={W - PR} y2={y}
                    stroke={label === '0' ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)'}
                    strokeWidth="1"
                    strokeDasharray={label !== '0' ? '4 5' : undefined}
                  />
                  <text x={PL - 6} y={y + 4} className="pc-y-lbl" textAnchor="end">
                    {label}
                  </text>
                </g>
              ))}

              {/* X month labels */}
              {xTicks.map(({ x, label }) => (
                <text key={`${label}-${x}`} x={x} y={H - 5} className="pc-x-lbl" textAnchor="middle">
                  {label}
                </text>
              ))}

              {separators.map(({ x, nextSeason }) => (
                <g key={nextSeason}>
                  <line
                    x1={x} y1={PT}
                    x2={x} y2={PT + IH}
                    stroke="rgba(255,255,255,0.12)"
                    strokeWidth="1"
                    strokeDasharray="2 5"
                  />
                  <text x={x + 6} y={PT + 10} className="pc-season-lbl">
                    {nextSeason}/{String(Number(nextSeason) + 1).slice(-2)}
                  </text>
                </g>
              ))}

              {/* Area fill */}
              {areaSegments.map((area, index) => (
                <path key={`area-${index}`} d={area} fill="url(#pc-grad)" className="pc-area" />
              ))}

              {/* Individual match line */}
              {lineSegments.map((line, index) => (
                <path
                  key={`raw-${index}`}
                  d={line}
                  fill="none"
                  stroke="rgba(255,255,255,0.18)"
                  strokeWidth="1"
                  strokeLinecap="round"
                  className="pc-line pc-line--raw"
                />
              ))}

              {/* Five-match moving average */}
              {trendSegments.map((trend, index) => (
                <path
                  key={`trend-${index}`}
                  d={trend}
                  fill="none"
                  stroke="#C9A84C"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  filter="url(#pc-glow)"
                  className="pc-line pc-line--trend"
                />
              ))}

              {pts.map((p) => (
                <circle
                  key={`dot-${p.fx.fixture_id}`}
                  cx={p.x}
                  cy={p.y}
                  r="1.8"
                  className="pc-match-dot"
                />
              ))}

              {/* Hover crosshair */}
              {active && (
                <>
                  <line
                    x1={active.x} y1={PT}
                    x2={active.x} y2={PT + IH}
                    stroke="rgba(255,255,255,0.2)"
                    strokeWidth="1"
                    strokeDasharray="3 4"
                    pointerEvents="none"
                  />
                  <circle cx={active.x} cy={active.y} r="4"
                    fill="#C9A84C" pointerEvents="none" />
                </>
              )}

              {pts.filter((p) => Math.abs(p.logoY - p.y) > 1).map((p) => (
                <line
                  key={`stem-${p.fx.fixture_id}`}
                  x1={p.x}
                  y1={p.y}
                  x2={p.x}
                  y2={p.logoY}
                  className="pc-logo-stem"
                />
              ))}

              {/* Key moment outer ring markers */}
              {featured.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x} cy={p.logoY} r="11"
                  fill="#0d0d0d"
                  stroke={p.kind === 'hat' ? '#C9A84C' : 'rgba(201,168,76,0.6)'}
                  strokeWidth={p.kind === 'hat' ? '2' : '1.5'}
                  className="pc-ring"
                  style={{ animationDelay: `${1.2 + i * 0.1}s` }}
                />
              ))}

              {/* Large invisible hit areas for hover */}
              {pts.map((p, i) => (
                <circle
                  key={i} cx={p.x} cy={p.logoY} r="14"
                  fill="transparent"
                  className="pc-hit-area"
                  role="button"
                  tabIndex={0}
                  aria-label={`${p.opponent}, ${fmtDate(p.fx.played_at)}, ${fmtPts(p.fx.sfa_pts)} puntos. Ver desglose.`}
                  onMouseEnter={() => setHovered(p)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(p)}
                  onBlur={() => setHovered(null)}
                  onClick={() => setSelected((current) =>
                    current?.fx.fixture_id === p.fx.fixture_id ? null : p
                  )}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                      setSelected(null)
                    }
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setSelected((current) =>
                        current?.fx.fixture_id === p.fx.fixture_id ? null : p
                      )
                    }
                  }}
                />
              ))}
            </svg>

            {/* Every match keeps its football identity; collisions are offset above. */}
            {pts.map((p) =>
              p.oppLogo ? (
                <div
                  key={p.fx.fixture_id}
                  className={`pc-logo${featuredIds.has(p.fx.fixture_id) ? ' pc-logo--featured' : ''}${active?.fx.fixture_id === p.fx.fixture_id ? ' pc-logo--active' : ''}`}
                  style={{ left: `${(p.x / W) * 100}%`, top: `${(p.logoY / H) * 100}%` }}
                >
                  <img
                    src={p.oppLogo}
                    alt={p.opponent}
                    onError={(e) => {
                      (e.target as HTMLImageElement).closest<HTMLElement>('.pc-logo')!.style.display = 'none'
                    }}
                  />
                </div>
              ) : (
                <div
                  key={p.fx.fixture_id}
                  className={`pc-logo pc-logo--text${featuredIds.has(p.fx.fixture_id) ? ' pc-logo--featured' : ''}${active?.fx.fixture_id === p.fx.fixture_id ? ' pc-logo--active' : ''}`}
                  style={{ left: `${(p.x / W) * 100}%`, top: `${(p.logoY / H) * 100}%` }}
                >
                  {p.opponent.slice(0, 3).toUpperCase()}
                </div>
              )
            )}

            {/* Tooltip — same layout as reference screenshot */}
            {active && (
              <div
                className={`pc-tooltip${selected ? ' pc-tooltip--selected' : ''}`}
                style={{
                  left: flipLeft
                    ? `calc(${ttX}% - 256px)`
                    : `calc(${ttX}% + 16px)`,
                  top: `calc(${ttY}% - 54px)`,
                }}
                role="status"
              >
                {active.oppLogo ? (
                  <img
                    src={active.oppLogo}
                    alt=""
                    className="pc-tooltip__logo"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                ) : (
                  <div className="pc-tooltip__logo-fb">
                    {active.opponent.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div className="pc-tooltip__body">
                  <div className="pc-tooltip__opp">{active.opponent}</div>
                  <div className="pc-tooltip__date">{fmtDate(active.fx.played_at)}</div>
                </div>
                <div className="pc-tooltip__badge">
                  {fmtPts(active.fx.sfa_pts)} pts
                </div>
                <div className="pc-tooltip__breakdown">
                  {breakdown.length > 0 ? breakdown.map(([action, item]) => (
                    <div className="pc-tooltip__row" key={action}>
                      <span>{formatAction(action, item.count)}</span>
                      <strong className={item.pts < 0 ? 'is-negative' : ''}>
                        {item.pts > 0 ? '+' : ''}{fmtPts(item.pts)}
                      </strong>
                    </div>
                  )) : (
                    <span className="pc-tooltip__empty">Sin acciones puntuables registradas</span>
                  )}
                  {technicalContext.length > 0 && (
                    <span className="pc-tooltip__context">
                      {technicalContext.join(' · ')}
                    </span>
                  )}
                </div>
                <span className="pc-tooltip__hint">
                  {selected ? 'Pulsa el punto para cerrar' : 'Pulsa para fijar el detalle'}
                </span>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}
