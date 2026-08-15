import { useMemo } from 'react'
import type { TournamentFixture, TournamentTeam } from '../../types'
import { FINAL_TOURNAMENT_STATUSES, tournamentTeamLogo } from '../../utils/tournaments'

type KnockoutStage = 'round16' | 'quarter' | 'semi' | 'final'

interface KnockoutTie {
  key: string
  stage: KnockoutStage
  teamA: TournamentTeam
  teamB: TournamentTeam
  scoreA: number
  scoreB: number
  hasScore: boolean
  fixtures: TournamentFixture[]
  winnerId: number | null
  firstPlayedAt: number
}

function knockoutStage(stage: string): KnockoutStage | null {
  const value = stage.toLowerCase().replace(/_/g, ' ')
  if (value.includes('round of 16') || value.includes('last 16') || value.includes('octav')) return 'round16'
  if (value.includes('quarter') || value.includes('cuarto')) return 'quarter'
  if (value.includes('semi')) return 'semi'
  if (value.includes('final') && !value.includes('third') && !value.includes('3rd')) return 'final'
  return null
}

function buildTies(fixtures: TournamentFixture[]) {
  const groups = new Map<string, { stage: KnockoutStage; fixtures: TournamentFixture[] }>()
  fixtures.forEach((fixture) => {
    const stage = knockoutStage(fixture.stage)
    if (!stage) return
    const pair = [fixture.home_team.id, fixture.away_team.id].sort((a, b) => a - b)
    const key = `${stage}-${pair[0]}-${pair[1]}`
    const current = groups.get(key)
    if (current) current.fixtures.push(fixture)
    else groups.set(key, { stage, fixtures: [fixture] })
  })

  return [...groups.entries()].map(([key, group]): KnockoutTie => {
    const ordered = [...group.fixtures].sort((a, b) => (
      new Date(a.played_at).getTime() - new Date(b.played_at).getTime()
    ))
    const teamA = ordered[0].home_team
    const teamB = ordered[0].away_team
    let scoreA = 0
    let scoreB = 0
    let hasScore = false
    ordered.forEach((fixture) => {
      if (fixture.home_goals == null || fixture.away_goals == null) return
      hasScore = true
      if (fixture.home_team.id === teamA.id) {
        scoreA += fixture.home_goals
        scoreB += fixture.away_goals
      } else {
        scoreA += fixture.away_goals
        scoreB += fixture.home_goals
      }
    })
    const complete = ordered.every((fixture) => FINAL_TOURNAMENT_STATUSES.has(fixture.status))
    const winnerId = complete && scoreA !== scoreB
      ? (scoreA > scoreB ? teamA.id : teamB.id)
      : null
    return {
      key,
      stage: group.stage,
      teamA,
      teamB,
      scoreA,
      scoreB,
      hasScore,
      fixtures: ordered,
      winnerId,
      firstPlayedAt: new Date(ordered[0].played_at).getTime(),
    }
  })
}

function tieContains(tie: KnockoutTie, teamId: number) {
  return tie.teamA.id === teamId || tie.teamB.id === teamId
}

function markAdvancedTeams(previous: KnockoutTie[], next: KnockoutTie[]) {
  const nextTeamIds = new Set(next.flatMap((tie) => [tie.teamA.id, tie.teamB.id]))
  previous.forEach((tie) => {
    const advanced = [tie.teamA.id, tie.teamB.id].filter((id) => nextTeamIds.has(id))
    if (advanced.length === 1) tie.winnerId = advanced[0]
  })
}

function orderPreviousRound(previous: KnockoutTie[], next: KnockoutTie[], size: number) {
  const ordered: KnockoutTie[] = []
  const used = new Set<string>()
  next.forEach((nextTie) => {
    ;[nextTie.teamA.id, nextTie.teamB.id].forEach((teamId) => {
      const match = previous.find((tie) => (
        !used.has(tie.key)
        && (tie.winnerId === teamId || tieContains(tie, teamId))
      ))
      if (match) {
        ordered.push(match)
        used.add(match.key)
      }
    })
  })
  previous
    .filter((tie) => !used.has(tie.key))
    .sort((a, b) => a.firstPlayedAt - b.firstPlayedAt)
    .forEach((tie) => ordered.push(tie))
  return Array.from({ length: size }, (_, index) => ordered[index] ?? null)
}

function TeamLine({ team, score, winner }: {
  team: TournamentTeam
  score: number | null
  winner: boolean
}) {
  const logo = tournamentTeamLogo(team)
  return (
    <span className={`trn-ko-team${winner ? ' is-winner' : ''}`}>
      {logo ? <img src={logo} alt="" loading="lazy" /> : <i>{team.name.slice(0, 2).toUpperCase()}</i>}
      <b title={team.name}>{team.name}</b>
      <strong>{score ?? '-'}</strong>
    </span>
  )
}

