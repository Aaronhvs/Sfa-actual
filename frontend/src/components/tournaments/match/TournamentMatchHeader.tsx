import type { TournamentMatchFixture } from '../../../types'
import { formatLocalDateLong, formatLocalTime, localTimeZoneLabel } from '../../../utils/localTime'
import {
  isTournamentFinal,
  tournamentCompetitionLogoByName,
  tournamentStageLabel,
  tournamentStatusLabel,
} from '../../../utils/tournaments'

const teamLogo = (externalId: number | null) => externalId
  ? `https://media.api-sports.io/football/teams/${externalId}.png`
  : null

function Team({ name, externalId }: { name: string; externalId: number | null }) {
  const logo = teamLogo(externalId)
  return (
    <div className="trm-team">
      {logo
        ? <img src={logo} alt="" decoding="async" />
        : <span aria-hidden="true">{name.slice(0, 2).toUpperCase()}</span>}
      <strong>{name}</strong>
    </div>
  )
}

export default function TournamentMatchHeader({ fixture }: { fixture: TournamentMatchFixture }) {
  const competitionLogo = tournamentCompetitionLogoByName(fixture.competition_name)
  const activeLabels: Record<string, string> = {
    HT: 'Descanso',
    ET: 'Prórroga',
    BT: 'Pausa',
    P: 'Penaltis',
    INT: 'Interrumpido',
    SUSP: 'Suspendido',
  }
  const activeLabel = activeLabels[fixture.status]
  const status = fixture.is_live
    ? activeLabel ?? `${fixture.elapsed != null ? `${fixture.elapsed}' · ` : ''}En vivo`
    : isTournamentFinal(fixture.status)
      ? fixture.status_label
      : ['NS', 'TBD'].includes(fixture.status)
        ? `${formatLocalTime(fixture.played_at)} · ${localTimeZoneLabel()}`
        : fixture.status_label || tournamentStatusLabel(fixture.status)

  return (
    <header className={`trm-scoreboard${fixture.is_live ? ' trm-scoreboard--live' : ''}`}>
      <div className="trm-scoreboard__competition">
        {competitionLogo && <img src={competitionLogo} alt="" />}
        <div>
          <strong>{fixture.competition_name ?? 'Competición'}</strong>
          <span>{tournamentStageLabel(fixture.stage, fixture.matchday)}</span>
        </div>
        <time dateTime={fixture.played_at}>{formatLocalDateLong(fixture.played_at)}</time>
      </div>

      <div className="trm-scoreboard__match">
        <Team name={fixture.home_team.name} externalId={fixture.home_team.external_id} />
        <div className="trm-scoreboard__result">
          <strong>
            <b>{fixture.home_goals ?? '-'}</b>
            <span>:</span>
            <b>{fixture.away_goals ?? '-'}</b>
          </strong>
          <small className={fixture.is_live ? 'is-live' : ''}>{status}</small>
        </div>
        <Team name={fixture.away_team.name} externalId={fixture.away_team.external_id} />
      </div>
    </header>
  )
}
