import { Link } from 'react-router-dom'
import { useCountUp } from '../../hooks/useCountUp'
import type { RankedPlayer } from '../../types'
import { worldCupTeamFlagUrl } from '../../utils/worldCupTeams'

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
  return name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
}

export default function RankingCard({
  player,
  index = 0,
  competitionName,
  season,
  isWorldCup = false,
}: Props) {
  const animatedRank = useCountUp(player.rank, 620)
  const playerLink = `/player/${player.id}${season ? `?season=${season}` : ''}`
  const displayedRank = String(isWorldCup ? player.rank : animatedRank).padStart(2, '0')
  const flagUrl = isWorldCup ? worldCupTeamFlagUrl(player.team) : null

  return (
    <Link
      to={playerLink}
      className={`ranking-card${isWorldCup ? ' ranking-card--wc' : ''}`}
      style={{ animationDelay: `${index * 45}ms` }}
    >
      <div className="rc-mobile-row">
        <span className="rc-mobile-row__rank">{displayedRank}</span>
        <div className="rc-mobile-row__photo">
          {player.photo_url ? (
            <img src={player.photo_url} alt="" loading="lazy" decoding="async" />
          ) : (
            <span>{initials(player.name)}</span>
          )}
        </div>
        <div className="rc-mobile-row__identity">
          <strong>{player.name}</strong>
          <span>
            {flagUrl ? (
              <img src={flagUrl} alt={player.team} className="rc-mobile-row__flag" />
            ) : (
              player.team
            )}
            {!isWorldCup && competitionName ? ` · ${competitionName}` : ''}
          </span>
        </div>
        <div className="rc-mobile-row__score">
          <strong>{formatPts(player.sfa_pts)}</strong>
          <span>PTS</span>
          <div
            className="rc-mobile-row__ga"
            aria-label={`${player.goals} goles y ${player.assists} asistencias`}
          >
            <b>{player.goals}<i>G</i></b>
            <b>{player.assists}<i>A</i></b>
          </div>
        </div>
      </div>

      {player.photo_url ? (
        <img
          src={player.photo_url}
          alt=""
          className="rc-photo"
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className="rc-photo-placeholder">{initials(player.name)}</div>
      )}

      <div className="rc-rank-wm" aria-hidden="true">
        {displayedRank}
      </div>

      <div className="rc-top-meta">
        <span className="rc-pos-badge">{player.position}</span>
        {player.team_logo_url && (
          <img
            src={player.team_logo_url}
            alt=""
            className="rc-team-logo"
            loading="lazy"
            decoding="async"
            aria-hidden="true"
          />
        )}
      </div>

      <div className="rc-content">
        <div className="rc-name-row">
          <div className="rc-name">{player.name}</div>
        </div>
        <div className="rc-divider" />
        <div className="rc-stats">
          <div className="rc-stat-main">
            <div className="rc-stat-pts">{formatPts(player.sfa_pts)}</div>
            <div className="rc-stat-lbl">PTS SFA</div>
          </div>
          <div className="rc-stats-secondary">
            <div className="rc-stat-compact">
              <div className="rc-stat-side-val">{player.goals}</div>
              <div className="rc-stat-lbl">G</div>
            </div>
            <div className="rc-stat-compact">
              <div className="rc-stat-side-val">{player.assists}</div>
              <div className="rc-stat-lbl">A</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
