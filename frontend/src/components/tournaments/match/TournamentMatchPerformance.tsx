import { Link } from 'react-router-dom'
import type { TournamentMatchTeamLineup } from '../../../types'

export default function TournamentMatchPerformance({ lineups, scope }: { lineups: TournamentMatchTeamLineup[]; scope: string }) {
  const players = lineups.flatMap((lineup) => [...lineup.start_xi, ...lineup.substitutes].map((player) => ({ player, team: lineup.team.name }))).filter(({ player }) => player.sfa_points != null).sort((a, b) => (b.player.sfa_points ?? 0) - (a.player.sfa_points ?? 0))
  if (players.length === 0) return <div className="trm-empty">El rendimiento SFA está pendiente de cálculo.</div>
  return (
    <section className="trm-section trm-performance">
      <header><span>Impacto individual</span><h2>Rendimiento SFA</h2></header>
      <div className="trm-performance__list">
        {players.map(({ player, team }, index) => {
          const content = <><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{player.name}</strong><small>{team}{player.position ? ` · ${player.position}` : ''}</small></div><b>{Math.round(player.sfa_points ?? 0).toLocaleString('es-ES')} <small>pts</small></b></>
          return player.player_id != null
            ? <Link className="trm-performance__row" to={`/player/${player.player_id}?scope=${scope}`} key={`${player.external_id ?? player.name}-${index}`}>{content}</Link>
            : <div className="trm-performance__row" key={`${player.external_id ?? player.name}-${index}`}>{content}</div>
        })}
      </div>
    </section>
  )
}
