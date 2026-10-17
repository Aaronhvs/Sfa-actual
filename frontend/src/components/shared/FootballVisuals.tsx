import { useState } from 'react'
import { tournamentCompetitionLogoByName } from '../../utils/tournaments'
import './FootballVisuals.css'

export function FootballIcon({ kind }: { kind: 'goal' | 'assist' | 'matches' | 'rival' | 'moment' | 'competition' }) {
  return <svg className="sfa-football-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === 'goal' ? <><circle cx="12" cy="12" r="9" /><path d="m12 7 4.8 3.5-1.8 5.6H9l-1.8-5.6L12 7Zm0 0V3m4.8 7.5 3.8-1.3M15 16.1l2.4 3.2M9 16.1l-2.4 3.2m.6-8.8L3.4 9.2" /></>
      : kind === 'assist' ? <><path d="m6 3 6 2-1 5 3 3 6 2c1.4.5 2 1.5 2 3v2H3v-6l2-4 1-7Z" /><path d="m11 10-3 1m5 1-3 1m-7 4h19M6 20v2m5-2v2m5-2v2m5-2v2" /></>
        : kind === 'matches' ? <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4m10-4v4M3 10h18m-13 5h1m6 0h1m-8 3h1" /></>
          : kind === 'rival' ? <><path d="M4 4h16v7c0 5-4 8-8 10-4-2-8-5-8-10V4Z" /><path d="m8 12 3 3 5-6" /></>
            : kind === 'moment' ? <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>
              : <><path d="M8 3h8v5c0 4-2 6-4 6S8 12 8 8V3Zm0 2H4v3c0 3 2 4 5 4m7-7h4v3c0 3-2 4-5 4m-3 2v5m-4 2h8m-6-2h4" /></>}
  </svg>
}

export function TeamCrest({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  return <span className="sfa-team-crest" title={name}>
    {url && !failed ? <img src={url} alt={name} loading="lazy" decoding="async" onError={() => setFailed(true)} />
      : <span role="img" aria-label={name}>{name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>}
  </span>
}

export function CompetitionCrest({ name }: { name: string }) {
  const [failed, setFailed] = useState(false)
  const url = tournamentCompetitionLogoByName(name)
  const needsDarkSurface = name.toLowerCase().includes('ligue 1')
  return <span className={`sfa-competition-crest${needsDarkSurface ? ' sfa-competition-crest--dark' : ''}`} title={name}>
    {url && !failed ? <img src={url} alt={name} loading="lazy" decoding="async" onError={() => setFailed(true)} />
      : <span role="img" aria-label={name || 'Competición'}><FootballIcon kind="competition" /></span>}
  </span>
}
