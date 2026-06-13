import { useMemo, useState, useEffect, useRef } from 'react'
import type { PlayerDetail, PlayerEvent, PlayerFixture, PlayerSeasonStats } from '../../types'

interface Props {
  player:      PlayerDetail
  events:      PlayerEvent[]
  fixtures:    PlayerFixture[]
  seasonStats?: PlayerSeasonStats | null
}

const MAX_FOR_KEY: Record<string, number> = {
  goal:           25,
  assist:         20,
  corner_assist:  35,
  xa_no_assist:   80,
  penalty_won:     8,
  dribbles_won:  220,
  fouls_drawn:   100,
  passes:       2000,
  duels_won:     350,
  tackles:       130,
  interceptions:  70,
  blocks:         45,
  foul_c:         70,
  yellow:         10,
  red:             3,
  drib_past:      50,
  shots_on:       60,
}

const BASE_PTS: Record<string, Record<string, number>> = {
  FW: { dribbles_won: 100, duels_won: 30,  tackles: 110, interceptions: 90,  blocks: 150, fouls_drawn: 50 },
  MF: { dribbles_won: 100, duels_won: 25,  tackles: 110, interceptions: 150, blocks: 100, fouls_drawn: 35 },
  DF: { dribbles_won: 130, duels_won: 25,  tackles: 150, interceptions: 200, blocks: 130, fouls_drawn: 20 },
  GK: { dribbles_won: 130, duels_won: 25,  tackles: 150, interceptions: 200, blocks: 130, fouls_drawn: 20 },
}

interface TileRow {
  key:          string
  label:        string
  displayValue: string
  pct:          number
  pts:          number
  isNeg?:       boolean
  isEst?:       boolean
  subText?:     string
}

interface Section {
  title: string
  tiles: TileRow[]
}

function fmt(n: number): string {
  const abs = Math.abs(Math.round(n))
  if (abs >= 10000) return `${Math.round(abs / 1000)}k`
  if (abs >= 1000)  return `${(abs / 1000).toFixed(1)}k`
  return abs.toLocaleString('es-ES')
}

function fmtCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function scoreTile(
  key: string,
  label: string,
  count: number,
  pts: number,
  opts?: { isNeg?: boolean; isEst?: boolean },
): TileRow {
  return {
    key,
    label,
    displayValue: fmtCount(count),
    pct: Math.min(1, count / (MAX_FOR_KEY[key] ?? 100)),
    pts,
    ...opts,
  }
}

function statTile(
  key: string,
  label: string,
  displayValue: string,
  pct: number,
  subText?: string,
): TileRow {
  return { key, label, displayValue, pct: Math.min(1, Math.max(0, pct)), pts: 0, subText }
}

interface TileProps {
  tile:    TileRow
  delay:   number
  visible: boolean
}

function useCountUp(target: number, visible: boolean, delay: number): number {
  const [count, setCount] = useState(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (!visible || target === 0) return
    const timer = setTimeout(() => {
      const duration = 750
      const startTime = performance.now()
      const step = (now: number) => {
        const progress = Math.min((now - startTime) / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        setCount(Math.round(target * eased))
        if (progress < 1) rafRef.current = requestAnimationFrame(step)
      }
      rafRef.current = requestAnimationFrame(step)
    }, delay)

    return () => {
      clearTimeout(timer)
      cancelAnimationFrame(rafRef.current)
    }
  }, [visible, target, delay])

  return count
}

