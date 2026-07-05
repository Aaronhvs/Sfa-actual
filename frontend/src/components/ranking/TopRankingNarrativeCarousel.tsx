import { useEffect, useMemo, useState } from 'react'
import type { RankedPlayer, RankingPlayerExplanation } from '../../types'

interface Props {
  players: RankedPlayer[]
  explanations: RankingPlayerExplanation[]
  onOpenAnalysis: (explanation: RankingPlayerExplanation) => void
}

function evidenceNumber(explanation: RankingPlayerExplanation, key: string): number | null {
  const player = explanation.evidence?.player
  if (!player || typeof player !== 'object') return null
  const value = (player as Record<string, unknown>)[key]
  return typeof value === 'number' ? value : null
}

export default function TopRankingNarrativeCarousel({ players, explanations, onOpenAnalysis }: Props) {
  const [active, setActive] = useState(0)
  const [paused, setPaused] = useState(false)
  const byPlayer = useMemo(() => new Map(explanations.map((item) => [item.player_id, item])), [explanations])
  const slides = players
    .slice(0, 3)
    .map((player) => ({ player, explanation: byPlayer.get(player.id) }))
    .filter((slide) => slide.explanation)

  useEffect(() => {
    if (paused || slides.length <= 1) return
    const id = window.setInterval(() => {
      setActive((current) => (current + 1) % slides.length)
    }, 3000)
    return () => window.clearInterval(id)
  }, [paused, slides.length])

  useEffect(() => {
    if (active >= slides.length) setActive(0)
  }, [active, slides.length])

  if (slides.length === 0) return null

  const slide = slides[active]
  const explanation = slide.explanation!
  const goals = evidenceNumber(explanation, 'goals')
  const assists = evidenceNumber(explanation, 'assists')
  const points = evidenceNumber(explanation, 'total_pts')
  const bullets = explanation.bullets.length > 0
    ? explanation.bullets.slice(0, 3)
    : [
        points != null ? `${Math.round(points).toLocaleString('es-ES')} pts` : null,
        goals != null ? `${goals} goles` : null,
        assists != null ? `${assists} asistencias` : null,
      ].filter((item): item is string => Boolean(item)).slice(0, 3)

  return (
    <section
      className="top-narrative"
      aria-label="Analisis del top del ranking"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onTouchStart={() => setPaused(true)}
    >
      <div className="top-narrative__media">
        {slide.player.photo_url && <img src={slide.player.photo_url} alt="" />}
        <span>#{slide.player.rank}</span>
      </div>
      <div className="top-narrative__body">
        <span className="top-narrative__eyebrow">Por que esta arriba</span>
        <h3>{slide.player.name}</h3>
        <p className="top-narrative__hook">{explanation.short_text}</p>
        {bullets.length > 0 && (
          <ul className="top-narrative__bullets" aria-label="Datos clave">
            {bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        )}
        <button
          type="button"
          className="top-narrative__link"
          onClick={() => onOpenAnalysis(explanation)}
        >
          Leer mas
        </button>
      </div>
      <div className="top-narrative__dots" aria-hidden="true">
        {slides.map((item, index) => (
          <button
            key={item.player.id}
            type="button"
            className={index === active ? 'is-active' : ''}
            onClick={() => setActive(index)}
            tabIndex={-1}
          />
        ))}
      </div>
    </section>
  )
}
