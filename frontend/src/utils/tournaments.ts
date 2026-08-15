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

const API_FOOTBALL_COMPETITION_IDS: Array<[string, number]> = [
  ['champions league', 2],
  ['premier league', 39],
  ['la liga', 140],
  ['serie a', 135],
  ['bundesliga', 78],
  ['ligue 1', 61],
  ['europa league', 3],
  ['conference league', 848],
  ['uefa super cup', 531],
  ['copa del rey', 143],
  ['supercopa de espana', 556],
  ['fa cup', 45],
  ['efl cup', 48],
  ['community shield', 528],
  ['dfb-pokal', 81],
  ['dfl-supercup', 529],
  ['coppa italia', 137],
  ['supercoppa italiana', 547],
  ['coupe de france', 66],
  ['trophee des champions', 526],
]

function normalizedCompetitionName(name: string) {
  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

export function tournamentCompetitionLogo(competition: TournamentCompetition) {
  const name = normalizedCompetitionName(competition.name)
  const apiFootballId = API_FOOTBALL_COMPETITION_IDS
    .find(([key]) => name.includes(key))?.[1]
  return apiFootballId == null
    ? undefined
    : `https://media.api-sports.io/football/leagues/${apiFootballId}.png`
}

export function usesMonochromeTournamentLogo(competition: TournamentCompetition) {
  const name = normalizedCompetitionName(competition.name)
  return name.includes('champions league')
    || name.includes('premier league')
    || name.includes('ligue 1')
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

export function isFeaturedTournamentCompetition(competition: TournamentCompetition) {
  return tournamentCompetitionPriority(competition) <= 50
}

export function sortTournamentCompetitions<T extends { competition: TournamentCompetition }>(items: T[]) {
  return [...items].sort((a, b) => (
    tournamentCompetitionPriority(a.competition)
    - tournamentCompetitionPriority(b.competition)
    || a.competition.name.localeCompare(b.competition.name)
  ))
}
