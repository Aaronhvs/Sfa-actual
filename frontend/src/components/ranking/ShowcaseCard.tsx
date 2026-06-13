import { Link } from 'react-router-dom'
import { useCountUp } from '../../hooks/useCountUp'
import type { RankedPlayer, PlayerDetail } from '../../types'

interface Props {
  player: RankedPlayer
  detail: PlayerDetail | null
  isFirst?: boolean
}

function initials(name: string): string {
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

function formatPts(pts: number): string {
  return Math.round(pts).toLocaleString('es-ES')
}

function cardClass(rank: number): string {
  if (rank === 1) return 'player-showcase-card player-showcase-card--first'
  if (rank === 2) return 'player-showcase-card player-showcase-card--second'
  return 'player-showcase-card player-showcase-card--third'
}

export default function ShowcaseCard({ player }: Props) {
  const animatedRank = useCountUp(player.rank, 620)

  return (
    <Link
      to={`/player/${player.id}`}
      className={cardClass(player.rank)}
    >
      {player.photo_url ? (
        <img src={player.photo_url} alt={player.name} />
      ) : (
        <div className="psc-photo-placeholder">{initials(player.name)}</div>
      )}

      <div className="psc-rank-watermark" aria-label={`Posición ${player.rank}`}>
        {String(animatedRank).padStart(2, '0')}
      </div>

      <div className="psc-top-right">
        <div className="psc-tag">{player.position}</div>
        {player.team_logo_url && (
          <img
            className="psc-team-crest"
            src={player.team_logo_url}
            alt={player.team}
          />
        )}
      </div>

      <div className="psc-content">
        <div className="psc-name">{player.name}</div>
        <div className="psc-divider" />
        <div className="psc-stats">
          <div className="psc-stat-main">
            <div className="psc-stat-val">{formatPts(player.sfa_pts)}</div>
            <div className="psc-stat-lbl">PTS SFA</div>
          </div>
          <div className="psc-stats-secondary">
            <div className="psc-stat-side">
              <div className="psc-stat-side-val">{player.goals}</div>
              <div className="psc-stat-lbl">GOLES</div>
            </div>
            <div className="psc-stat-side">
              <div className="psc-stat-side-val">{player.assists}</div>
              <div className="psc-stat-lbl">ASIST.</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
