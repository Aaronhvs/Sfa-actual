import { useIsTeamLive } from '../../hooks/useLiveTeams'
import './LiveDot.css'

/** Green dot shown while the team (identified by its crest URL) has a match in progress. */
export default function LiveDot({ logoUrl, className = '' }: { logoUrl: string | null | undefined; className?: string }) {
  if (!useIsTeamLive(logoUrl)) return null
  return <i className={`sfa-live-dot ${className}`.trim()} role="img" aria-label="Jugando ahora" title="Jugando ahora" />
}
