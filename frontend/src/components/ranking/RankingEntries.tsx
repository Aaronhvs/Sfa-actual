import { Link } from 'react-router-dom'
import type { RankedPlayer } from '../../types'
import { worldCupTeamFlagUrl } from '../../utils/worldCupTeams'
import PlayerPortrait from '../shared/PlayerPortrait'
import { FootballIcon, TeamCrest } from '../shared/FootballVisuals'

const POSITION_LABELS: Record<string, string> = {
  DEL: 'Delantero', EXT: 'Extremo', MCO: 'Mediapunta', MC: 'Centrocampista', LAT: 'Lateral', DC: 'Central', GK: 'Portero',
}

type EntryProps = {
  player: RankedPlayer
  href: string
  isWorldCup?: boolean
}

const points = (value: number) => Math.round(value).toLocaleString('es-ES')

function Club({ player, isWorldCup }: { player: RankedPlayer; isWorldCup: boolean }) {
  const flag = isWorldCup ? worldCupTeamFlagUrl(player.team) : null
  return (
    <span className="rk-club">
      <TeamCrest key={player.team} url={flag ?? player.team_logo_url} name={player.team} />
      <span>{player.team}</span>
    </span>
  )
}

/** One ranking row: rank, identity, three counting stats and SFA points. */
export function RankingRow({ player, href, isWorldCup = false }: EntryProps) {
  return (
    <Link className="rk-row" to={href}>
      <b className="rk-row__rank">{player.rank}</b>
      <PlayerPortrait player={player} className="rk-row__photo" />
      <span className="rk-row__who">
        <strong>{player.name}</strong>
        <span className="rk-row__meta">
          <Club player={player} isWorldCup={isWorldCup} />
          <span className="rk-pos">{POSITION_LABELS[player.position] ?? player.position}</span>
          {player.b1_bonus_label && <span className="rk-tag">{player.b1_bonus_label}</span>}
        </span>
      </span>
      <span className="rk-row__stat"><b>{player.goals}</b><small>Goles</small></span>
      <span className="rk-row__stat"><b>{player.assists}</b><small>Asist.</small></span>
      <span className="rk-row__stat"><b>{player.matches}</b><small>Partidos</small></span>
      <span className="rk-row__pts"><b>{points(player.sfa_pts)}</b><small>pts SFA</small></span>
    </Link>
  )
}

/** Photo card for the "Fichas" view. */
export function RankingTile({ player, href, isWorldCup = false }: EntryProps) {
  return (
    <Link className="rk-tile" to={href}>
      <span className="rk-tile__top">
        <b>{player.rank}</b>
        <span className="rk-pos">{player.position}</span>
      </span>
      <PlayerPortrait player={player} className="rk-tile__photo" />
      <strong className="rk-tile__name">{player.name}</strong>
      <Club player={player} isWorldCup={isWorldCup} />
      <span className="rk-tile__pts"><b>{points(player.sfa_pts)}</b><small>pts SFA</small></span>
      <span className="rk-tile__stats">
        <span><span className="rk-tile__stat"><FootballIcon kind="goal" /><b>{player.goals}</b></span><small>Goles</small></span>
        <span><span className="rk-tile__stat"><FootballIcon kind="assist" /><b>{player.assists}</b></span><small>Asist.</small></span>
        <span><span className="rk-tile__stat"><FootballIcon kind="matches" /><b>{player.matches}</b></span><small>Partidos</small></span>
      </span>
    </Link>
  )
}
