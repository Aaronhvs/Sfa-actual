import type { PlayerDetail } from '../../types'

const POSITION_LABELS: Record<string, string> = {
  DEL: 'Delantero',
  EXT: 'Extremo',
  MC: 'Centrocampista',
  DC: 'Defensa Central',
  LAT: 'Lateral',
  GK: 'Portero',
}

interface Props {
  player: PlayerDetail
}

function initials(name: string): string {
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

function formatPts(pts: number): string {
  return pts.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

export default function PlayerHeader({ player }: Props) {
  const posLabel = POSITION_LABELS[player.position] ?? player.position

  return (
    <div className="card player-header">
      <div className="player-header__photo-wrap">
        {player.photo_url ? (
          <img
            src={player.photo_url}
            alt={player.name}
            className="player-header__photo"
          />
        ) : (
          <div className="player-header__photo-placeholder">
            {initials(player.name)}
          </div>
        )}
      </div>

      <div>
        <div className="player-header__name-row">
          <h1 className="player-header__name">{player.name}</h1>
          <span className="player-rank-tag">#{player.global_rank}</span>
        </div>
        <div className="player-header__meta">
          <span className="pos-badge">{player.position}</span>
          <span>{player.team}</span>
          <span className="player-header__meta-sep">&middot;</span>
          <span>{player.competition}</span>
        </div>
        <div className="player-header__meta player-header__meta--sub">
          <span>{posLabel}</span>
          <span className="player-header__meta-sep">&middot;</span>
          <span>Temporada {player.season}</span>
        </div>

        <div className="sfa-badge">
          <span className="sfa-badge__num">{formatPts(player.sfa_pts)}</span>
          <span className="sfa-badge__label">SFA pts</span>
        </div>
      </div>
    </div>
  )
}
