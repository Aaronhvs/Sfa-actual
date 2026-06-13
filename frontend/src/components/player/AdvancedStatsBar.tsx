import type { PlayerSeasonStats } from '../../types'

interface Props {
  stats: PlayerSeasonStats
  position: string
}

function fmt(n: number): string {
  return n.toLocaleString('es-ES')
}

interface StatItem {
  label: string
  value: string
  sub?: string
  warn?: boolean
}

export default function AdvancedStatsBar({ stats, position }: Props) {
  const isGK = position === 'GK'

  const passesCompleted = stats.passes_accuracy_avg > 0
    ? `${fmt(Math.round(stats.passes_total * stats.passes_accuracy_avg / 100))} / ${fmt(stats.passes_total)}`
    : fmt(stats.passes_total)

  const items: StatItem[] = [
    {
      label: 'Pases comp.',
      value: passesCompleted,
      sub: stats.passes_accuracy_avg > 0 ? `${Math.round(stats.passes_accuracy_avg)}% prec.` : undefined,
    },
    {
      label: 'Disparos tot.',
      value: fmt(stats.shots_total),
      sub: stats.shots_on > 0 ? `${fmt(stats.shots_on)} a puerta` : undefined,
    },
    {
      label: 'Duelos tot.',
      value: fmt(stats.duels_total),
      sub: stats.duel_win_rate != null ? `${Math.round(stats.duel_win_rate * 100)}% gan.` : undefined,
    },
    {
      label: 'Reg. sufridos',
      value: fmt(stats.dribbles_past),
    },
    {
      label: 'Penales gan.',
      value: fmt(stats.penalty_won),
    },
    {
      label: 'Faltas com.',
      value: fmt(stats.fouls_committed),
      warn: stats.fouls_committed > 40,
    },
    {
      label: 'T. amarillas',
      value: fmt(stats.cards_yellow),
      warn: stats.cards_yellow > 0,
    },
    {
      label: 'T. rojas',
      value: fmt(stats.cards_red),
      warn: stats.cards_red > 0,
    },
    ...(isGK ? [
      { label: 'Paradas', value: fmt(stats.saves) },
      { label: 'Goles rec.', value: fmt(stats.goals_conceded), warn: true },
    ] : []),
  ]

  return (
    <div className="adv-stats-bar">
      {items.map((item) => (
        <div key={item.label} className="adv-stats-bar__item">
          <span className={`adv-stats-bar__num${item.warn ? ' adv-stats-bar__num--warn' : ''}`}>
            {item.value}
          </span>
          <span className="adv-stats-bar__label">{item.label}</span>
          {item.sub && <span className="adv-stats-bar__sub">{item.sub}</span>}
        </div>
      ))}
    </div>
  )
}
