import { useEffect } from 'react'
import type { PlayerEvent, PlayerFixture } from '../../types'
import { competitionLabel, stageLabel } from '../../utils/footballLabels'

export interface ModalFixtureItem {
  type: 'fixture'
  fixture: PlayerFixture
  extra?: string
}

export interface ModalEventItem {
  type: 'event'
  event: PlayerEvent
  fixture: PlayerFixture
}

export type ModalItem = ModalFixtureItem | ModalEventItem

interface Props {
  title: string
  subtitle?: string
  items: ModalItem[]
  onClose: () => void
}

function fmt(n: number): string {
  return Math.round(n).toLocaleString('es-ES')
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })
}

function scoreContext(scoreDiff: number | null): string {
  if (scoreDiff === null) return ''
  if (scoreDiff < 0) return 'Perdiendo'
  if (scoreDiff === 0) return 'Empatando'
  return 'Ganando'
}

export default function MatchListModal({ title, subtitle, items, onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <p className="modal__title">{title}</p>
            {subtitle && <p className="modal__subtitle">{subtitle}</p>}
          </div>
          <button className="modal__close" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>

        <div className="modal__list">
          {items.map((item, i) => {
            if (item.type === 'fixture') {
              const f = item.fixture
              const goals = (f.breakdown?.['goal']?.count ?? 0) + (f.breakdown?.['goal_penalty']?.count ?? 0)
              const assists = f.breakdown?.['assist']?.count ?? 0
              return (
                <div key={i} className="modal__item">
                  <div className="modal__item-main">
                    <span className="modal__item-match">{f.home_team} vs {f.away_team}</span>
                    <span className="modal__item-meta">{competitionLabel(f.competition)} · {stageLabel(f.stage)} · {formatDate(f.played_at)}</span>
                  </div>
                  <div className="modal__item-right">
                    {goals > 0 && <span className="modal__chip modal__chip--gold">{goals}G</span>}
                    {assists > 0 && <span className="modal__chip modal__chip--gold">{assists}A</span>}
                    {item.extra && <span className="modal__chip">{item.extra}</span>}
                    <span className="modal__item-pts">{fmt(f.sfa_pts)} pts</span>
                  </div>
                </div>
              )
            }

            const { event: ev, fixture: f } = item
            return (
              <div key={i} className="modal__item">
                <div className="modal__item-main">
                  <span className="modal__item-match">{f.home_team} vs {f.away_team}</span>
                  <span className="modal__item-meta">
                    {competitionLabel(f.competition)} · {formatDate(f.played_at)}
                    {ev.minute ? ` · min ${ev.minute}'` : ''}
                    {ev.score_diff !== null ? ` · ${scoreContext(ev.score_diff)}` : ''}
                  </span>
                </div>
                <div className="modal__item-right">
                  <span className="modal__item-pts">+{fmt(ev.pts)} pts</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
