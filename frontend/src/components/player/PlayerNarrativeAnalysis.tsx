import type { RankingPlayerExplanation } from '../../types'

interface Props {
  explanation: RankingPlayerExplanation | null
}

export default function PlayerNarrativeAnalysis({ explanation }: Props) {
  if (!explanation) return null

  return (
    <section className="player-analysis" aria-label="Analisis SFA del jugador">
      <div>
        <span>Analisis SFA</span>
        <h2>Por que aparece en el top</h2>
      </div>
      <p>{explanation.long_text}</p>
      {explanation.bullets.length > 0 && (
        <ul>
          {explanation.bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
