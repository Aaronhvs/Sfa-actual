import type { TournamentMatchStatistic } from '../../../types'

const LABELS: Record<string, string> = {
  'Ball Possession': 'Posesión',
  'Total Shots': 'Remates',
  'Shots on Goal': 'Remates al arco',
  'Shots off Goal': 'Remates fuera',
  'Blocked Shots': 'Remates bloqueados',
  'Corner Kicks': 'Tiros de esquina',
  Fouls: 'Faltas',
  Offsides: 'Fuera de juego',
  'Yellow Cards': 'Tarjetas amarillas',
  'Red Cards': 'Tarjetas rojas',
  'Goalkeeper Saves': 'Atajadas',
  'Total passes': 'Pases',
  'Passes accurate': 'Pases completados',
  'Passes %': 'Precisión de pase',
}

export default function TournamentMatchStatistics({ statistics }: { statistics: TournamentMatchStatistic[] }) {
  if (statistics.length === 0) return <div className="trm-empty">Las estadísticas estarán disponibles cuando la fuente las publique.</div>
  return (
    <section className="trm-section trm-statistics">
      <header><span>Datos del partido</span><h2>Estadísticas</h2></header>
      <div className="trm-statistics__list">
        {statistics.map((stat) => {
          const home = stat.home_numeric ?? 0
          const away = stat.away_numeric ?? 0
          const total = Math.max(home + away, 1)
          return (
            <div className="trm-stat" key={stat.label}>
              <strong>{stat.home_value ?? '-'}</strong>
              <div>
                <span>{LABELS[stat.label] ?? stat.label}</span>
                <i><b style={{ width: `${(home / total) * 100}%` }} /><em style={{ width: `${(away / total) * 100}%` }} /></i>
              </div>
              <strong>{stat.away_value ?? '-'}</strong>
            </div>
          )
        })}
      </div>
    </section>
  )
}
