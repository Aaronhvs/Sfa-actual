import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import type { TournamentMatchLineupPlayer, TournamentMatchTeamLineup } from '../../../types'

const playerPhoto = (externalId: number | null) => externalId
  ? `https://media.api-sports.io/football/players/${externalId}.png`
  : null

function Player({ player, scope }: { player: TournamentMatchLineupPlayer; scope: string }) {
  const photo = playerPhoto(player.external_id)
  const content = <>{photo ? <img src={photo} alt="" loading="lazy" /> : <span>{player.number ?? '-'}</span>}<div><strong>{player.name}</strong><small>{player.position ?? 'Posición por confirmar'}</small></div>{player.sfa_points != null && <b>{Math.round(player.sfa_points).toLocaleString('es-ES')} pts</b>}</>
  return player.player_id != null
    ? <Link className="trm-player" to={`/player/${player.player_id}?scope=${scope}`}>{content}</Link>
    : <div className="trm-player">{content}</div>
}

function TacticalPitch({ players, scope }: { players: TournamentMatchTeamLineup['start_xi']; scope: string }) {
  const placed = players.flatMap((player) => {
    const [row, column] = player.grid?.split(':').map(Number) ?? []
    return Number.isFinite(row) && Number.isFinite(column) ? [{ player, row, column }] : []
  })
  if (placed.length === 0) return null
  const maxRow = Math.max(...placed.map((item) => item.row), 1)
  return (
    <div className="trm-pitch" aria-label="Disposición táctica">
      {placed.map(({ player, row, column }, index) => {
        const rowSize = placed.filter((item) => item.row === row).length
        const style = {
          '--pitch-x': `${(column / (rowSize + 1)) * 100}%`,
          '--pitch-y': `${((row - 0.5) / maxRow) * 100}%`,
        } as CSSProperties
        const names = player.name.split(' ')
        const content = <><span>{player.number ?? '-'}</span><strong>{names[names.length - 1]}</strong></>
        return player.player_id != null
          ? <Link to={`/player/${player.player_id}?scope=${scope}`} className="trm-pitch__player" style={style} key={`${player.external_id ?? player.name}-${index}`}>{content}</Link>
          : <div className="trm-pitch__player" style={style} key={`${player.external_id ?? player.name}-${index}`}>{content}</div>
      })}
    </div>
  )
}

function TeamLineup({ lineup, scope }: { lineup: TournamentMatchTeamLineup; scope: string }) {
  return (
    <section className="trm-lineup">
      <header><div><span>{lineup.formation ?? 'Formación por confirmar'}</span><h2>{lineup.team.name}</h2></div><small>{lineup.coach_name ? `DT · ${lineup.coach_name}` : 'Director técnico por confirmar'}</small></header>
      <TacticalPitch players={lineup.start_xi} scope={scope} />
      <h3>Titulares</h3>
      <div>{lineup.start_xi.map((player, index) => <Player key={`${player.external_id ?? player.name}-${index}`} player={player} scope={scope} />)}</div>
      {lineup.substitutes.length > 0 && <><h3>Suplentes</h3><div>{lineup.substitutes.map((player, index) => <Player key={`${player.external_id ?? player.name}-${index}`} player={player} scope={scope} />)}</div></>}
    </section>
  )
}

export default function TournamentMatchLineups({ lineups, scope }: { lineups: TournamentMatchTeamLineup[]; scope: string }) {
  if (lineups.length === 0) return <div className="trm-empty">Las alineaciones todavía no fueron publicadas.</div>
  return <div className="trm-lineups">{lineups.map((lineup) => <TeamLineup lineup={lineup} scope={scope} key={lineup.team.external_id ?? lineup.team.id} />)}</div>
}
