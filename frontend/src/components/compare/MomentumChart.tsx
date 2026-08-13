import { useMemo, useState } from 'react'
import type { PlayerFixture } from '../../types'

const WIDTH = 1000
const HEIGHT = 250
const BASELINE = HEIGHT / 2
const AMPLITUDE = 94

interface MonthStats {
  key: string
  shortLabel: string
  fullLabel: string
  a: number
  b: number
  matchesA: number
  matchesB: number
  goalsA: number
  goalsB: number
  assistsA: number
  assistsB: number
}

interface FixtureMonthStats {
  points: number
  matches: number
  goals: number
  assists: number
}

function monthKey(date: Date) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
}

function dateFromMonthKey(key: string) {
  const [year, month] = key.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, 1))
}

function fixtureDate(fixture: PlayerFixture) {
  const date = new Date(fixture.played_at)
  return Number.isNaN(date.getTime()) ? null : date
}

function aggregateFixtures(fixtures: PlayerFixture[]) {
  const months = new Map<string, FixtureMonthStats>()
  for (const fixture of fixtures) {
    const date = fixtureDate(fixture)
    if (!date) continue
    const key = monthKey(date)
    const current = months.get(key) ?? { points: 0, matches: 0, goals: 0, assists: 0 }
    current.points += fixture.sfa_pts
    current.matches += 1
    current.goals += (fixture.breakdown?.goal?.count ?? 0) + (fixture.breakdown?.goal_penalty?.count ?? 0)
    current.assists += fixture.breakdown?.assist?.count ?? 0
    months.set(key, current)
  }
  return months
}

function monthRange(fixturesA: PlayerFixture[], fixturesB: PlayerFixture[]) {
  const dates = [...fixturesA, ...fixturesB]
    .map(fixtureDate)
    .filter((date): date is Date => date !== null)
  if (dates.length === 0) return []

  const first = new Date(Math.min(...dates.map((date) => date.getTime())))
  const last = new Date(Math.max(...dates.map((date) => date.getTime())))
  const cursor = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1))
  const end = new Date(Date.UTC(last.getUTCFullYear(), last.getUTCMonth(), 1))
  const keys: string[] = []

  while (cursor <= end) {
    keys.push(monthKey(cursor))
    cursor.setUTCMonth(cursor.getUTCMonth() + 1)
  }
  return keys
}

function buildMonths(fixturesA: PlayerFixture[], fixturesB: PlayerFixture[]): MonthStats[] {
  const statsA = aggregateFixtures(fixturesA)
  const statsB = aggregateFixtures(fixturesB)
  return monthRange(fixturesA, fixturesB).map((key) => {
    const date = dateFromMonthKey(key)
    const a = statsA.get(key) ?? { points: 0, matches: 0, goals: 0, assists: 0 }
    const b = statsB.get(key) ?? { points: 0, matches: 0, goals: 0, assists: 0 }
    return {
      key,
      shortLabel: new Intl.DateTimeFormat('es-ES', { month: 'short', timeZone: 'UTC' })
        .format(date).replace('.', '').toUpperCase(),
      fullLabel: new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric', timeZone: 'UTC' })
        .format(date),
      a: a.points,
      b: b.points,
      matchesA: a.matches,
      matchesB: b.matches,
      goalsA: a.goals,
      goalsB: b.goals,
      assistsA: a.assists,
      assistsB: b.assists,
    }
  })
}

function leaderText(a: number, b: number, nameA: string, nameB: string) {
  if (Math.abs(a - b) < 0.01) return 'Empate'
  return a > b ? nameA : nameB
}

