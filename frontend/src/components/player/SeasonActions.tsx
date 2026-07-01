import type { PlayerDetail, PlayerFixture } from '../../types'

interface Props {
  player: PlayerDetail
  fixtures: PlayerFixture[]
}

function fmt(n: number): string {
  return n.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

interface ChipProps {
  label: string
  count: number
  pts?: number
}

function Chip({ label, count, pts }: ChipProps) {
  return (
    <div className="sa-chip">
      <span className="sa-chip__label">{label}</span>
      <span className="sa-chip__count">{count}</span>
      {pts != null && pts > 0
        ? <span className="sa-chip__pts">{fmt(pts)} pts</span>
        : <span className="sa-chip__pts sa-chip__pts--empty">—</span>
      }
    </div>
  )
}

export default function SeasonActions({ player, fixtures }: Props) {
  const bd = player.breakdown ?? {}

  const stats = fixtures.reduce(
    (acc, f) => ({
      shots_on:     acc.shots_on     + (f.shots_on     ?? 0),
      dribbles_won: acc.dribbles_won + (f.dribbles_won ?? 0),
      duels_won:    acc.duels_won    + (f.duels_won    ?? 0),
      tackles:      acc.tackles      + (f.tackles_won  ?? 0) + (f.interceptions ?? 0),
      blocks:       acc.blocks       + (f.blocks       ?? 0),
      fouls_drawn:  acc.fouls_drawn  + (f.fouls_drawn  ?? 0),
    }),
    { shots_on: 0, dribbles_won: 0, duels_won: 0, tackles: 0, blocks: 0, fouls_drawn: 0 },
  )

  const allActions: Array<{ key: string; label: string; count: number; pts?: number }> = [
    { key: 'goal',          label: 'Goles',             count: bd['goal']?.count          ?? 0, pts: bd['goal']?.pts },
    { key: 'goal_penalty',  label: 'Penaltis',           count: bd['goal_penalty']?.count  ?? 0, pts: bd['goal_penalty']?.pts },
    { key: 'assist',        label: 'Asistencias',        count: bd['assist']?.count        ?? 0, pts: bd['assist']?.pts },
    { key: 'corner_assist', label: 'Pre-asistencias',    count: bd['corner_assist']?.count ?? 0, pts: bd['corner_assist']?.pts },
    { key: 'penalty_won',   label: 'Penales ganados',    count: bd['penalty_won']?.count   ?? 0, pts: bd['penalty_won']?.pts },
    { key: 'shots_on',      label: 'Disparos',           count: stats.shots_on },
    { key: 'dribbles_won',  label: 'Regates',            count: stats.dribbles_won },
    { key: 'duels_won',     label: 'Duelos ganados',     count: stats.duels_won },
    { key: 'tackles',       label: 'Entradas / Interc.', count: stats.tackles },
    { key: 'blocks',        label: 'Bloqueos',           count: stats.blocks },
    { key: 'fouls_drawn',   label: 'Faltas recibidas',   count: stats.fouls_drawn },
  ]

  const visible = allActions.filter((a) => a.count > 0)
  if (visible.length === 0) return null

  return (
    <div className="card sa-card mt-24">
      <p className="section-title">Acciones de temporada</p>
      <div className="sa-grid">
        {visible.map(({ key, label, count, pts }) => (
          <Chip key={key} label={label} count={count} pts={pts} />
        ))}
      </div>
    </div>
  )
}
