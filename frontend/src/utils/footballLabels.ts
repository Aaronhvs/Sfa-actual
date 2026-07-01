const COMPETITION_LABELS: Record<string, string> = {
  'fifa world cup': 'Mundial',
  'world cup': 'Mundial',
}

const STAGE_LABELS: Record<string, string> = {
  group: 'Fase de grupos',
  'group stage': 'Fase de grupos',
  regular: 'Liga',
  'regular season': 'Liga',
  final: 'Final',
  '3rd place': 'Tercer puesto',
  'third place': 'Tercer puesto',
  third_place: 'Tercer puesto',
  'round of 32': 'Dieciseisavos',
  round_of_32: 'Dieciseisavos',
  'last 32': 'Dieciseisavos',
  'round of 16': 'Octavos de final',
  round_of_16: 'Octavos de final',
  'last 16': 'Octavos de final',
  'quarter final': 'Cuartos de final',
  'quarter finals': 'Cuartos de final',
  'quarter-finals': 'Cuartos de final',
  quarter_final: 'Cuartos de final',
  quarterfinals: 'Cuartos de final',
  'semi final': 'Semifinal',
  'semi finals': 'Semifinales',
  'semi-finals': 'Semifinales',
  semi_final: 'Semifinal',
  semifinals: 'Semifinales',
  winner: 'Campeón',
  champion: 'Campeón',
  runner_up: 'Subcampeón',
}

const PHASE_BADGES: Record<string, string> = {
  runner_up: '2',
  final: 'F',
  semi_final: '4',
  semifinal: '4',
  quarter_final: '8',
  'quarter-finals': '8',
  round_of_16: '8',
  'round of 16': '8',
  round_of_32: '16',
  'round of 32': '16',
  group_stage: 'FG',
  'group stage': 'FG',
}

function normalize(value: string): string {
  return value.trim().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').toLowerCase()
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function competitionLabel(value: string | null | undefined): string {
  if (!value) return ''
  return COMPETITION_LABELS[normalize(value)] ?? value
}

export function stageLabel(value: string | null | undefined): string {
  if (!value) return ''
  const key = normalize(value)
  const groupMatch = key.match(/^group ([a-z0-9]+)$/)
  if (groupMatch) return `Grupo ${groupMatch[1].toUpperCase()}`
  const matchday = key.match(/^matchday (\d+)$/)
  if (matchday) return `Fecha ${matchday[1]}`
  return STAGE_LABELS[key] ?? titleCase(value)
}

export function phaseLabel(value: string | null | undefined): string {
  if (!value) return ''
  return stageLabel(value)
}

export function phaseBadge(value: string | null | undefined): string {
  if (!value) return ''
  const key = normalize(value)
  return PHASE_BADGES[key] ?? phaseLabel(value).slice(0, 2)
}
