import type { PlayerIndividualHonor } from '../../types'

interface Props {
  honors: PlayerIndividualHonor[]
  historical: boolean
}

const HONOR_LABELS: Record<string, string> = {
  top_scorer: 'Bota de oro',
  top_assister: 'M\u00e1ximo asistidor',
  best_dribbler: 'Mejor regateador',
  duel_king: 'Rey de los duelos',
}

const HONOR_CODES: Record<string, string> = {
  top_scorer: 'GO',
  top_assister: 'AS',
  best_dribbler: 'RG',
  duel_king: 'DL',
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString('es-ES')
}

function evidence(honor: PlayerIndividualHonor): string {
  if (honor.honor_type === 'top_scorer') {
    return `${formatNumber(honor.metric_value)} goles`
  }
  if (honor.honor_type === 'top_assister') {
    return `${formatNumber(honor.metric_value)} asistencias`
  }
  if (honor.honor_type === 'best_dribbler') {
    const rate = honor.metric_rate == null ? 0 : honor.metric_rate * 100
    return `${rate.toLocaleString('es-ES', { maximumFractionDigits: 1 })} % \u00b7 ${formatNumber(honor.metric_value)} de ${formatNumber(honor.metric_total ?? 0)} regates`
  }
  const rate = honor.metric_rate == null ? 0 : honor.metric_rate * 100
  return `${formatNumber(honor.metric_value)} duelos ganados \u00b7 ${rate.toLocaleString('es-ES', { maximumFractionDigits: 1 })} %`
}

export default function IndividualHonors({ honors, historical }: Props) {
  if (honors.length === 0) return null

  const grouped = honors.reduce<Record<string, PlayerIndividualHonor[]>>(
    (groups, honor) => {
      ;(groups[honor.scope_label] ??= []).push(honor)
      return groups
    },
    {},
  )

  return (
    <section className="individual-honors" aria-labelledby="individual-honors-title">
      <h2 id="individual-honors-title" className="individual-honors__title">
        {'Palmar\u00e9s individual'}
      </h2>
      <div className="individual-honors__groups">
        {Object.entries(grouped).map(([scopeLabel, items]) => (
          <div className="individual-honors__group" key={scopeLabel}>
            {historical && (
              <p className="individual-honors__scope">{scopeLabel}</p>
            )}
            <div className="individual-honors__list">
              {items.map((honor) => (
                <article className="individual-honors__item" key={honor.honor_id}>
                  <span className="individual-honors__mark" aria-hidden="true">
                    {HONOR_CODES[honor.honor_type] ?? 'IN'}
                  </span>
                  <span className="individual-honors__body">
                    <strong>{HONOR_LABELS[honor.honor_type] ?? honor.honor_type}</strong>
                    <small>{honor.context_label}</small>
                    <span>{evidence(honor)}</span>
                  </span>
                  <span className="individual-honors__points">
                    <strong>+{formatNumber(honor.bonus_pts)}</strong>
                    <small>pts SFA</small>
                  </span>
                </article>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