function StatTile({ tile, delay, visible }: TileProps) {
  const isInt = /^\d+$/.test(tile.displayValue)
  const targetInt = isInt ? parseInt(tile.displayValue, 10) : 0
  const animatedInt = useCountUp(targetInt, visible && isInt, delay)
  const displayNum = visible && isInt ? String(animatedInt) : tile.displayValue

  return (
    <div
      className={`ptsbr__tile${tile.isNeg ? ' ptsbr__tile--neg' : ''}${visible ? ' ptsbr__tile--visible' : ''}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div className="ptsbr__tile-main">
        <span className="ptsbr__metric-value">{displayNum}</span>
        <div className="ptsbr__metric-copy">
          <span className="ptsbr__tile-label">{tile.label}</span>
          {tile.subText && (
            <span className="ptsbr__tile-sub">{tile.subText}</span>
          )}
        </div>
      </div>
      {tile.pts !== 0 && (
        <span className={`ptsbr__tile-pts${tile.isNeg ? ' ptsbr__tile-pts--neg' : tile.isEst ? ' ptsbr__tile-pts--est' : ''}`}>
          {tile.isNeg ? '−' : '+'}{fmt(Math.abs(tile.pts))}{tile.isEst ? ' ~' : ''}
        </span>
      )}
      <div className="ptsbr__meter" aria-hidden="true">
        <span
          className="ptsbr__meter-fill"
          style={{ width: visible ? `${Math.max(tile.pct * 100, 3)}%` : '0%' }}
        />
      </div>
    </div>
  )
}

export default function PointsBreakdown({ player, events, fixtures, seasonStats }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.05 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const sections = useMemo<Section[]>(() => {
    const bd   = player.breakdown ?? {}
    const pos  = player.position in BASE_PTS ? player.position : 'MF'
    const base = BASE_PTS[pos]

    const agg = fixtures.reduce(
      (acc, f) => ({
        dribbles_won:  acc.dribbles_won  + (f.dribbles_won  ?? 0),
        duels_won:     acc.duels_won     + (f.duels_won     ?? 0),
        tackles:       acc.tackles       + (f.tackles_won   ?? 0),
        interceptions: acc.interceptions + (f.interceptions ?? 0),
        blocks:        acc.blocks        + (f.blocks        ?? 0),
        fouls_drawn:   acc.fouls_drawn   + (f.fouls_drawn   ?? 0),
        shots_on:      acc.shots_on      + (f.shots_on      ?? 0),
      }),
      { dribbles_won: 0, duels_won: 0, tackles: 0, interceptions: 0, blocks: 0, fouls_drawn: 0, shots_on: 0 },
    )

    // Contar desde events (cubre TODAS las competiciones, no solo la primaria del breakdown)
    const regularGoals  = events.filter(e => e.event_type === 'goal').length
    const penaltyGoals  = events.filter(e => e.event_type === 'goal_penalty').length
    const shootoutGoals = events.filter(e => e.event_type === 'goal_shootout').length
    const totalGoals    = regularGoals + penaltyGoals + shootoutGoals
    const totalGoalPts  = events
      .filter(e => ['goal', 'goal_penalty', 'goal_shootout'].includes(e.event_type))
      .reduce((sum, e) => sum + e.pts, 0)

    const directAssists = events.filter(e => e.event_type === 'assist').length
    const cornerAssists = events.filter(e => e.event_type === 'corner_assist').length
    const totalAssistPts = events
      .filter(e => ['assist', 'corner_assist'].includes(e.event_type))
      .reduce((sum, e) => sum + e.pts, 0)

    // ── Sección 1: Creación y ataque (scoring tiles) ─────────────
    const ataque: TileRow[] = []

    if (regularGoals + shootoutGoals > 0) {
      const playGoals = regularGoals + shootoutGoals
      const playPts   = events
        .filter(e => e.event_type === 'goal' || e.event_type === 'goal_shootout')
        .reduce((sum, e) => sum + e.pts, 0)
      ataque.push({
        key:          'goal',
        label:        'Goles',
        displayValue: String(playGoals),
        pct:          Math.min(1, playGoals / 22),
        pts:          playPts,
      })
    }

    if (penaltyGoals > 0) {
      const penPts = events
        .filter(e => e.event_type === 'goal_penalty')
        .reduce((sum, e) => sum + e.pts, 0)
      ataque.push({
        key:          'goal_pen',
        label:        'Penales',
        displayValue: String(penaltyGoals),
        pct:          Math.min(1, penaltyGoals / 8),
        pts:          penPts,
      })
    }

    if (directAssists + cornerAssists > 0) {
      ataque.push({
        key:          'assist',
        label:        'Asistencias',
        displayValue: String(directAssists + cornerAssists),
        pct:          Math.min(1, (directAssists + cornerAssists) / 20),
        pts:          totalAssistPts,
        subText:      cornerAssists > 0 ? `${directAssists} dir. · ${cornerAssists} pre.` : undefined,
      })
    }

    if (bd['xa_no_assist']?.count)
      ataque.push(scoreTile('xa_no_assist', 'Pase clave', bd['xa_no_assist'].count, bd['xa_no_assist'].pts))

    if (bd['penalty_won']?.count)
      ataque.push(scoreTile('penalty_won', 'Penal gen.', bd['penalty_won'].count, bd['penalty_won'].pts))

    if (agg.dribbles_won > 0)
      ataque.push(scoreTile('dribbles_won', 'Regates', agg.dribbles_won, agg.dribbles_won * base.dribbles_won, { isEst: true }))

    if (agg.fouls_drawn > 0)
      ataque.push(scoreTile('fouls_drawn', 'Faltas rec.', agg.fouls_drawn, agg.fouls_drawn * base.fouls_drawn, { isEst: true }))

    if ((bd['passes_completed']?.pts ?? 0) > 0)
      ataque.push(scoreTile('passes', 'Pases comp.', bd['passes_completed']!.count, bd['passes_completed']!.pts))

    // ── Sección 2: Estadísticas de rendimiento ───────────────────
    const stats: TileRow[] = []

    if (agg.shots_on > 0)
      stats.push(statTile('shots_on', 'A puerta', String(agg.shots_on), agg.shots_on / 60))

    if (seasonStats) {
      // Normaliza valores que pueden llegar como decimal (0-1) o porcentaje (0-100)
      const toPct = (v: number | null): number | null => {
        if (!v || v <= 0) return null
        return v < 2 ? v * 100 : v   // 0.54 → 54, 54 → 54
      }

      const passAcc = toPct(seasonStats.passes_accuracy_avg)
      if (passAcc && passAcc > 5)
        stats.push(statTile(
          'pass_acc', 'Precisión',
          `${Math.round(passAcc)}%`,
          passAcc / 100,
          seasonStats.passes_total > 0 ? `${fmtCount(seasonStats.passes_total)} pases` : undefined,
        ))

      const drRate = toPct(seasonStats.dribble_success_rate)
      if (drRate && drRate > 5)
        stats.push(statTile(
          'dribble_rate', 'Regates %',
          `${Math.round(drRate)}%`,
          drRate / 100,
          seasonStats.dribbles_won > 0 ? `${seasonStats.dribbles_won} éxit.` : undefined,
        ))

      const duelRate = toPct(seasonStats.duel_win_rate)
      if (duelRate && duelRate > 5)
        stats.push(statTile(
          'duel_rate', 'Duelos %',
          `${Math.round(duelRate)}%`,
          duelRate / 100,
          seasonStats.duels_won > 0 ? `${seasonStats.duels_won} gan.` : undefined,
        ))

      if (seasonStats.passes_key > 0)
        stats.push(statTile(
          'passes_key', 'Pases clave',
          String(seasonStats.passes_key),
          Math.min(1, seasonStats.passes_key / 80),
        ))
    }

    // ── Sección 3: Duelos y defensa (scoring tiles) ──────────────
    const defensa: TileRow[] = []

    if (agg.duels_won > 0)
      defensa.push(scoreTile('duels_won', 'Duelos', agg.duels_won, agg.duels_won * base.duels_won, { isEst: true }))
    if (agg.tackles > 0)
      defensa.push(scoreTile('tackles', 'Tackles', agg.tackles, agg.tackles * base.tackles, { isEst: true }))
    if (agg.interceptions > 0)
      defensa.push(scoreTile('interceptions', 'Interc.', agg.interceptions, agg.interceptions * base.interceptions, { isEst: true }))
    if (agg.blocks > 0)
      defensa.push(scoreTile('blocks', 'Bloqueos', agg.blocks, agg.blocks * base.blocks, { isEst: true }))

    // ── Sección 4: Disciplina negativa ────────────────────────────
    const disciplina: TileRow[] = []

    if (bd['fouls_committed']?.count)
      disciplina.push(scoreTile('foul_c', 'Faltas com.', bd['fouls_committed'].count, bd['fouls_committed'].pts, { isNeg: true }))
    if (bd['yellow_card']?.count)
      disciplina.push(scoreTile('yellow', 'Amarillas', bd['yellow_card'].count, bd['yellow_card'].pts, { isNeg: true }))
    if (bd['red_card']?.count)
      disciplina.push(scoreTile('red', 'Rojas', bd['red_card'].count, bd['red_card'].pts, { isNeg: true }))
    if ((bd['dribbles_past']?.pts ?? 0) < 0)
      disciplina.push(scoreTile('drib_past', 'Reg. sufridos', bd['dribbles_past']!.count, bd['dribbles_past']!.pts, { isNeg: true }))

    return [
      ...(ataque.length     ? [{ title: 'Creación y ataque',         tiles: ataque }]     : []),
      ...(stats.length      ? [{ title: 'Rendimiento',               tiles: stats }]       : []),
      ...(defensa.length    ? [{ title: 'Duelos y defensa',          tiles: defensa }]     : []),
      ...(disciplina.length ? [{ title: 'Disciplina',                tiles: disciplina }]  : []),
    ]
  }, [player.breakdown, player.position, events, fixtures, seasonStats])

  if (sections.length === 0) return null

  let globalIdx = 0

  return (
    <div className="ptsbr card mt-32" ref={containerRef}>
      <p className="section-title">Desglose de puntos</p>

      {sections.map((section) => {
        const sectionPts = section.tiles.reduce((sum, tile) => sum + tile.pts, 0)
        return (
          <div key={section.title} className="ptsbr__section">
            <div className="ptsbr__section-header">
              <div>
                <span className="ptsbr__section-title">{section.title}</span>
                <span className="ptsbr__section-count">{section.tiles.length} métricas</span>
              </div>
              {sectionPts !== 0 && (
                <span className={`ptsbr__section-pts${sectionPts < 0 ? ' ptsbr__section-pts--neg' : ''}`}>
                  {sectionPts > 0 ? '+' : '−'}{fmt(Math.abs(sectionPts))}
                </span>
              )}
            </div>
            <div className="ptsbr__grid">
              {section.tiles.map((tile) => {
                const idx = globalIdx++
                return (
                  <StatTile key={tile.key} tile={tile} delay={idx * 50} visible={visible} />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
