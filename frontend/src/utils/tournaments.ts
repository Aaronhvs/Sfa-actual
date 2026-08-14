import type { TournamentCompetition, TournamentTeam } from '../types'

export const FINAL_TOURNAMENT_STATUSES = new Set(['FT', 'AET', 'PEN'])
export const LIVE_TOURNAMENT_STATUSES = new Set(['LIVE', '1H', 'HT', '2H', 'ET', 'BT', 'P'])

export function tournamentSeasonLabel(season: string) {
  const start = Number(season)
  return Number.isFinite(start) ? `${start}/${start + 1}` : season
}

export function tournamentTeamLogo(team: TournamentTeam) {
  return team.external_id == null
    ? null
    : `https://media.api-sports.io/football/teams/${team.external_id}.png`
}

export function tournamentCompetitionLogo(competitionId: number) {
  return `https://media.api-sports.io/football/leagues/${competitionId}.png`
}

export function tournamentDateKey(value: string | Date) {
  const date = value instanceof Date ? value : new Date(value)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function tournamentDateLabel(value: string, long = true) {
  return new Intl.DateTimeFormat('es-ES', {
    weekday: long ? 'long' : undefined,
    day: '2-digit',
    month: long ? 'long' : 'short',
    year: long ? 'numeric' : undefined,
  }).format(new Date(`${value}T12:00:00`))
}

export function tournamentTimeLabel(value: string) {
  return new Intl.DateTimeFormat('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function tournamentStageLabel(stage: string, matchday: number | null) {
  if (matchday != null) return `Jornada ${matchday}`
  const normalized = stage.toLowerCase().replace(/_/g, ' ')
  const labels: Array<[string, string]> = [
    ['round of 16', 'Octavos de final'],
    ['round of 32', 'Dieciseisavos'],
    ['quarter', 'Cuartos de final'],
    ['semi', 'Semifinal'],
    ['final', 'Final'],
    ['league stage', 'Fase de liga'],
    ['group', 'Fase de grupos'],
  ]
  return labels.find(([key]) => normalized.includes(key))?.[1] ?? stage.replace(/_/g, ' ')
}

export function tournamentStatusLabel(status: string) {
  const labels: Record<string, string> = {
    NS: 'Programado',
    TBD: 'Por definir',
    PST: 'Aplazado',
    CANC: 'Cancelado',
    FT: 'Final',
    AET: 'Final prorroga',
    PEN: 'Final penaltis',
    LIVE: 'En juego',
    '1H': '1.er tiempo',
    HT: 'Descanso',
    '2H': '2.º tiempo',
    ET: 'Prorroga',
  }
  return labels[status] ?? status
}

export function isTournamentKnockout(stage: string) {
  const value = stage.toLowerCase().replace(/_/g, ' ')
  return [
    'round', 'octav', 'cuartos', 'quarter', 'semi', 'final', 'playoff',
    'play-off', 'knockout', '32', '16', '8th',
  ].some((token) => value.includes(token))
}

export function tournamentCompetitionPriority(competition: TournamentCompetition) {
  const name = competition.name.toLowerCase()
  const priorities: Array<[string, number]> = [
    ['champions league', 0],
    ['la liga', 10],
    ['premier league', 20],
    ['serie a', 30],
    ['bundesliga', 40],
    ['ligue 1', 50],
    ['europa league', 60],
    ['conference league', 70],
    ['copa libertadores', 80],
  ]
  return priorities.find(([key]) => name.includes(key))?.[1] ?? 500
}

export function sortTournamentCompetitions<T extends { competition: TournamentCompetition }>(items: T[]) {
  return [...items].sort((a, b) => (
    tournamentCompetitionPriority(a.competition)
    - tournamentCompetitionPriority(b.competition)
    || a.competition.name.localeCompare(b.competition.name)
  ))
}
