import { useEffect, useState } from 'react'
import type { RankedPlayer, RankingPlayerExplanation } from '../../types'
import { formatSfaPoints, rankingEvidence } from './rankingEvidence'

interface Props { players: RankedPlayer[]; explanations: RankingPlayerExplanation[]; onOpenAnalysis: (explanation: RankingPlayerExplanation) => void }
export default function TopRankingNarrativeCarousel({ players, explanations, onOpenAnalysis }: Props) {
  const [active, setActive] = useState(0)
  const slides = players.slice(0, 3).flatMap(player => {
    const explanation = explanations.find(item => item.player_id === player.id)
    return explanation ? [{ player, explanation }] : []
  })
  useEffect(() => { setActive(0) }, [players])
  const slide = slides[active] ?? slides[0]
  if (!slide) return null
  const { summary, featured } = rankingEvidence(slide.explanation)
  return <section className="top-narrative" aria-label="Desglose de puntos del top 3">
    <div className="top-narrative__tabs" aria-label="Elegir jugador para consultar su desglose">
      {slides.map((item, index) => <button key={item.player.id} type="button" className={slide.player.id === item.player.id ? 'is-active' : ''}
        aria-label={`Ver desglose de ${item.player.name}`} aria-pressed={slide.player.id === item.player.id} onClick={() => setActive(index)}>
        <span>#{item.player.rank}</span><strong>{item.player.name.split(' ').slice(-1)[0]}</strong>
      </button>)}
    </div>
    <div className="top-narrative__body">
      <div className="top-narrative__headline"><span className="top-narrative__eyebrow">De dónde salen sus puntos</span><h3>{slide.player.name}</h3></div>
      <div className="top-narrative__story"><strong>{summary}</strong>
        {featured && <p>{featured.label}{featured.minute != null ? ` en el ${featured.minute}′` : ''} · {featured.match}{featured.score ? ` · Marcador previo ${featured.score}` : ''} · {formatSfaPoints(featured.points, 2)} puntos.</p>}
      </div>
      <button type="button" className="top-narrative__link" onClick={() => onOpenAnalysis(slide.explanation)}>Ver desglose</button>
    </div>
  </section>
}
