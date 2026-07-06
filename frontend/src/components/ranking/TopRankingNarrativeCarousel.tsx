import { useEffect, useMemo, useState } from 'react'
import type { RankedPlayer, RankingPlayerExplanation } from '../../types'

interface Props {
  players: RankedPlayer[]
  explanations: RankingPlayerExplanation[]
  onOpenAnalysis: (explanation: RankingPlayerExplanation) => void
}

function cleanNarrativeText(text: string, player: RankedPlayer): string {
  const withoutRank = text.replace(new RegExp(`^#?${player.rank}:?\\s*`, 'i'), '').trim()
  const escapedName = player.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const withoutScoreLine = withoutRank
    .replace(new RegExp(`^${escapedName}\\s+suma\\s+[\\d.,]+\\s+pts?\\s+en\\s+\\d+\\s+partidos?:?\\s*`, 'i'), '')
    .trim()

  if (withoutScoreLine.length >= 60) return withoutScoreLine

  return 'El motor no repite una tabla de goleadores: pondera rival, minuto, fase y tipo de accion para explicar por que este impacto pesa dentro del top.'
}

function buildHook(player: RankedPlayer): string {
  const directImpact = [
    player.goals > 0 ? `${player.goals} goles` : null,
    player.assists > 0 ? `${player.assists} asistencias` : null,
  ].filter(Boolean).join(' y ')

  if (directImpact) {
    return `${directImpact} en ${player.matches} partidos. La pregunta es cuando pesaron.`
  }

  if (player.b1_bonus_label) {
    return `${player.b1_bonus_label} con impacto real: SFA mira contexto, no solo volumen.`
  }

  return 'SFA mira el peso de sus acciones: rival, momento, fase e impacto.'
}

function shortName(name: string): string {
  const parts = name.split(' ').filter(Boolean)
  if (parts.length <= 1) return name
  return parts[parts.length - 1]
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
  const narrativeText = cleanNarrativeText(explanation.short_text, slide.player)
  const hook = buildHook(slide.player)

  return (
    <section
      className="top-narrative"
      aria-label="Lectura SFA del top del ranking"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onTouchStart={() => setPaused(true)}
    >
      <div className="top-narrative__tabs" aria-label="Cambiar lectura del top 3">
        {slides.map((item, index) => (
          <button
            key={item.player.id}
            type="button"
            className={index === active ? 'is-active' : ''}
            onClick={() => setActive(index)}
            aria-label={`Ver lectura de ${item.player.name}`}
          >
            <span>#{item.player.rank}</span>
            <strong>{shortName(item.player.name)}</strong>
          </button>
        ))}
      </div>
      <div className="top-narrative__body">
        <div className="top-narrative__headline">
          <span className="top-narrative__eyebrow">Por que este puesto</span>
          <h3>
            <span>#{slide.player.rank}</span>
            {slide.player.name}
          </h3>
        </div>

        <div className="top-narrative__story">
          <strong>{hook}</strong>
          <p>{narrativeText}</p>
        </div>

        <div className="top-narrative__chips" aria-label="Factores que explica SFA">
          <span>
            <strong>Rival</strong>
            <small>dificultad</small>
          </span>
          <span>
            <strong>Momento</strong>
            <small>marcador</small>
          </span>
          <span>
            <strong>Fase</strong>
            <small>presion</small>
          </span>
          <span>
            <strong>Accion</strong>
            <small>impacto</small>
          </span>
        </div>
        <button
          type="button"
          className="top-narrative__link"
          onClick={() => onOpenAnalysis(explanation)}
        >
          Ver analisis
        </button>
      </div>
    </section>
  )
}
