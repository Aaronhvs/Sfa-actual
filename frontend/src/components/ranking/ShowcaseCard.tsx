import { Link } from 'react-router-dom'
import { useCountUp } from '../../hooks/useCountUp'
import type { RankedPlayer, PlayerDetail } from '../../types'

interface Props {
  player: RankedPlayer
  detail: PlayerDetail | null
  isFirst?: boolean
  season?: string
  isWorldCup?: boolean
}

function initials(name: string): string {
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

function formatPts(pts: number): string {
  return Math.round(pts).toLocaleString('es-ES')
}

function cardClass(rank: number, isWorldCup: boolean): string {
  const tournamentClass = isWorldCup ? ' player-showcase-card--wc' : ''
  if (rank === 1) return `player-showcase-card player-showcase-card--first${tournamentClass}`
  if (rank === 2) return `player-showcase-card player-showcase-card--second${tournamentClass}`
  return `player-showcase-card player-showcase-card--third${tournamentClass}`
}

export default function ShowcaseCard({ player, season, isWorldCup = false }: Props) {
  const animatedRank = useCountUp(player.rank, 620)
  const playerLink = `/player/${player.id}${season ? `?season=${season}` : ''}`

  return (
    <Link
      to={playerLink}
      className={cardClass(player.rank, isWorldCup)}
    >
      {player.photo_url ? (
        <img src={player.photo_url} alt={player.name} />
      ) : (
        <div className="psc-photo-placeholder">{initials(player.name)}</div>
      )}

      <div className="psc-rank-watermark" aria-label={`Posición ${player.rank}`}>
        {String(isWorldCup ? player.rank : animatedRank).padStart(2, '0')}
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
        {isWorldCup && (
          <div className="psc-national-team">{player.team}</div>
        )}
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
