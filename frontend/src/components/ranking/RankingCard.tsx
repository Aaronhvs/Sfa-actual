import { Link } from 'react-router-dom'
import { useCountUp } from '../../hooks/useCountUp'
import type { RankedPlayer } from '../../types'

interface Props {
  player: RankedPlayer
  index?: number
  competitionName?: string
  season?: string
  isWorldCup?: boolean
}

function formatPts(pts: number): string {
  return Math.round(pts).toLocaleString('es-ES')
}

function initials(name: string): string {
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

export default function RankingCard({ player, index = 0, season, isWorldCup = false }: Props) {
  const goalContributions = player.goals + player.assists
  const animatedRank = useCountUp(player.rank, 620)
  const playerLink = `/player/${player.id}${season ? `?season=${season}` : ''}`

  return (
    <Link
      to={playerLink}
      className={`ranking-card${isWorldCup ? ' ranking-card--wc' : ''}`}
      style={{ animationDelay: `${index * 45}ms` }}
    >
      {player.photo_url ? (
        <img src={player.photo_url} alt="" className="rc-photo" />
      ) : (
        <div className="rc-photo-placeholder">{initials(player.name)}</div>
      )}

      <div className="rc-rank-wm" aria-hidden="true">
        {String(isWorldCup ? player.rank : animatedRank).padStart(2, '0')}
      </div>

      <div className="rc-top-meta">
        <span className="rc-pos-badge">{player.position}</span>
        {player.team_logo_url && (
          <img src={player.team_logo_url} alt="" className="rc-team-logo" aria-hidden="true" />
        )}
      </div>

      <div className="rc-content">
        <div className="rc-name-row">
          <div className="rc-name">{player.name}</div>
        </div>
        {isWorldCup && (
          <div className="rc-national-team">{player.team}</div>
        )}
        <div className="rc-divider" />
        <div className="rc-stats">
          <div className="rc-stat-main">
            <div className="rc-stat-pts">{formatPts(player.sfa_pts)}</div>
            <div className="rc-stat-lbl">PTS SFA</div>
          </div>
          <div className="rc-stats-secondary">
            <div>
              <div className="rc-stat-side-val">{player.matches}</div>
              <div className="rc-stat-lbl">PJ</div>
            </div>
            <div>
              <div className="rc-stat-side-val">{goalContributions}</div>
              <div className="rc-stat-lbl">G + A</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
