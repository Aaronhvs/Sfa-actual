import { Link } from 'react-router-dom'
import { useCountUp } from '../../hooks/useCountUp'
import type { RankedPlayer, PlayerDetail } from '../../types'
import { worldCupTeamFlagUrl } from '../../utils/worldCupTeams'

interface Props {
  player: RankedPlayer
  detail: PlayerDetail | null
  isFirst?: boolean
  podiumPlace?: number
  season?: string
  isWorldCup?: boolean
}

function initials(name: string): string {
  return name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
}

function formatPts(pts: number): string {
  return Math.round(pts).toLocaleString('es-ES')
}

function compactName(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (name.length <= 16 || parts.length === 1) return name

  const lastName = parts[parts.length - 1]
  const initials = parts.slice(0, -1).map((part) => `${part[0]}.`).join(' ')
  const compact = `${initials} ${lastName}`

  if (compact.length <= 18) return compact
  return lastName.length <= 18 ? lastName : `${lastName.slice(0, 16)}…`
}

function B1Badge({ player }: { player: RankedPlayer }) {
  if (!player.b1_bonus_label) return null

  const tone = player.b1_bonus_label === 'Veterano' ? 'veteran' : 'prospect'
  return (
    <span className={`b1-player-badge b1-player-badge--${tone}`}>
      <b>{player.b1_bonus_label}</b>
    </span>
  )
}

function cardClass(place: number, isWorldCup: boolean): string {
  const tournamentClass = isWorldCup ? ' player-showcase-card--wc' : ''
  if (place === 1) return `player-showcase-card player-showcase-card--first${tournamentClass}`
  if (place === 2) return `player-showcase-card player-showcase-card--second${tournamentClass}`
  return `player-showcase-card player-showcase-card--third${tournamentClass}`
}

export default function ShowcaseCard({ player, podiumPlace, season, isWorldCup = false }: Props) {
  const playerLink = `/player/${player.id}${season ? `?season=${season}` : ''}`
  const displayPlace = podiumPlace ?? player.rank
  const animatedDisplayPlace = useCountUp(displayPlace, 620)
  const displayedRank = String(isWorldCup ? displayPlace : animatedDisplayPlace).padStart(2, '0')
  const flagUrl = isWorldCup ? worldCupTeamFlagUrl(player.team) : null
  const mobileName = compactName(player.name)

  return (
    <Link to={playerLink} className={cardClass(displayPlace, isWorldCup)}>
      <div className="psc-mobile-podium">
        <div className="psc-mobile-podium__portrait">
          {player.photo_url ? (
            <img
              src={player.photo_url}
              alt=""
              loading={player.rank === 1 ? 'eager' : 'lazy'}
              decoding="async"
            />
          ) : (
            <span>{initials(player.name)}</span>
          )}
          <b>{displayedRank}</b>
        </div>
        <div className="psc-mobile-podium__bar">
          {flagUrl && <img src={flagUrl} alt={player.team} className="psc-mobile-podium__flag" />}
          <strong title={player.name} aria-label={player.name}>{mobileName}</strong>
          <B1Badge player={player} />
          <span>{formatPts(player.sfa_pts)} pts</span>
          <div
            className="psc-mobile-podium__ga"
            aria-label={`${player.goals} goles y ${player.assists} asistencias`}
          >
            <b>{player.goals + player.assists}<i>G+A</i></b>
          </div>
        </div>
      </div>

      {player.photo_url ? (
        <img
          src={player.photo_url}
          alt={player.name}
          loading={player.rank === 1 ? 'eager' : 'lazy'}
          decoding="async"
        />
      ) : (
        <div className="psc-photo-placeholder">{initials(player.name)}</div>
      )}

      <div className="psc-rank-watermark" aria-label={`Posición ${player.rank}`}>
        {displayedRank}
      </div>

      <div className="psc-top-right">
        <div className="psc-tag">{player.position}</div>
        {player.team_logo_url && (
          <img
            className="psc-team-crest"
            src={player.team_logo_url}
            alt={player.team}
            loading="lazy"
            decoding="async"
          />
        )}
      </div>

      <div className="psc-content">
        <div className="psc-name">{player.name}</div>
        <B1Badge player={player} />
        <div className="psc-divider" />
        <div className="psc-stats">
          <div className="psc-stat-main">
            <div className="psc-stat-val">{formatPts(player.sfa_pts)}</div>
            <div className="psc-stat-lbl">PTS SFA</div>
          </div>
          <div className="psc-stats-secondary psc-stats-secondary--ga">
            <div className="psc-stat-compact">
              <div className="psc-stat-side-val">{player.goals}</div>
              <div className="psc-stat-lbl">G</div>
            </div>
            <div className="psc-stat-compact">
              <div className="psc-stat-side-val">{player.assists}</div>
              <div className="psc-stat-lbl">A</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
