import { useEffect, useState } from 'react'
import { fetchPlayerLeads } from '../../api/client'
import type { PlayerLead } from '../../types'
import { competitionLabel } from '../../utils/footballLabels'
import { tournamentCompetitionLogoByName } from '../../utils/tournaments'

/* ── "Lidera en": stats where the player is on the podium, computed by the backend (spec 0067) ── */

const POSITION_PLURAL: Record<string, string> = {
  GK: 'porteros', DC: 'centrales', LAT: 'laterales', MC: 'centrocampistas', MCO: 'mediapuntas', EXT: 'extremos', DEL: 'delanteros',
}

const int = (value: number) => Math.round(value).toLocaleString('es-ES')
const dec = (value: number) => value.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 })
const pct = (value: number) => `${Math.round(value * 100)} %`

type Copy = { title: string; figure: string; unit?: string; context: string }

/** Plain-language copy per metric. Figures stay honest: the raw numbers behind every rate are shown. */
function copyFor(lead: PlayerLead): Copy {
  const d = lead.details
  switch (lead.metric) {
    case 'shot_conversion': {
      const penalties = d.penalty_goals_excluded ?? 0
      return {
        title: 'El más eficaz de cara a puerta',
        figure: pct(lead.value),
        context: `${int(lead.numerator)} goles en ${int(lead.denominator)} tiros a puerta${penalties ? `, sin contar ${penalties} de penal` : ''}`,
      }
    }
    case 'goals_per90':
      return { title: 'Más goles por partido', figure: dec(lead.value), unit: 'por 90′', context: `${int(d.goals)} goles en ${int(d.minutes)} minutos` }
    case 'goal_contributions_per90':
      return { title: 'Más goles y asistencias', figure: dec(lead.value), unit: 'por 90′', context: `${int(d.goals)} goles y ${int(d.assists)} asistencias` }
    case 'key_passes_per90':
      return { title: 'Más pases clave', figure: dec(lead.value), unit: 'por 90′', context: `${int(d.key_passes)} pases que acabaron en tiro` }
    case 'dribbles_per90':
      return { title: 'Más regates completados', figure: dec(lead.value), unit: 'por 90′', context: `${int(d.dribbles_won)} de ${int(d.dribbles_attempts)} regates (${pct(d.success_rate ?? 0)} de acierto)` }
    case 'defensive_actions_per90':
      return { title: 'Más entradas e intercepciones', figure: dec(lead.value), unit: 'por 90′', context: `${int(d.tackles)} entradas y ${int(d.interceptions)} intercepciones` }
    case 'duel_win_rate':
      return { title: 'Gana más duelos', figure: pct(lead.value), context: `${int(d.duels_won)} de ${int(d.duels_total)} duelos ganados` }
    case 'save_rate':
      return { title: 'Mejor porcentaje de paradas', figure: pct(lead.value), context: `${int(d.saves)} paradas, ${int(d.goals_conceded)} goles encajados` }
    case 'big_game_points_per90':
      return { title: 'Mejor contra los grandes', figure: int(lead.value), unit: 'pts SFA por 90′', context: `${int(d.big_points)} pts en ${int(d.big_matches)} partidos ante rivales de nivel alto o élite` }
  }
}

function groupLabel(lead: PlayerLead) {
  const { kind, competition_name: name, position } = lead.group
  const comp = name ? competitionLabel(name) : ''
  const peers = position ? POSITION_PLURAL[position] ?? 'su posición' : ''
  if (kind === 'competition') return `en ${comp}`
  if (kind === 'competition_position') return `entre los ${peers} de ${comp}`
  if (kind === 'scope_position') return `entre los ${peers} de la temporada`
  return 'en toda la temporada'
}

function minimumLabel(lead: PlayerLead) {
  const { minutes, attempts, attempts_kind: kind } = lead.minimums
  const attemptsText: Record<string, string> = {
    shots_on_target: 'tiros a puerta', dribble_attempts: 'regates intentados', duels: 'duelos', shots_faced: 'tiros recibidos',
  }
  if (lead.metric === 'big_game_points_per90') return `mín. ${int(minutes ?? 0)}′ ante grandes`
  if (attempts && kind) return `mín. ${int(attempts)} ${attemptsText[kind] ?? ''}`.trim()
  return minutes ? `mín. ${int(minutes)} minutos` : ''
}

export default function ProfileLeads({ playerId, scope }: { playerId: number; scope: string }) {
  const [leads, setLeads] = useState<PlayerLead[]>([])

  useEffect(() => {
    let active = true
    setLeads([])
    fetchPlayerLeads(playerId, scope).then((response) => {
      if (active && response?.supported) setLeads(response.items)
    })
    return () => { active = false }
  }, [playerId, scope])

  if (leads.length === 0) return null
  const allFirst = leads.every((lead) => lead.rank === 1)

  return (
    <section className="pf-leads" aria-labelledby="pf-leads-title">
      <h3 id="pf-leads-title">{allFirst ? 'Lidera en' : 'En lo más alto'}</h3>
      <ol className="pf-leads__list">
        {leads.map((lead) => {
          const copy = copyFor(lead)
          const logo = lead.group.competition_name ? tournamentCompetitionLogoByName(lead.group.competition_name) : null
          return (
            <li key={lead.metric} className={`pf-lead is-p${lead.rank}`}>
              <span className="pf-lead__rank" aria-label={`Puesto ${lead.rank}${lead.tied ? ', empatado' : ''}`}>
                <small>#</small>{lead.rank}
              </span>
              <span className="pf-lead__body">
                <strong>{copy.title}</strong>
                <span className="pf-lead__where">
                  {logo && <span className="tp-tile"><img src={logo} alt="" /></span>}
                  <span>{groupLabel(lead)}{lead.tied && ' (empatado)'} · de {int(lead.qualified_count)} jugadores</span>
                </span>
                <small className="pf-lead__context">{copy.context}<em> · {minimumLabel(lead)}</em></small>
              </span>
              <span className="pf-lead__figure"><b>{copy.figure}</b>{copy.unit && <em>{copy.unit}</em>}</span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
