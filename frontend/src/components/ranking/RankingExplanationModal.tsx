import type { RankingPlayerExplanation } from '../../types'

interface Props {
  explanation: RankingPlayerExplanation | null
  onClose: () => void
}

export default function RankingExplanationModal({ explanation, onClose }: Props) {
  if (!explanation) return null
  const player = explanation.evidence?.player as Record<string, unknown> | undefined
  const playerName = explanation.player_name ?? (typeof player?.name === 'string' ? player.name : 'Jugador')

  return (
    <div className="analysis-modal" role="dialog" aria-modal="true" aria-label="Analisis SFA">
      <button className="analysis-modal__backdrop" type="button" onClick={onClose} aria-label="Cerrar analisis" />
      <div className="analysis-modal__panel">
        <button className="analysis-modal__close" type="button" onClick={onClose} aria-label="Cerrar">
          x
        </button>
        <span className="analysis-modal__eyebrow">Analisis SFA</span>
        <h3>{playerName}</h3>
        <p>{explanation.long_text}</p>
        {explanation.bullets.length > 0 && (
          <ul>
            {explanation.bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        )}
        <div className="analysis-modal__chips">
          {typeof player?.total_pts === 'number' && <span>{Math.round(player.total_pts).toLocaleString('es-ES')} pts</span>}
          {typeof player?.matches === 'number' && <span>{player.matches} PJ</span>}
          {typeof player?.b1_bonus_pts === 'number' && player.b1_bonus_pts > 0 && <span>{player.b1_bonus_pts} bonus</span>}
        </div>
      </div>
    </div>
  )
}
