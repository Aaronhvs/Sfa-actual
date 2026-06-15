import { useEffect, useMemo, useRef, useState } from 'react'
import type { PlayerDetail, PlayerEvent, PlayerFixture, RankedPlayer } from '../types'
import { fetchPlayer, fetchPlayerEvents, fetchPlayerFixtures, fetchRanking } from '../api/client'

const SEASON = '2024'
const SEARCH_DEBOUNCE_MS = 300
const COMPARE_ENABLED = false

/* ── Formatters ─────────────────────────────────────────────────────── */
function fmt(n: number) { return Math.round(n).toLocaleString('es-ES') }
function fmtDec(n: number, d = 1) {
  return n.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: d })
}
function initials(name: string) {
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
}
function posGroup(pos: string): 'FW' | 'MF' | 'DF' | null {
  const p = pos.toUpperCase()
  if (['DEL', 'EXT'].some(x => p.includes(x))) return 'FW'
  if (['MC', 'MED', 'CENT'].some(x => p.includes(x))) return 'MF'
  if (['DC', 'LAT', 'DEF'].some(x => p.includes(x))) return 'DF'
  return null
}

/* ── Derived stats ──────────────────────────────────────────────────── */
interface CmpDerived {
  totalMinutes: number
  goalsJugada: number
  goalsPenalti: number
  goalsTanda: number
  totalGoals: number
  goalsPenaltiPct: number
  goalsJugadaPer90: number | null
  minutesPerGoal: number | null
  cornerAssists: number
  totalAssists: number
  minutesPerAssist: number | null
  minutesPerContribution: number | null
  criticalGoals: number
  goalEventsCount: number
  criticalGoalPct: number
  avgM3Goals: number | null
  avgM1Goals: number | null
  eliteFixtures: number
  decisiveGoals: number
  ptsPerMatch: number
  homePts: number | null
  awayPts: number | null
  maxStreak: number
  shotsPer90: number | null
  dribblesPer90: number | null
  duelsPer90: number | null
  tacklesPlusInterceptionsPer90: number | null
  yellowCards: number
  redCards: number
  foulsPerMatch: number | null
  ptsLostDiscipline: number
}