function TieNode({ tie, fallback }: { tie: KnockoutTie | null; fallback: string }) {
  if (!tie) {
    return (
      <article className="trn-ko-node is-pending">
        <span>Por definir</span>
        <small>{fallback}</small>
      </article>
    )
  }
  const aggregate = tie.fixtures.length > 1
  return (
    <article className={`trn-ko-node${tie.winnerId ? ' is-decided' : ''}`}>
      <TeamLine team={tie.teamA} score={tie.hasScore ? tie.scoreA : null} winner={tie.winnerId === tie.teamA.id} />
      <TeamLine team={tie.teamB} score={tie.hasScore ? tie.scoreB : null} winner={tie.winnerId === tie.teamB.id} />
      <small>{aggregate ? 'Marcador global' : fallback}</small>
    </article>
  )
}

function TrophyMark() {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path d="M19 8h26v11c0 10-5 17-13 19-8-2-13-9-13-19V8Z" fill="none" stroke="currentColor" strokeWidth="4" />
      <path d="M20 14H9v5c0 7 5 12 12 12M44 14h11v5c0 7-5 12-12 12" fill="none" stroke="currentColor" strokeWidth="4" />
      <path d="M32 38v10M22 56h20M26 48h12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}

export default function TournamentKnockoutBracket({ fixtures, champion }: {
  fixtures: TournamentFixture[]
  champion: TournamentTeam | null
}) {
  const bracket = useMemo(() => {
    const ties = buildTies(fixtures)
    const round16 = ties.filter((tie) => tie.stage === 'round16')
    const quarters = ties.filter((tie) => tie.stage === 'quarter')
    const semis = ties.filter((tie) => tie.stage === 'semi')
    const final = ties.find((tie) => tie.stage === 'final') ?? null

    if (final && champion && tieContains(final, champion.id)) final.winnerId = champion.id
    markAdvancedTeams(semis, final ? [final] : [])
    markAdvancedTeams(quarters, semis)
    markAdvancedTeams(round16, quarters)

    const orderedSemis = orderPreviousRound(semis, final ? [final] : [], 2)
    const orderedQuarters = orderPreviousRound(quarters, orderedSemis.filter(Boolean) as KnockoutTie[], 4)
    const orderedRound16 = orderPreviousRound(round16, orderedQuarters.filter(Boolean) as KnockoutTie[], 8)
    let winnerFromFinal: TournamentTeam | null = null
    if (final) {
      if (final.winnerId === final.teamA.id) winnerFromFinal = final.teamA
      else if (final.winnerId === final.teamB.id) winnerFromFinal = final.teamB
    }
    const resolvedChampion = champion ?? winnerFromFinal
    return { round16: orderedRound16, quarters: orderedQuarters, semis: orderedSemis, final, champion: resolvedChampion }
  }, [champion, fixtures])

  if (!bracket.final && bracket.semis.every((tie) => tie == null) && bracket.quarters.every((tie) => tie == null) && bracket.round16.every((tie) => tie == null)) {
    return <div className="trn-state trn-state--inline">Los cruces apareceran cuando se definan las fases eliminatorias.</div>
  }

  const championLogo = bracket.champion ? tournamentTeamLogo(bracket.champion) : null
  return (
    <section className="trn-ko-shell" aria-label="Cuadro eliminatorio del torneo">
      <div className="trn-ko-scroll">
        <div className="trn-ko-board">
          <svg className="trn-ko-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <path d="M12 12.5H14V25H15M12 37.5H14V25M12 62.5H14V75H15M12 87.5H14V75" />
            <path d="M27 25H29V50H30M27 75H29V50M42 50H44" />
            <path d="M88 12.5H86V25H85M88 37.5H86V25M88 62.5H86V75H85M88 87.5H86V75" />
            <path d="M73 25H71V50H70M73 75H71V50M58 50H56" />
          </svg>

          <div className="trn-ko-column trn-ko-column--four">
            {bracket.round16.slice(0, 4).map((tie, index) => <TieNode tie={tie} fallback="Octavos" key={`lr16-${index}`} />)}
          </div>
          <div className="trn-ko-column trn-ko-column--two">
            {bracket.quarters.slice(0, 2).map((tie, index) => <TieNode tie={tie} fallback="Cuartos" key={`lq-${index}`} />)}
          </div>
          <div className="trn-ko-column trn-ko-column--one">
            <TieNode tie={bracket.semis[0]} fallback="Semifinal" />
          </div>

          <div className="trn-ko-center">
            <div className="trn-ko-champion">
              <span className="trn-ko-trophy"><TrophyMark /></span>
              {championLogo && <img src={championLogo} alt="" />}
              <strong title={bracket.champion?.name}>{bracket.champion?.name ?? 'Campeon por definir'}</strong>
              <small>Campeon</small>
            </div>
            <TieNode tie={bracket.final} fallback="Final" />
          </div>

          <div className="trn-ko-column trn-ko-column--one">
            <TieNode tie={bracket.semis[1]} fallback="Semifinal" />
          </div>
          <div className="trn-ko-column trn-ko-column--two">
            {bracket.quarters.slice(2, 4).map((tie, index) => <TieNode tie={tie} fallback="Cuartos" key={`rq-${index}`} />)}
          </div>
          <div className="trn-ko-column trn-ko-column--four">
            {bracket.round16.slice(4, 8).map((tie, index) => <TieNode tie={tie} fallback="Octavos" key={`rr16-${index}`} />)}
          </div>
        </div>
      </div>
      <p className="trn-ko-hint">Desliza horizontalmente para recorrer el cuadro completo.</p>
    </section>
  )
}
