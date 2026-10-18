import type { RankingPlayerExplanation } from '../../types'

const LABELS: Record<string, string> = { stats: 'Rendimiento del partido', goal: 'Goles', assist: 'Asistencias', goal_penalty: 'Penaltis', penalty: 'Penaltis', own_goal: 'Autogoles' }
const ACTIONS: Record<string, string> = { goal: 'Gol', assist: 'Asistencia', goal_penalty: 'Gol de penalti', penalty: 'Gol de penalti' }
const STAGES: Record<string, string> = { regular: 'Liga regular', group: 'Fase de grupos', final: 'Final', semi_final: 'Semifinal', quarter_final: 'Cuartos de final', round_of_16: 'Octavos de final' }
function record(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }
function records(value: unknown) { return Array.isArray(value) ? value.map(record) : [] }
function text(value: unknown) { return typeof value === 'string' ? value : '' }
function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) }
export function formatSfaPoints(value: number, decimals = 0) { return value.toLocaleString('es-ES', { maximumFractionDigits: decimals }) }

export function rankingEvidence(explanation: RankingPlayerExplanation) {
  const evidence = explanation.evidence ?? {}
  const player = record(evidence.player)
  const total = finite(player.total_pts) ? player.total_pts : 0
  const breakdown = Object.entries(record(evidence.breakdown)).flatMap(([key, value]) => {
    const row = record(value)
    return finite(row.pts) && row.pts !== 0 ? [{ label: LABELS[key] ?? 'Otras acciones', points: row.pts }] : []
  }).sort((a, b) => b.points - a.points)
  for (const [key, label] of [['b1_bonus_pts', 'Bonificación de perfil'], ['achievement_bonus_pts', 'Logros del equipo'], ['individual_honor_bonus_pts', 'Reconocimientos individuales']]) {
    const points = player[key]
    if (finite(points) && points !== 0) breakdown.push({ label, points })
  }
  breakdown.sort((a, b) => b.points - a.points)
  const unexplained = total - breakdown.reduce((sum, row) => sum + row.points, 0)
  // Individual actions only: aggregate stats are not minute-by-minute events.
  const actions = records(evidence.match_summaries).flatMap(match => records(match.impact_minutes).flatMap(action => {
    const label = ACTIONS[text(action.type)]
    const home = text(match.home_team), away = text(match.away_team)
    return label && home && away && finite(action.points) ? [{ label, points: action.points, match: `${home} – ${away}`,
      minute: finite(action.minute) ? action.minute : null, score: text(action.score_before),
      stage: STAGES[text(match.stage)] ?? text(match.stage_label),
    }] : []
  })).sort((a, b) => b.points - a.points)
  const featured = actions[0] ?? null
  const largest = breakdown[0]
  const summary = largest && total > 0 ? `${largest.label}: ${formatSfaPoints(largest.points)} puntos, el ${Math.round(largest.points / total * 100)} % del total.` : 'El desglose contextual no está disponible para este periodo.'
  return { total, breakdown, featured, summary, unexplained }
}