function deriveCmpStats(
  detail: PlayerDetail,
  events: PlayerEvent[],
  fixtures: PlayerFixture[],
): CmpDerived {
  const sf = [...fixtures].sort(
    (a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime(),
  )
  const bd = detail.breakdown ?? {}

  const goalsJugada = bd.goal?.count ?? 0
  const goalsPenalti = bd.goal_penalty?.count ?? 0
  const goalsTanda = bd.goal_shootout?.count ?? 0
  const totalGoals = goalsJugada + goalsPenalti + goalsTanda
  const goalsPenaltiPct = totalGoals > 0 ? (goalsPenalti + goalsTanda) / totalGoals * 100 : 0
  const totalMinutes = fixtures.reduce((s, f) => s + (f.minutes ?? 0), 0)
  const goalsJugadaPer90 = totalMinutes >= 90 ? goalsJugada / totalMinutes * 90 : null
  const minutesPerGoal = totalGoals > 0 && totalMinutes > 0 ? totalMinutes / totalGoals : null

  const cornerAssists = bd.corner_assist?.count ?? 0
  const totalAssists = detail.total_assists
  const minutesPerAssist = totalAssists > 0 && totalMinutes > 0 ? totalMinutes / totalAssists : null
  const minutesPerContribution =
    (totalGoals + totalAssists) > 0 && totalMinutes > 0
      ? totalMinutes / (totalGoals + totalAssists)
      : null

  const goalEvents = events.filter(
    e => e.event_type === 'goal' || e.event_type === 'goal_penalty',
  )
  const criticalGoals = goalEvents.filter(e => e.m3 >= 1.6).length
  const goalEventsCount = goalEvents.length
  const criticalGoalPct = goalEventsCount > 0 ? criticalGoals / goalEventsCount * 100 : 0
  const avgM3Goals =
    goalEventsCount > 0 ? goalEvents.reduce((s, e) => s + e.m3, 0) / goalEventsCount : null
  const avgM1Goals =
    goalEventsCount > 0 ? goalEvents.reduce((s, e) => s + e.m1, 0) / goalEventsCount : null

  const eliteFixtures = fixtures.filter(f => f.sfa_pts >= 2500).length
  const decisiveGoals = goalEvents.filter(
    e => e.score_diff !== null && e.score_diff >= -1 && e.score_diff <= 0,
  ).length

  const ptsPerMatch = detail.matches > 0 ? detail.sfa_pts / detail.matches : 0
  const team = detail.team
  const hf = fixtures.filter(f => f.home_team === team)
  const af = fixtures.filter(f => f.away_team === team)
  const homePts = hf.length > 0 ? hf.reduce((s, f) => s + f.sfa_pts, 0) / hf.length : null
  const awayPts = af.length > 0 ? af.reduce((s, f) => s + f.sfa_pts, 0) / af.length : null

  const scoringFids = new Set(
    events
      .filter(e =>
        ['goal', 'goal_penalty', 'goal_shootout', 'assist', 'corner_assist'].includes(
          e.event_type,
        ),
      )
      .map(e => e.fixture_id),
  )
  let maxStreak = 0
  let curStreak = 0
  for (const f of sf) {
    if (scoringFids.has(f.fixture_id)) {
      curStreak++
      maxStreak = Math.max(maxStreak, curStreak)
    } else {
      curStreak = 0
    }
  }

  const totalShots = fixtures.reduce((s, f) => s + (f.shots_on ?? 0), 0)
  const totalDrib = fixtures.reduce((s, f) => s + (f.dribbles_won ?? 0), 0)
  const totalDuels = fixtures.reduce((s, f) => s + (f.duels_won ?? 0), 0)
  const totalTI = fixtures.reduce(
    (s, f) => s + (f.tackles_won ?? 0) + (f.interceptions ?? 0),
    0,
  )
  const shotsPer90 = totalMinutes > 0 ? totalShots / totalMinutes * 90 : null
  const dribblesPer90 = totalMinutes > 0 ? totalDrib / totalMinutes * 90 : null
  const duelsPer90 = totalMinutes > 0 ? totalDuels / totalMinutes * 90 : null
  const tacklesPlusInterceptionsPer90 = totalMinutes > 0 ? totalTI / totalMinutes * 90 : null

  const yellowCards = bd.yellow_card?.count ?? 0
  const redCards = bd.red_card?.count ?? 0
  const foulsCommitted = bd.fouls_committed?.count ?? 0
  const gamesPlayed = fixtures.filter(f => (f.minutes ?? 0) > 0).length
  const foulsPerMatch = gamesPlayed > 0 ? foulsCommitted / gamesPlayed : null
  const ptsLostDiscipline = Math.abs(
    (bd.yellow_card?.pts ?? 0) + (bd.red_card?.pts ?? 0) + (bd.fouls_committed?.pts ?? 0),
  )

  return {
    totalMinutes, goalsJugada, goalsPenalti, goalsTanda, totalGoals,
    goalsPenaltiPct, goalsJugadaPer90, minutesPerGoal,
    cornerAssists, totalAssists, minutesPerAssist, minutesPerContribution,
    criticalGoals, goalEventsCount, criticalGoalPct, avgM3Goals, avgM1Goals,
    eliteFixtures, decisiveGoals, ptsPerMatch, homePts, awayPts, maxStreak,
    shotsPer90, dribblesPer90, duelsPer90, tacklesPlusInterceptionsPer90,
    yellowCards, redCards, foulsPerMatch, ptsLostDiscipline,
  }
}

/* ── PlayerPicker ───────────────────────────────────────────────────── */
interface PickerProps {
  label: string
  selected: RankedPlayer | null
  onSelect: (p: RankedPlayer) => void
  onClear: () => void
  excludeId?: number
}

function PlayerPicker({ label, selected, onSelect, onClear, excludeId }: PickerProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RankedPlayer[]>([])
  const [searching, setSearching] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    if (!query || query.length < 2) { setResults([]); return }
    setSearching(true)
    timerRef.current = setTimeout(() => {
      fetchRanking({ season: SEASON, name: query, limit: 8 })
        .then(d => setResults(d.ranking.filter(p => p.id !== excludeId)))
        .catch(() => setResults([]))
        .finally(() => setSearching(false))
    }, SEARCH_DEBOUNCE_MS)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [query, excludeId])

  if (selected) {
    return (
      <div className="cmp-chip">
        {selected.photo_url
          ? <img src={selected.photo_url} alt={selected.name} className="cmp-chip__photo" />
          : <div className="cmp-chip__avatar">{initials(selected.name)}</div>
        }
        <div className="cmp-chip__info">
          <span className="cmp-chip__name">{selected.name}</span>
          <span className="cmp-chip__sub">
            <span className="pos-badge">{selected.position}</span>
            <span className="cmp-chip__team">{selected.team}</span>
          </span>
        </div>
        <span className="cmp-chip__pts">
          {fmt(selected.sfa_pts)}<span className="cmp-chip__pts-lbl"> pts</span>
        </span>
        <button className="cmp-chip__clear" onClick={onClear} aria-label="Cambiar jugador">×</button>
      </div>
    )
  }

  return (
    <div className="cmp-picker">
      <div className="cmp-picker__label">{label}</div>
      <div className="cmp-picker__search-row">
        <svg className="cmp-picker__icon" viewBox="0 0 20 20" fill="none">
          <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M14 14l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          className="cmp-picker__input"
          type="text"
          placeholder="Buscar jugador..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
        {searching && <span className="cmp-picker__spinner" />}
      </div>
      {query.length >= 2 && !searching && results.length === 0 && (
        <div className="cmp-picker__empty">Sin resultados para "{query}"</div>
      )}
      {results.length > 0 && (
        <div className="cmp-picker__dropdown">
          {results.map(p => (
            <button
              key={p.id}
              className="cmp-picker__result"
              onClick={() => { onSelect(p); setQuery(''); setResults([]) }}
            >
              {p.photo_url
                ? <img src={p.photo_url} alt={p.name} className="cmp-picker__result-photo" />
                : <div className="cmp-picker__result-avatar">{initials(p.name)}</div>
              }
              <div className="cmp-picker__result-info">
                <span className="cmp-picker__result-name">{p.name}</span>
                <span className="cmp-picker__result-meta">{p.team} · #{p.rank}</span>
              </div>
              <span className="cmp-picker__result-pts">{fmt(p.sfa_pts)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── UI Building blocks ─────────────────────────────────────────────── */

function PlayerCard({ player, side }: { player: PlayerDetail; side: 'a' | 'b' }) {
  return (
    <div className={`cmp-card cmp-card--${side}`}>
      <span className="cmp-card__rank">#{player.global_rank}</span>
      {player.photo_url
        ? <img src={player.photo_url} alt={player.name} className="cmp-card__photo" />
        : <div className="cmp-card__photo-ph">{initials(player.name)}</div>
      }
      <span className="cmp-card__name">{player.name}</span>
      <div className="cmp-card__meta">
        <span className="pos-badge">{player.position}</span>
        <span className="cmp-card__team">{player.team}</span>
      </div>
      <div className="cmp-card__pts">
        {fmt(player.sfa_pts)}<span className="cmp-card__pts-lbl"> pts</span>
      </div>
    </div>
  )
}

interface DualRowProps {
  label: string
  aVal: number | null
  bVal: number | null
  format?: (n: number) => string
  lowerIsBetter?: boolean
}

function DualRow({ label, aVal, bVal, format = fmtDec, lowerIsBetter = false }: DualRowProps) {
  const aNum = aVal ?? 0
  const bNum = bVal ?? 0
  const total = aNum + bNum
  const aWidth = total === 0 ? 50 : Math.round((aNum / total) * 100)

  let aWins = false
  let bWins = false
  if (aVal !== null && bVal !== null) {
    aWins = lowerIsBetter ? aNum < bNum : aNum > bNum
    bWins = lowerIsBetter ? bNum < aNum : bNum > aNum
  } else if (aVal !== null) {
    aWins = true
  } else if (bVal !== null) {
    bWins = true
  }

  return (
    <div className="dual-row">
      <span className={`dual-row__val dual-row__val--a${aWins ? ' dual-row__val--win' : ''}`}>
        {aVal === null ? '—' : format(aVal)}
      </span>
      <div className="dual-row__center">
        <span className="dual-row__label">{label}</span>
        <div className="dual-row__bar">
          <div className="dual-row__bar-a" style={{ width: `${aWidth}%` }} />
          <div className="dual-row__bar-b" />
        </div>
      </div>
      <span className={`dual-row__val dual-row__val--b${bWins ? ' dual-row__val--win' : ''}`}>
        {bVal === null ? '—' : format(bVal)}
      </span>
    </div>
  )
}

function BlockSection({
  title,
  eyebrow,
  children,
  className = '',
}: {
  title: string
  eyebrow?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={`cmp-block ${className}`}>
      <div className="cmp-block__header">
        {eyebrow && <span className="cmp-block__eyebrow">{eyebrow}</span>}
        <span className="cmp-block__title">{title}</span>
      </div>
      <div className="cmp-block__rows">{children}</div>
    </section>
  )
}

function GolBar({
  jugada,
  penalti,
  tanda,
  total,
}: {
  jugada: number
  penalti: number
  tanda: number
  total: number
}) {
  if (total === 0) {
    return (
      <div className="gol-bar gol-bar--empty">
        <span className="gol-bar__none">sin goles</span>
      </div>
    )
  }
  const jp = (jugada / total) * 100
  const pp = (penalti / total) * 100
  const tp = (tanda / total) * 100
  return (
    <div className="gol-bar">
      {jugada > 0 && (
        <div className="gol-bar__seg gol-bar__seg--j" style={{ width: `${jp}%` }}>
          <span className="gol-bar__num">{jugada}</span>
        </div>
      )}
      {penalti > 0 && (
        <div className="gol-bar__seg gol-bar__seg--p" style={{ width: `${pp}%` }}>
          <span className="gol-bar__num">{penalti}</span>
        </div>
      )}
      {tanda > 0 && (
        <div className="gol-bar__seg gol-bar__seg--t" style={{ width: `${tp}%` }}>
          <span className="gol-bar__num">{tanda}</span>
        </div>
      )}
    </div>
  )
}

/* ── Blocks ─────────────────────────────────────────────────────────── */

function SummaryBlock({ detailA, detailB }: { detailA: PlayerDetail; detailB: PlayerDetail }) {
  const total = detailA.sfa_pts + detailB.sfa_pts
  const aWidth = total === 0 ? 50 : Math.round((detailA.sfa_pts / total) * 100)
  const aWins = detailA.sfa_pts > detailB.sfa_pts
  const bWins = detailB.sfa_pts > detailA.sfa_pts

  return (
    <div className="cmp-summary">
      <PlayerCard player={detailA} side="a" />
      <div className="cmp-summary__center">
        <div className="cmp-summary__vs">VS</div>
        <div className="cmp-summary__pts-bar">
          <div
            className={`cmp-summary__pts-fill cmp-summary__pts-fill--a${aWins ? ' cmp-summary__pts-fill--win' : ''}`}
            style={{ width: `${aWidth}%` }}
          />
          <div
            className={`cmp-summary__pts-fill cmp-summary__pts-fill--b${bWins ? ' cmp-summary__pts-fill--win' : ''}`}
            style={{ width: `${100 - aWidth}%` }}
          />
        </div>
        <div className="cmp-summary__bar-labels">
          <span>{Math.round(aWidth)}%</span>
          <span>{Math.round(100 - aWidth)}%</span>
        </div>
      </div>
      <PlayerCard player={detailB} side="b" />
    </div>
  )
}

function GolesBlock({ dA, dB }: { dA: CmpDerived; dB: CmpDerived }) {
  const hasTanda = dA.goalsTanda > 0 || dB.goalsTanda > 0

  return (
    <BlockSection title="Goles">
      <div className="cmp-goal-section">
        <GolBar
          jugada={dA.goalsJugada}
          penalti={dA.goalsPenalti}
          tanda={dA.goalsTanda}
          total={dA.totalGoals}
        />
        <div className="cmp-goal-legend">
          <span><span className="cmp-goal-dot cmp-goal-dot--j" />Jugada</span>
          <span><span className="cmp-goal-dot cmp-goal-dot--p" />Penalti</span>
          {hasTanda && <span><span className="cmp-goal-dot cmp-goal-dot--t" />Tanda</span>}
        </div>
        <GolBar
          jugada={dB.goalsJugada}
          penalti={dB.goalsPenalti}
          tanda={dB.goalsTanda}
          total={dB.totalGoals}
        />
      </div>
      <DualRow
        label="Total goles"
        aVal={dA.totalGoals}
        bVal={dB.totalGoals}
        format={n => String(Math.round(n))}
      />
      <DualRow
        label="Goles de jugada"
        aVal={dA.goalsJugada}
        bVal={dB.goalsJugada}
        format={n => String(Math.round(n))}
      />
      {(dA.goalsPenalti > 0 || dB.goalsPenalti > 0) && (
        <DualRow
          label="Goles de penalti"
          aVal={dA.goalsPenalti}
          bVal={dB.goalsPenalti}
          format={n => String(Math.round(n))}
          lowerIsBetter
        />
      )}
      {(dA.goalsPenaltiPct > 0 || dB.goalsPenaltiPct > 0) && (
        <DualRow
          label="% goles penalti"
          aVal={dA.goalsPenaltiPct > 0 ? dA.goalsPenaltiPct : null}
          bVal={dB.goalsPenaltiPct > 0 ? dB.goalsPenaltiPct : null}
          format={n => `${Math.round(n)}%`}
          lowerIsBetter
        />
      )}
      {(dA.goalsJugadaPer90 !== null || dB.goalsJugadaPer90 !== null) && (
        <DualRow
          label="Goles jugada / 90'"
          aVal={dA.goalsJugadaPer90}
          bVal={dB.goalsJugadaPer90}
          format={n => fmtDec(n, 2)}
        />
      )}
      {(dA.minutesPerGoal !== null || dB.minutesPerGoal !== null) && (
        <DualRow
          label="Min. por gol"
          aVal={dA.minutesPerGoal}
          bVal={dB.minutesPerGoal}
          format={n => `${Math.round(n)}'`}
          lowerIsBetter
        />
      )}
    </BlockSection>
  )
}

function AsistenciasBlock({ dA, dB }: { dA: CmpDerived; dB: CmpDerived }) {
  return (
    <BlockSection title="Asistencias">
      <DualRow
        label="Total asistencias"
        aVal={dA.totalAssists}
        bVal={dB.totalAssists}
        format={n => String(Math.round(n))}
      />
      {(dA.cornerAssists > 0 || dB.cornerAssists > 0) && (
        <DualRow
          label="Corner assists"
          aVal={dA.cornerAssists > 0 ? dA.cornerAssists : null}
          bVal={dB.cornerAssists > 0 ? dB.cornerAssists : null}
          format={n => String(Math.round(n))}
        />
      )}
      {(dA.minutesPerAssist !== null || dB.minutesPerAssist !== null) && (
        <DualRow
          label="Min. por asistencia"
          aVal={dA.minutesPerAssist}
          bVal={dB.minutesPerAssist}
          format={n => `${Math.round(n)}'`}
          lowerIsBetter
        />
      )}
      {(dA.minutesPerContribution !== null || dB.minutesPerContribution !== null) && (
        <DualRow
          label="Min. por G+A"
          aVal={dA.minutesPerContribution}
          bVal={dB.minutesPerContribution}
          format={n => `${Math.round(n)}'`}
          lowerIsBetter
        />
      )}
    </BlockSection>
  )
}

function CriticosBlock({
  dA,
  dB,
}: {
  dA: CmpDerived
  dB: CmpDerived
}) {
  return (
    <BlockSection title="Impacto crítico" eyebrow="Exclusivo SFA" className="cmp-block--critical">
      <div className="cmp-critical">
        <div className="cmp-critical__item cmp-critical__item--a">
          <span className="cmp-critical__num">{dA.criticalGoals}</span>
          <span className="cmp-critical__of">de {dA.goalEventsCount}</span>
          <span className="cmp-critical__desc">goles en momentos críticos</span>
          {dA.goalEventsCount > 0 && (
            <span className="cmp-critical__pct">{Math.round(dA.criticalGoalPct)}%</span>
          )}
        </div>
        <div className="cmp-critical__divider" />
        <div className="cmp-critical__item cmp-critical__item--b">
          <span className="cmp-critical__num">{dB.criticalGoals}</span>
          <span className="cmp-critical__of">de {dB.goalEventsCount}</span>
          <span className="cmp-critical__desc">goles en momentos críticos</span>
          {dB.goalEventsCount > 0 && (
            <span className="cmp-critical__pct">{Math.round(dB.criticalGoalPct)}%</span>
          )}
        </div>
      </div>
      {(dA.avgM3Goals !== null || dB.avgM3Goals !== null) && (
        <DualRow
          label="M3 promedio en goles"
          aVal={dA.avgM3Goals}
          bVal={dB.avgM3Goals}
          format={n => fmtDec(n, 2)}
        />
      )}
      {(dA.avgM1Goals !== null || dB.avgM1Goals !== null) && (
        <DualRow
          label="M1 promedio en goles"
          aVal={dA.avgM1Goals}
          bVal={dB.avgM1Goals}
          format={n => fmtDec(n, 2)}
        />
      )}
      <DualRow
        label="Actuaciones élite (≥2500 pts)"
        aVal={dA.eliteFixtures}
        bVal={dB.eliteFixtures}
        format={n => String(Math.round(n))}
      />
      <DualRow
        label="Goles decisivos"
        aVal={dA.decisiveGoals}
        bVal={dB.decisiveGoals}
        format={n => String(Math.round(n))}
      />
    </BlockSection>
  )
}

function EficienciaBlock({ dA, dB }: { dA: CmpDerived; dB: CmpDerived }) {
  return (
    <BlockSection title="Eficiencia">
      <DualRow label="Pts por partido" aVal={dA.ptsPerMatch} bVal={dB.ptsPerMatch} format={fmt} />
      {(dA.homePts !== null || dB.homePts !== null) && (
        <DualRow
          label="Pts como local"
          aVal={dA.homePts}
          bVal={dB.homePts}
          format={fmt}
        />
      )}
      {(dA.awayPts !== null || dB.awayPts !== null) && (
        <DualRow
          label="Pts como visitante"
          aVal={dA.awayPts}
          bVal={dB.awayPts}
          format={fmt}
        />
      )}
      <DualRow
        label="Racha anotadora"
        aVal={dA.maxStreak}
        bVal={dB.maxStreak}
        format={n => `${Math.round(n)} PJ`}
      />
    </BlockSection>
  )
}

function PosicionBlock({
  dA,
  dB,
  posA,
  posB,
}: {
  dA: CmpDerived
  dB: CmpDerived
  posA: string
  posB: string
}) {
  const pgA = posGroup(posA)
  const pgB = posGroup(posB)

  const isFwA = pgA === 'FW'
  const isMfA = pgA === 'MF'
  const isDfA = pgA === 'DF'
  const isFwB = pgB === 'FW'
  const isMfB = pgB === 'MF'
  const isDfB = pgB === 'DF'

  const rows: Array<{
    label: string
    aVal: number | null
    bVal: number | null
    fmt?: (n: number) => string
  }> = []

  if (isFwA || isFwB) {
    rows.push({
      label: 'Disparos a puerta / 90\'',
      aVal: isFwA ? dA.shotsPer90 : null,
      bVal: isFwB ? dB.shotsPer90 : null,
      fmt: n => fmtDec(n, 1),
    })
  }
  if (isFwA || isMfA || isFwB || isMfB) {
    rows.push({
      label: 'Regates ganados / 90\'',
      aVal: (isFwA || isMfA) ? dA.dribblesPer90 : null,
      bVal: (isFwB || isMfB) ? dB.dribblesPer90 : null,
      fmt: n => fmtDec(n, 1),
    })
  }
  if (isMfA || isDfA || isMfB || isDfB) {
    rows.push({
      label: 'Duelos ganados / 90\'',
      aVal: (isMfA || isDfA) ? dA.duelsPer90 : null,
      bVal: (isMfB || isDfB) ? dB.duelsPer90 : null,
      fmt: n => fmtDec(n, 1),
    })
    rows.push({
      label: 'Tackles + intercep. / 90\'',
      aVal: (isMfA || isDfA) ? dA.tacklesPlusInterceptionsPer90 : null,
      bVal: (isMfB || isDfB) ? dB.tacklesPlusInterceptionsPer90 : null,
      fmt: n => fmtDec(n, 1),
    })
  }

  const visible = rows.filter(r => r.aVal !== null || r.bVal !== null)
  if (visible.length === 0) return null

  return (
    <BlockSection title="Métricas por posición">
      {visible.map((r, i) => (
        <DualRow
          key={i}
          label={r.label}
          aVal={r.aVal}
          bVal={r.bVal}
          format={r.fmt ?? fmtDec}
        />
      ))}
    </BlockSection>
  )
}

function DisciplinaBlock({ dA, dB }: { dA: CmpDerived; dB: CmpDerived }) {
  return (
    <BlockSection title="Disciplina">
      <DualRow
        label="Tarjetas amarillas"
        aVal={dA.yellowCards}
        bVal={dB.yellowCards}
        format={n => String(Math.round(n))}
        lowerIsBetter
      />
      <DualRow
        label="Tarjetas rojas"
        aVal={dA.redCards}
        bVal={dB.redCards}
        format={n => String(Math.round(n))}
        lowerIsBetter
      />
      {(dA.foulsPerMatch !== null || dB.foulsPerMatch !== null) && (
        <DualRow
          label="Faltas por partido"
          aVal={dA.foulsPerMatch}
          bVal={dB.foulsPerMatch}
          format={n => fmtDec(n, 1)}
          lowerIsBetter
        />
      )}
      {(dA.ptsLostDiscipline > 0 || dB.ptsLostDiscipline > 0) && (
        <DualRow
          label="Pts perdidos (disciplina)"
          aVal={dA.ptsLostDiscipline > 0 ? dA.ptsLostDiscipline : null}
          bVal={dB.ptsLostDiscipline > 0 ? dB.ptsLostDiscipline : null}
          format={fmt}
          lowerIsBetter
        />
      )}
    </BlockSection>
  )
}

/* ── Compare body ───────────────────────────────────────────────────── */
function CompareBody({
  detailA,
  detailB,
  derivedA,
  derivedB,
}: {
  detailA: PlayerDetail
  detailB: PlayerDetail
  derivedA: CmpDerived
  derivedB: CmpDerived
}) {
  return (
    <div className="cmp-body">
      <SummaryBlock detailA={detailA} detailB={detailB} />
      <GolesBlock dA={derivedA} dB={derivedB} />
      <AsistenciasBlock dA={derivedA} dB={derivedB} />
      <CriticosBlock dA={derivedA} dB={derivedB} />
      <EficienciaBlock dA={derivedA} dB={derivedB} />
      <PosicionBlock
        dA={derivedA}
        dB={derivedB}
        posA={detailA.position}
        posB={detailB.position}
      />
      <DisciplinaBlock dA={derivedA} dB={derivedB} />
    </div>
  )
}

/* ── Page ───────────────────────────────────────────────────────────── */
interface PlayerData {
  detail: PlayerDetail
  events: PlayerEvent[]
  fixtures: PlayerFixture[]
}

export default function ComparePage() {
  const [selectedA, setSelectedA] = useState<RankedPlayer | null>(null)
  const [selectedB, setSelectedB] = useState<RankedPlayer | null>(null)
  const [dataA, setDataA] = useState<PlayerData | null>(null)
  const [dataB, setDataB] = useState<PlayerData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedA || !selectedB) {
      setDataA(null)
      setDataB(null)
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      fetchPlayer(selectedA.id, SEASON),
      fetchPlayer(selectedB.id, SEASON),
      fetchPlayerEvents(selectedA.id, SEASON),
      fetchPlayerEvents(selectedB.id, SEASON),
      fetchPlayerFixtures(selectedA.id, SEASON),
      fetchPlayerFixtures(selectedB.id, SEASON),
    ])
      .then(([dA, dB, evA, evB, fxA, fxB]) => {
        setDataA({ detail: dA, events: evA, fixtures: fxA })
        setDataB({ detail: dB, events: evB, fixtures: fxB })
      })
      .catch((e: Error) => setError(e.message ?? 'Error al cargar los datos'))
      .finally(() => setLoading(false))
  }, [selectedA, selectedB])

  const derivedA = useMemo(
    () => (dataA ? deriveCmpStats(dataA.detail, dataA.events, dataA.fixtures) : null),
    [dataA],
  )
  const derivedB = useMemo(
    () => (dataB ? deriveCmpStats(dataB.detail, dataB.events, dataB.fixtures) : null),
    [dataB],
  )

  if (!COMPARE_ENABLED) {
    return (
      <div className="page-container">
        <div className="coming-soon coming-soon--compare">
          <span className="coming-soon__eyebrow">Stats Football Award</span>
          <h1 className="coming-soon__title">Comparar jugadores</h1>
          <p className="coming-soon__sub">En construcción</p>
          <span className="coming-soon__note">
            Estamos preparando una comparación SFA más clara y completa.
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="compare-page">
      <div className="cmp-header">
        <span className="rp-header__eyebrow">Temporada {SEASON}</span>
        <h1 className="rp-header__title">Comparar<br />Jugadores</h1>
        <p className="rp-header__sub">
          Head-to-head con métricas contextuales SFA
        </p>
      </div>

      <div className="cmp-pickers">
        <PlayerPicker
          label="Jugador A"
          selected={selectedA}
          onSelect={p => { setSelectedA(p); setDataA(null) }}
          onClear={() => { setSelectedA(null); setDataA(null) }}
          excludeId={selectedB?.id}
        />
        <div className="cmp-pickers__vs">VS</div>
        <PlayerPicker
          label="Jugador B"
          selected={selectedB}
          onSelect={p => { setSelectedB(p); setDataB(null) }}
          onClear={() => { setSelectedB(null); setDataB(null) }}
          excludeId={selectedA?.id}
        />
      </div>

      {loading && (
        <div className="cmp-loading">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="skeleton"
              style={{ height: i === 0 ? 160 : 48, borderRadius: 4 }}
            />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">{error}</div>
      )}

      {!loading && !error && dataA && dataB && derivedA && derivedB && (
        <CompareBody
          detailA={dataA.detail}
          detailB={dataB.detail}
          derivedA={derivedA}
          derivedB={derivedB}
        />
      )}

      {!selectedA && !selectedB && (
        <div className="cmp-placeholder">
          <div className="cmp-placeholder__slots">
            <div className="cmp-placeholder__slot">
              <div className="cmp-placeholder__silhouette" />
              <span className="cmp-placeholder__hint">Busca un jugador</span>
            </div>
            <span className="cmp-placeholder__vs">VS</span>
            <div className="cmp-placeholder__slot">
              <div className="cmp-placeholder__silhouette" />
              <span className="cmp-placeholder__hint">Busca un jugador</span>
            </div>
          </div>
          <p className="cmp-placeholder__text">
            Selecciona dos jugadores para ver su comparativa detallada
          </p>
        </div>
      )}
    </div>
  )
}
