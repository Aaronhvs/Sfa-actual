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

const HONOR_TONES: Record<string, string> = {
  top_scorer: 'scorer',
  top_assister: 'assister',
  best_dribbler: 'dribbler',
  duel_king: 'duelist',
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
              {items.map((honor) => {
                const label = HONOR_LABELS[honor.honor_type] ?? honor.honor_type
                const metric = evidence(honor)
                const points = `+${formatNumber(honor.bonus_pts)} pts SFA`
                return (
                  <article
                    className={`individual-honors__item individual-honors__item--${HONOR_TONES[honor.honor_type] ?? 'default'}`}
                    key={honor.honor_id}
                    tabIndex={0}
                    aria-label={`${label} en ${honor.context_label}. ${metric}. ${points}.`}
                    onFocus={(event) => event.currentTarget.scrollIntoView({ block: 'nearest', inline: 'center' })}
                  >
                    <span className="individual-honors__face individual-honors__face--summary" aria-hidden="true">
                      <span className="individual-honors__mark">
                        {HONOR_CODES[honor.honor_type] ?? 'IN'}
                      </span>
                      <span className="individual-honors__body">
                        <strong>{label}</strong>
                        <small>{honor.context_label}</small>
                      </span>
                    </span>
                    <span className="individual-honors__face individual-honors__face--detail" aria-hidden="true">
                      <small>{honor.context_label}</small>
                      <span>{metric}</span>
                      <strong>{points}</strong>
                    </span>
                  </article>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
