import { useMemo, useState } from 'react'
import type { PlayerEvent } from '../../types'

const BUCKET_SIZE = 5
const BUCKET_COUNT = 18
const WIDTH = 1000
const HEIGHT = 250
const BASELINE = HEIGHT / 2
const AMPLITUDE = 94

interface Bucket {
  start: number
  end: number
  a: number
  b: number
}

function bucketEvents(events: PlayerEvent[]) {
  const buckets = Array.from({ length: BUCKET_COUNT }, () => 0)
  for (const event of events) {
    if (event.event_type === 'stats' || event.minute <= 0 || event.pts <= 0) continue
    const minute = Math.min(event.minute, 90)
    const index = Math.min(BUCKET_COUNT - 1, Math.floor((minute - 1) / BUCKET_SIZE))
    buckets[index] += event.pts
  }
  return buckets
}

function sumRange(values: number[], start: number, end: number) {
  return values.slice(start, end).reduce((sum, value) => sum + value, 0)
}

function leaderText(a: number, b: number, nameA: string, nameB: string) {
  if (Math.abs(a - b) < 0.01) return 'Empate'
  return a > b ? nameA : nameB
}

function fmtPts(value: number) {
  return Math.round(value).toLocaleString('es-ES')
}

export default function MomentumChart({
  eventsA,
  eventsB,
  nameA,
  nameB,
}: {
  eventsA: PlayerEvent[]
  eventsB: PlayerEvent[]
  nameA: string
  nameB: string
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const valuesA = useMemo(() => bucketEvents(eventsA), [eventsA])
  const valuesB = useMemo(() => bucketEvents(eventsB), [eventsB])
  const maxValue = Math.max(0, ...valuesA, ...valuesB)

  const buckets: Bucket[] = valuesA.map((a, index) => ({
    start: index * BUCKET_SIZE,
    end: index === BUCKET_COUNT - 1 ? 90 : (index + 1) * BUCKET_SIZE,
    a,
    b: valuesB[index],
  }))

  if (maxValue === 0) {
    return (
      <section className="cmp-momentum">
        <header className="cmp-momentum__header">
          <div>
            <span className="cmp-momentum__eyebrow">Momento del partido</span>
            <h2>Impacto por minuto</h2>
          </div>
        </header>
        <div className="cmp-momentum__empty">No hay eventos minutados con puntos en este periodo.</div>
      </section>
    )
  }

  const pointX = (index: number) => index / (BUCKET_COUNT - 1) * WIDTH
  const pointsA = valuesA.map((value, index) => `${pointX(index)},${BASELINE - value / maxValue * AMPLITUDE}`)
  const pointsB = valuesB.map((value, index) => `${pointX(index)},${BASELINE + value / maxValue * AMPLITUDE}`)
  const areaA = `0,${BASELINE} ${pointsA.join(' ')} ${WIDTH},${BASELINE}`
  const areaB = `0,${BASELINE} ${pointsB.join(' ')} ${WIDTH},${BASELINE}`
  const earlyA = sumRange(valuesA, 0, 9)
  const earlyB = sumRange(valuesB, 0, 9)
  const lateA = sumRange(valuesA, 9, BUCKET_COUNT)
  const lateB = sumRange(valuesB, 9, BUCKET_COUNT)
  const active = activeIndex === null ? null : buckets[activeIndex]

  return (
    <section className="cmp-momentum">
      <header className="cmp-momentum__header">
        <div>
          <span className="cmp-momentum__eyebrow">Momento del partido</span>
          <h2>Impacto SFA por minuto</h2>
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
          aria-label={`Impacto SFA por minuto de ${nameA} y ${nameB}`}
        >
          {[0, 15, 30, 45, 60, 75, 90].map((minute) => (
            <line
              key={minute}
              className="cmp-momentum__grid"
              x1={minute / 90 * WIDTH}
              x2={minute / 90 * WIDTH}
              y1="0"
              y2={HEIGHT}
            />
          ))}
          <line className="cmp-momentum__baseline" x1="0" x2={WIDTH} y1={BASELINE} y2={BASELINE} />
          <polygon className="cmp-momentum__area cmp-momentum__area--a" points={areaA} />
          <polyline className="cmp-momentum__line cmp-momentum__line--a" points={pointsA.join(' ')} />
          <polygon className="cmp-momentum__area cmp-momentum__area--b" points={areaB} />
          <polyline className="cmp-momentum__line cmp-momentum__line--b" points={pointsB.join(' ')} />
          {buckets.map((bucket, index) => (
            <rect
              key={bucket.start}
              className="cmp-momentum__hit"
              x={index / BUCKET_COUNT * WIDTH}
              y="0"
              width={WIDTH / BUCKET_COUNT}
              height={HEIGHT}
              tabIndex={0}
              role="button"
              aria-label={`Minutos ${bucket.start + 1} a ${bucket.end}: ${nameA} ${fmtPts(bucket.a)} puntos, ${nameB} ${fmtPts(bucket.b)} puntos`}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
              onFocus={() => setActiveIndex(index)}
              onBlur={() => setActiveIndex(null)}
            />
          ))}
        </svg>
        <div className="cmp-momentum__axis" aria-hidden="true">
          {[0, 15, 30, 45, 60, 75, '90+'].map((minute) => <span key={minute}>{minute}'</span>)}
        </div>
      </div>

      <div className="cmp-momentum__readout" aria-live="polite">
        {active
          ? <>
              <strong>Min. {active.start + 1}–{active.end}</strong>
              <span>{nameA}: {fmtPts(active.a)} pts</span>
              <span>{nameB}: {fmtPts(active.b)} pts</span>
            </>
          : <span>Enfoca o pasa sobre un tramo para ver el detalle.</span>
        }
      </div>

      <div className="cmp-momentum__halves">
        <div>
          <span>0–45'</span>
          <strong>{leaderText(earlyA, earlyB, nameA, nameB)}</strong>
          <small>{fmtPts(earlyA)} · {fmtPts(earlyB)} pts</small>
        </div>
        <div>
          <span>46–90+'</span>
          <strong>{leaderText(lateA, lateB, nameA, nameB)}</strong>
          <small>{fmtPts(lateA)} · {fmtPts(lateB)} pts</small>
        </div>
      </div>
    </section>
  )
}
