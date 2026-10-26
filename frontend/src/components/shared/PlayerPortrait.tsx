import { useState } from 'react'
import type { RankedPlayer } from '../../types'

// Full-body artwork, keyed by SFA player id (not the image provider's id).
// Shown ONLY on the top-3 podium, the player's own profile and the comparator duel (pass `allowArtwork`);
// every other surface uses the provider photo.
const PLAYER_ARTWORK: Record<number, string> = {
  34: '/images/players/lamine-yamal-cutout-v2.png',
  7657: '/images/players/michael-olise-cutout.png',
  37427: '/images/players/florian-thauvin-cutout.png',
  35: '/images/players/raphinha-cutout.png',
  7568: '/images/players/vitinha-cutout.png',
  888: '/images/players/kylian-mbappe-cutout.png',
  7660: '/images/players/harry-kane-cutout.png',
  29: '/images/players/pau-cubarsi-cutout.png',
}

export default function PlayerPortrait({ player, className, eager = false, allowArtwork = false }: {
  player: Pick<RankedPlayer, 'id' | 'name' | 'photo_url'>
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
