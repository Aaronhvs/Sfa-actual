import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import type { RankingPlayerExplanation } from '../../types'
import { formatSfaPoints, rankingEvidence } from './rankingEvidence'

interface Props { explanation: RankingPlayerExplanation | null; onClose: () => void }
export default function RankingExplanationModal({ explanation, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!explanation || !dialogRef.current) return
    const dialog = dialogRef.current
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => { dialog.close(); document.body.style.overflow = previousOverflow; if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true }) }
  }, [explanation])
  if (!explanation) return null
  const { total, breakdown, featured, summary, unexplained } = rankingEvidence(explanation)
  return createPortal(<dialog ref={dialogRef} className="sfa-analysis-dialog" aria-labelledby="sfa-analysis-title"
    onKeyDown={event => {
      if (event.key !== 'Tab') return
      const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]'))
        .filter(item => item.getClientRects().length > 0)
      const first = items[0], last = items[items.length - 1]
      if (first && ((!event.shiftKey && document.activeElement === last) || (event.shiftKey && document.activeElement === first))) {
        event.preventDefault(); (event.shiftKey ? last : first).focus()
      }
    }}
    onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className="sfa-analysis-dialog__content">
      <button className="sfa-analysis-dialog__close" type="button" onClick={onClose} aria-label="Cerrar desglose">×</button>
      <p className="sfa-analysis-dialog__eyebrow">Desglose SFA · {explanation.team_name}</p>
      <h2 id="sfa-analysis-title">{explanation.player_name ?? 'Jugador'}</h2><p>{summary}</p>
      {breakdown.length > 0 && <dl className="sfa-analysis-dialog__breakdown">
        {breakdown.map((item, index) => <div key={`${item.label}-${index}`}><dt>{item.label}</dt><dd>{formatSfaPoints(item.points, 2)} <small>pts</small></dd></div>)}
        {total > 0 && <div className="sfa-analysis-dialog__total"><dt>Total SFA</dt><dd>{formatSfaPoints(total, 2)} <small>pts</small></dd></div>}
      </dl>}
      {breakdown.length > 0 && Math.abs(unexplained) > .1 && <p className="sfa-analysis-dialog__note">El desglose recibido difiere del total en {formatSfaPoints(Math.abs(unexplained), 2)} puntos. No se dispone del detalle de esa diferencia.</p>}
      {featured && <section className="sfa-analysis-dialog__example" aria-labelledby="sfa-analysis-example">
        <h3 id="sfa-analysis-example">Una acción con contexto</h3>
        <p><strong>{featured.label}{featured.minute != null ? ` · ${featured.minute}′` : ''}</strong><br />{featured.match}</p>
        {featured.score && <p>Marcador antes de la acción: {featured.score}</p>}
        {featured.stage && <p>Fase: {featured.stage}</p>}
        <p className="sfa-analysis-dialog__event-points">{formatSfaPoints(featured.points, 2)} puntos SFA</p>
        <small>Acción destacada entre los partidos disponibles. Es una parte de la puntuación total.</small>
      </section>}
      <p className="sfa-analysis-dialog__note">El rendimiento del partido agrupa la valoración estadística; no representa una jugada aislada.</p>
    </div>
  </dialog>, document.body)
}
