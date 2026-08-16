import { Link } from 'react-router-dom'
import type { TournamentFixture, TournamentTeam } from '../../types'
import {
  FINAL_TOURNAMENT_STATUSES,
  LIVE_TOURNAMENT_STATUSES,
  tournamentStageLabel,
  tournamentStatusLabel,
  tournamentTeamLogo,
  tournamentTimeLabel,
} from '../../utils/tournaments'

function TeamMark({ team }: { team: TournamentTeam }) {
  const logo = tournamentTeamLogo(team)
  return logo
    ? <img src={logo} alt="" loading="lazy" decoding="async" />
    : <span aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

export default function TournamentFixtureRow({ fixture }: { fixture: TournamentFixture }) {
  const finished = FINAL_TOURNAMENT_STATUSES.has(fixture.status)
  const live = LIVE_TOURNAMENT_STATUSES.has(fixture.status)
  return (
    <Link
      className={`trn-match trn-match--link${live ? ' trn-match--live' : ''}`}
      to={`/torneos/partido/${fixture.external_id}?season=2026`}
      aria-label={`${fixture.home_team.name} vs ${fixture.away_team.name}`}
    >
      <div className="trn-match__time">
        <strong>{finished ? tournamentStatusLabel(fixture.status) : tournamentTimeLabel(fixture.played_at)}</strong>
        <span>{tournamentStageLabel(fixture.stage, fixture.matchday)}</span>
      </div>
      <div className="trn-match__teams">
        <div><TeamMark team={fixture.home_team} /><span>{fixture.home_team.name}</span></div>
        <div><TeamMark team={fixture.away_team} /><span>{fixture.away_team.name}</span></div>
      </div>
      <div className="trn-match__score" aria-label={tournamentStatusLabel(fixture.status)}>
        <strong>{fixture.home_goals ?? '-'}</strong>
        <strong>{fixture.away_goals ?? '-'}</strong>
      </div>
      {live && <span className="trn-match__live">En vivo</span>}
    </Link>
  )
}