function fmtPts(value: number) {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

function peakMonth(months: MonthStats[], side: 'a' | 'b') {
  return months.reduce((peak, month) => month[side] > peak[side] ? month : peak, months[0])
}

export default function MomentumChart({
  fixturesA,
  fixturesB,
  nameA,
  nameB,
}: {
  fixturesA: PlayerFixture[]
  fixturesB: PlayerFixture[]
  nameA: string
  nameB: string
}) {
  const months = useMemo(() => buildMonths(fixturesA, fixturesB), [fixturesA, fixturesB])
  const defaultIndex = useMemo(() => {
    if (months.length === 0) return null
    return months.reduce((best, month, index) => (
      month.a + month.b > months[best].a + months[best].b ? index : best
    ), 0)
  }, [months])
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const activeIndex = hoveredIndex !== null && hoveredIndex < months.length
    ? hoveredIndex
    : defaultIndex
  const active = activeIndex === null ? null : months[activeIndex]
  const maxValue = Math.max(0, ...months.flatMap((month) => [month.a, month.b]))

  if (months.length === 0 || maxValue === 0) {
    return (
      <section className="cmp-momentum">
        <header className="cmp-momentum__header">
          <div>
            <span className="cmp-momentum__eyebrow">Ritmo de la temporada</span>
            <h2>Impacto SFA por mes</h2>
          </div>
        </header>
        <div className="cmp-momentum__empty">No hay partidos con puntos en este periodo.</div>
      </section>
    )
  }

  const pointX = (index: number) => (index + 0.5) / months.length * WIDTH
  const barWidth = Math.min(46, WIDTH / months.length * 0.48)
  const barHeight = (value: number) => value > 0 ? Math.max(3, value / maxValue * AMPLITUDE) : 0
  const peakA = peakMonth(months, 'a')
  const peakB = peakMonth(months, 'b')
  const totalA = months.reduce((sum, month) => sum + month.a, 0)
  const totalB = months.reduce((sum, month) => sum + month.b, 0)

  return (
    <section className="cmp-momentum">
      <header className="cmp-momentum__header">
        <div>
          <span className="cmp-momentum__eyebrow">Ritmo de la temporada</span>
          <h2>Impacto SFA por mes</h2>
        </div>
        <div className="cmp-momentum__legend" aria-label="Leyenda">
          <span><i className="cmp-momentum__key cmp-momentum__key--a" />{nameA}, arriba</span>
          <span><i className="cmp-momentum__key cmp-momentum__key--b" />{nameB}, abajo</span>
        </div>
      </header>

      <div className="cmp-momentum__chart-wrap">
        <svg
          className="cmp-momentum__chart"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Impacto SFA mensual de ${nameA} y ${nameB}`}
        >
          {months.map((month, index) => (
            <line
              key={month.key}
              className="cmp-momentum__grid"
              x1={pointX(index)}
              x2={pointX(index)}
              y1="0"
              y2={HEIGHT}
            />
          ))}
          {[BASELINE / 2, BASELINE + BASELINE / 2].map((y) => (
            <line
              key={y}
              className="cmp-momentum__grid cmp-momentum__grid--horizontal"
              x1="0"
              x2={WIDTH}
              y1={y}
              y2={y}
            />
          ))}
          {activeIndex !== null && (
            <rect
              className="cmp-momentum__active-column"
              x={activeIndex / months.length * WIDTH}
              width={WIDTH / months.length}
              y="0"
              height={HEIGHT}
            />
          )}
          <line className="cmp-momentum__baseline" x1="0" x2={WIDTH} y1={BASELINE} y2={BASELINE} />
          {months.map((month, index) => {
            const heightA = barHeight(month.a)
            const heightB = barHeight(month.b)
            const x = pointX(index) - barWidth / 2
            return (
              <g key={month.key}>
                <rect
                  className="cmp-momentum__bar cmp-momentum__bar--a"
                  x={x}
                  y={BASELINE - heightA}
                  width={barWidth}
                  height={heightA}
                  rx="3"
                />
                <rect
                  className="cmp-momentum__bar cmp-momentum__bar--b"
                  x={x}
                  y={BASELINE}
                  width={barWidth}
                  height={heightB}
                  rx="3"
                />
              </g>
            )
          })}
          {months.map((month, index) => (
            <rect
              key={month.key}
              className="cmp-momentum__hit"
              x={index / months.length * WIDTH}
              y="0"
              width={WIDTH / months.length}
              height={HEIGHT}
              tabIndex={0}
              role="button"
              aria-label={`${month.fullLabel}: ${nameA} ${fmtPts(month.a)} puntos, ${nameB} ${fmtPts(month.b)} puntos`}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
              onFocus={() => setHoveredIndex(index)}
              onBlur={() => setHoveredIndex(null)}
            />
          ))}
        </svg>
        <div
          className="cmp-momentum__axis cmp-momentum__axis--months"
          style={{ gridTemplateColumns: `repeat(${months.length}, minmax(0, 1fr))` }}
          aria-hidden="true"
        >
          {months.map((month) => <span key={month.key}>{month.shortLabel}</span>)}
        </div>
      </div>

      {active && (
        <div className="cmp-momentum__readout" aria-live="polite">
          <div className="cmp-momentum__readout-month">
            <span>Mes seleccionado</span>
            <strong>{active.fullLabel}</strong>
          </div>
          <div className="cmp-momentum__readout-player cmp-momentum__readout-player--a">
            <span>{nameA}</span>
            <strong>{fmtPts(active.a)} pts</strong>
          </div>
          <div className="cmp-momentum__readout-player cmp-momentum__readout-player--b">
            <span>{nameB}</span>
            <strong>{fmtPts(active.b)} pts</strong>
          </div>
        </div>
      )}

      <div className="cmp-momentum__halves cmp-momentum__halves--season">
        <div className="cmp-momentum__peak cmp-momentum__peak--a">
          <span>Mejor mes de {nameA}</span>
          <strong>{peakA.fullLabel}</strong>
          <small>{fmtPts(peakA.a)} pts</small>
        </div>
        <div className="cmp-momentum__peak cmp-momentum__peak--b">
          <span>Mejor mes de {nameB}</span>
          <strong>{peakB.fullLabel}</strong>
          <small>{fmtPts(peakB.b)} pts</small>
        </div>
        <div className="cmp-momentum__peak cmp-momentum__peak--total">
          <span>Mayor impacto en cancha</span>
          <strong>{leaderText(totalA, totalB, nameA, nameB)}</strong>
          <small>{fmtPts(Math.max(totalA, totalB))} pts</small>
        </div>
      </div>
    </section>
  )
}
