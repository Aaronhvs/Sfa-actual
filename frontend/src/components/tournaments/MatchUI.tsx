import { Link } from 'react-router-dom'
import type { TournamentCompetition, TournamentFixture, TournamentTeam } from '../../types'
import {
  FINAL_TOURNAMENT_STATUSES,
  LIVE_TOURNAMENT_STATUSES,
  tournamentCompetitionLogo,
  tournamentStatusLabel,
  tournamentTeamLogo,
  tournamentTimeLabel,
} from '../../utils/tournaments'
import './MatchUI.css'

export const isLive = (fixture: TournamentFixture) => LIVE_TOURNAMENT_STATUSES.has(fixture.status)
export const isFinal = (fixture: TournamentFixture) => FINAL_TOURNAMENT_STATUSES.has(fixture.status)
export const isUpcoming = (fixture: TournamentFixture) => !isLive(fixture) && !isFinal(fixture)

export function matchPath(fixture: TournamentFixture, season: string) {
  return `/torneos/partido/${fixture.external_id}?season=${season}`
}

export function liveLabel(status: string) {
  const short: Record<string, string> = { '1H': '1.er tiempo', '2H': '2.º tiempo', HT: 'Descanso', ET: 'Prórroga', P: 'Penaltis' }
  return short[status] ?? 'En juego'
}

export function Crest({ team, size = 'md' }: { team: TournamentTeam; size?: 'md' | 'xl' }) {
  const logo = tournamentTeamLogo(team)
  return logo
    ? <img className={`tp-crest tp-crest--${size}`} src={logo} alt="" loading="lazy" decoding="async" />
    : <span className={`tp-crest tp-crest--${size} tp-crest--fallback`} aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

export function CompetitionTile({ competition }: { competition: TournamentCompetition }) {
  const logo = tournamentCompetitionLogo(competition)
  return (
    <span className="tp-tile" aria-hidden="true">
      {logo ? <img src={logo} alt="" loading="lazy" /> : competition.name.slice(0, 2).toUpperCase()}
    </span>
  )
}

export function ArrowIcon({ direction = 'right' }: { direction?: 'left' | 'right' }) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" className={direction === 'left' ? 'is-flipped' : undefined}>
      <path d="M3 8h9.5M8.5 3.5 13 8l-4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function ScoreRow({ fixture, season, competition }: {
  fixture: TournamentFixture
  season: string
  /** Shown before the status when rows from several competitions share one list. */
  competition?: TournamentCompetition
}) {
  const live = isLive(fixture)
  const finished = isFinal(fixture)
  const home = fixture.home_goals ?? 0
  const away = fixture.away_goals ?? 0
  const homeLost = finished && home < away
  const awayLost = finished && away < home
  const postponed = !live && !finished && !['NS', 'TBD'].includes(fixture.status)

  return (
    <Link
      className={`tp-row${live ? ' is-live' : ''}${competition ? ' has-competition' : ''}`}
      to={matchPath(fixture, season)}
      aria-label={`${fixture.home_team.name} contra ${fixture.away_team.name}, ${live ? liveLabel(fixture.status) : tournamentStatusLabel(fixture.status)}`}
    >
      <span className="tp-row__status">
        {competition && <CompetitionTile competition={competition} />}
        {live && <b>{liveLabel(fixture.status)}</b>}
        {finished && tournamentStatusLabel(fixture.status)}
        {postponed && tournamentStatusLabel(fixture.status)}
      </span>
      <span className={`tp-row__team tp-row__team--home${homeLost ? ' is-dim' : ''}`}>
        <span>{fixture.home_team.name}</span>
        <Crest team={fixture.home_team} />
      </span>
      {live || finished ? (
        <span className="tp-row__score">{home}<i aria-hidden="true">–</i>{away}</span>
      ) : (
        <span className="tp-row__score tp-row__score--time">{tournamentTimeLabel(fixture.played_at)}</span>
      )}
      <span className={`tp-row__team${awayLost ? ' is-dim' : ''}`}>
        <Crest team={fixture.away_team} />
        <span>{fixture.away_team.name}</span>
      </span>
    </Link>
  )
}
