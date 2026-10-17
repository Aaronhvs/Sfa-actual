import { useState } from 'react'
import type { RankedPlayer } from '../../types'

// SFA player IDs, independent of the image provider's IDs.
const PLAYER_ARTWORK: Record<number, string> = {
  34: '/images/players/lamine-yamal-cutout-v2.png',
  7657: '/images/players/michael-olise-cutout.png',
  37427: '/images/players/florian-thauvin-cutout.png',
}

export default function PlayerPortrait({ player, className, eager = false, allowArtwork = false }: {
  player: RankedPlayer
  className: string
  eager?: boolean
  allowArtwork?: boolean
}) {
  const [failedUrls, setFailedUrls] = useState<string[]>([])
  const artwork = allowArtwork ? PLAYER_ARTWORK[player.id] : undefined
  const source = [artwork, player.photo_url].find((url) => url && !failedUrls.includes(url))
  const isArtwork = Boolean(artwork && source === artwork)

  return <span className={`${className}${isArtwork ? ` ${className}--artwork` : ''}`}>
    {source ? <img src={source} alt="" loading={eager ? 'eager' : 'lazy'} decoding="async"
      onError={() => setFailedUrls((previous) => [...previous, source])} />
      : <span aria-hidden="true">{player.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>}
  </span>
}
