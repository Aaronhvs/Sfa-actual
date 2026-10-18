import { Link } from 'react-router-dom'
import type { RankedPlayer } from '../../types'
import { worldCupTeamFlagUrl } from '../../utils/worldCupTeams'
import PlayerPortrait from '../shared/PlayerPortrait'
import { FootballIcon, TeamCrest } from '../shared/FootballVisuals'

interface Props {
  player: RankedPlayer
  index?: number
  competitionName?: string
  scope?: string
  isWorldCup?: boolean
  returnTo?: string
}

export default function RankingCard({ player, competitionName, scope, isWorldCup = false, returnTo }: Props) {
  const params = new URLSearchParams()
  if (scope) params.set('scope', scope)
  if (returnTo) params.set('returnTo', returnTo)
  const flag = isWorldCup ? worldCupTeamFlagUrl(player.team) : null

  return <Link className="sfa-player-poster" data-player-id={player.id} to={`/player/${player.id}?${params}`}>
    <div className="sfa-player-poster__visual">
      <span className="sfa-player-poster__angle" aria-hidden="true" />
      <span className="sfa-player-poster__rank"><span className="sr-only">Puesto </span>{String(player.rank).padStart(2, '0')}</span>
      <TeamCrest key={player.team} url={flag ?? player.team_logo_url} name={player.team} />
      <span className="sfa-player-poster__position">{player.position}</span>
      <PlayerPortrait player={player} className="sfa-player-poster__portrait" />
      <strong className="sfa-player-poster__name">{player.name}</strong>
      <span className="sfa-player-poster__club">{player.team}</span>
    </div>
    <div className="sfa-player-poster__score">
      <span><span className="sfa-player-poster__monogram">SFA</span><small>Puntos</small></span>
      <strong>{Math.round(player.sfa_pts).toLocaleString('es-ES')}</strong>
    </div>
    <div className="sfa-player-poster__stats">
      <span><FootballIcon kind="goal" /><b>{player.goals}</b><small>Goles</small></span>
      <span><FootballIcon kind="assist" /><b>{player.assists}</b><small>Asist.</small></span>
      <span><FootballIcon kind="matches" /><b>{player.matches}</b><small>Partidos</small></span>
    </div>
    {(competitionName || player.b1_bonus_label) && <div className="sfa-player-poster__note">{competitionName && <span>{competitionName}</span>}{player.b1_bonus_label && <span>{player.b1_bonus_label}</span>}</div>}
  </Link>
}
