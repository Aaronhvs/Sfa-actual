import { useMemo, useState } from 'react'
import type { PlayerEvent, PlayerFixture } from '../../types'
import MatchListModal, { type ModalItem } from './MatchListModal'

interface Props {
  fixtures: PlayerFixture[]
  events: PlayerEvent[]
}

interface ModalData {
  title: string
  subtitle?: string
  items: ModalItem[]
}

interface Card {
  id: string
  fixture: PlayerFixture
  headline: string
  stat: string
  chips?: string[]
  context: string
  tag?: string
  variant: 'gold' | 'accent'
  modal?: ModalData
}

type GoalType = 'penalty' | 'decisive' | 'pressure' | 'normal'

function classifyGoal(e: PlayerEvent): GoalType {
  if (e.event_type === 'goal_penalty') return 'penalty'
  if (e.m3 >= 2.0) return 'decisive'
  if (e.m3 >= 1.3) return 'pressure'
  return 'normal'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })
}

function fmt(n: number): string {
  return n.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function goalCount(f: PlayerFixture): number {
  return (f.breakdown?.['goal']?.count ?? 0) + (f.breakdown?.['goal_penalty']?.count ?? 0)
}

function assistCount(f: PlayerFixture): number {
  return f.breakdown?.['assist']?.count ?? 0
}

const TEAM_NAMES_ES: Record<string, string> = {
  Morocco: 'Marruecos',
  'Korea Republic': 'Corea del Sur',
  USA: 'Estados Unidos',
  Qatar: 'Catar',
  Czechia: 'Chequia',
}

function competitionLabel(value: string): string {
  const normalized = value.trim().toLowerCase()
  if (normalized === 'world cup' || normalized === 'fifa world cup') return 'Mundial'
  return value
}

function stageLabel(value: string): string {
  const normalized = value.trim().toLowerCase()
  if (normalized === 'group' || normalized === 'group stage') return 'Fase de grupos'
  if (normalized === 'round of 32') return 'Dieciseisavos'
  if (normalized === 'round of 16') return 'Octavos'
  if (normalized === 'quarter-finals' || normalized === 'quarterfinals') return 'Cuartos'
  if (normalized === 'semi-finals' || normalized === 'semifinals') return 'Semifinales'
  if (normalized === 'final') return 'Final'
  return value
}

function teamLabel(value: string): string {
  return TEAM_NAMES_ES[value] ?? value
}

function matchup(f: PlayerFixture): string {
  return `${teamLabel(f.home_team)} vs ${teamLabel(f.away_team)}`
}

export default function HighlightsView({ fixtures, events }: Props) {
  const [modal, setModal] = useState<ModalData | null>(null)

  const cards = useMemo(() => {
    if (fixtures.length === 0) return []

    const result: Card[] = []

    const fixtureMap = new Map<number, PlayerFixture>()
    for (const f of fixtures) fixtureMap.set(f.fixture_id, f)

    const sortedByDate = [...fixtures].sort(
      (a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime(),
    )

    // ── 1. Mejor actuación · gold ─────────────────────────────────
    const bestMatch = fixtures.reduce((b, f) => (f.sfa_pts > b.sfa_pts ? f : b), fixtures[0])
    const bmGoals = goalCount(bestMatch)
    const bmAssists = assistCount(bestMatch)
    const bmChips: string[] = []
    if (bmGoals > 0 || bmAssists > 0) {
      const parts: string[] = []
      if (bmGoals > 0) parts.push(`${bmGoals}G`)
      if (bmAssists > 0) parts.push(`${bmAssists}A`)
      bmChips.push(parts.join(' · '))
    }
    bmChips.push(competitionLabel(bestMatch.competition))
    if (bestMatch.stage) bmChips.push(stageLabel(bestMatch.stage))
    result.push({
      id: 'best',
      fixture: bestMatch,
      headline: 'MEJOR ACTUACIÓN',
      stat: `${fmt(Math.round(bestMatch.sfa_pts))} pts`,
      chips: bmChips,
      context: `${matchup(bestMatch)} · ${formatDate(bestMatch.played_at)}`,
      tag: 'TOP PARTIDO',
      variant: 'gold',
    })

    // ── 2. Hat tricks · gold ──────────────────────────────────────
    const hatTrickMatches = fixtures
      .filter((f) => goalCount(f) >= 3)
      .sort((a, b) => goalCount(b) - goalCount(a))
    if (hatTrickMatches.length > 0) {
      const best = hatTrickMatches[0]
      const maxGoals = goalCount(best)
      const count = hatTrickMatches.length
      result.push({
        id: 'hattrick',
        fixture: best,
        headline: maxGoals >= 5 ? 'MANITA' : maxGoals >= 4 ? 'PÓKER DE GOLES' : count > 1 ? 'HAT TRICKS EN LA TEMP.' : 'HAT TRICK',
        stat: count > 1 ? `${count}` : `${maxGoals} GOLES`,
        chips: count > 1
          ? [`Mejor: ${maxGoals} goles`, formatDate(best.played_at)]
          : [best.competition, formatDate(best.played_at)],
        context: count > 1
          ? `Mejor: ${matchup(best)} · ${formatDate(best.played_at)} (${maxGoals} goles)`
          : `${matchup(best)} · ${best.competition} · ${formatDate(best.played_at)}`,
        tag: 'HISTÓRICO',
        variant: 'gold',
        modal: count > 1 ? {
          title: 'Hat Tricks en la temporada',
          subtitle: `${count} en la temporada`,
          items: hatTrickMatches.map((f) => ({ type: 'fixture' as const, fixture: f, extra: `${goalCount(f)}G` })),
        } : undefined,
      })
    }

    // ── 3. Dobletes · gold ────────────────────────────────────────
    const dobleMatches = fixtures
      .filter((f) => goalCount(f) === 2)
      .sort((a, b) => b.sfa_pts - a.sfa_pts)
    if (dobleMatches.length > 0) {
      const best = dobleMatches[0]
      const count = dobleMatches.length
      result.push({
        id: 'doblete',
        fixture: best,
        headline: count > 1 ? 'DOBLETES EN LA TEMP.' : 'DOBLETE',
        stat: count > 1 ? `${count}` : '1 DOBLETE',
        chips: [best.competition, formatDate(best.played_at)],
        context: count > 1
          ? `Mejor: ${matchup(best)} · ${formatDate(best.played_at)}`
          : `${matchup(best)} · ${best.competition} · ${formatDate(best.played_at)}`,
        variant: 'gold',
        modal: count > 1 ? {
          title: 'Dobletes en la temporada',
          subtitle: `${count} en la temporada`,
          items: dobleMatches.map((f) => ({ type: 'fixture' as const, fixture: f, extra: '2G' })),
        } : undefined,
      })
    }

    // ── 4. Gol más valioso · gold ─────────────────────────────────
    const goalEvents = events.filter(
      (e) => e.event_type === 'goal' || e.event_type === 'goal_penalty',
    )
    if (goalEvents.length > 0) {
      const best = goalEvents.reduce((b, e) => (e.pts > b.pts ? e : b), goalEvents[0])
      const bf = fixtureMap.get(best.fixture_id) ?? fixtures[0]
      const chips: string[] = []
      if (best.minute) chips.push(`min ${best.minute}'`)
      const classification = classifyGoal(best)
      chips.push(
        classification === 'penalty' ? 'Penal' :
        classification === 'decisive' ? 'Decisivo' :
        classification === 'pressure' ? 'En presión' : 'Normal',
      )
      result.push({
        id: 'best_goal',
        fixture: bf,
        headline: 'GOL MÁS VALIOSO',
        stat: `+${fmt(Math.round(best.pts))} pts`,
        chips,
        context: `${matchup(bf)} · ${bf.competition} · ${formatDate(bf.played_at)}`,
        tag: 'TOP GOL',
        variant: 'gold',
      })
    }

    // ── 5. Asistencia más valiosa · accent ────────────────────────
    const assistEvents = events.filter((e) => e.event_type === 'assist')
    if (assistEvents.length > 0) {
      const best = assistEvents.reduce((b, e) => (e.pts > b.pts ? e : b), assistEvents[0])
      const bf = fixtureMap.get(best.fixture_id) ?? fixtures[0]
      const chips: string[] = []
      if (best.minute) chips.push(`min ${best.minute}'`)
      if (best.score_diff !== null) {
        chips.push(best.score_diff < 0 ? 'Perdiendo' : best.score_diff === 0 ? 'Empatando' : 'Ganando')
      }
      result.push({
        id: 'best_assist',
        fixture: bf,
        headline: 'ASISTENCIA MÁS VALIOSA',
        stat: `+${fmt(Math.round(best.pts))} pts`,
        chips,
        context: `${matchup(bf)} · ${bf.competition} · ${formatDate(bf.played_at)}`,
        tag: 'TOP ASIST.',
        variant: 'accent',
      })
    }

    // ── 6. Noche perfecta (G + A) · gold ─────────────────────────
    const perfectMatches = fixtures
      .filter((f) => goalCount(f) > 0 && assistCount(f) > 0)
      .sort((a, b) => b.sfa_pts - a.sfa_pts)
    if (perfectMatches.length > 0) {
      const best = perfectMatches[0]
      const count = perfectMatches.length
      result.push({
        id: 'perfect',
        fixture: best,
        headline: count > 1 ? 'GOL + ASIST. EN UN PARTIDO' : 'NOCHE PERFECTA',
        stat: count > 1 ? `${count} VECES` : `${goalCount(best)}G + ${assistCount(best)}A`,
        chips: [best.competition, formatDate(best.played_at)],
        context: count > 1
          ? `Mejor: ${matchup(best)} · ${formatDate(best.played_at)}`
          : `${matchup(best)} · ${best.competition} · ${formatDate(best.played_at)}`,
        tag: count > 1 ? undefined : 'GOL + ASIST.',
        variant: 'gold',
        modal: count > 1 ? {
          title: 'Gol + Asistencia en un partido',
          subtitle: `${count} veces en la temporada`,
          items: perfectMatches.map((f) => ({
            type: 'fixture' as const,
            fixture: f,
            extra: `${goalCount(f)}G · ${assistCount(f)}A`,
          })),
        } : undefined,
      })
    }

    // ── 7. Goles en presión · gold (nuevo) ───────────────────────
    const pressureGoals = goalEvents.filter((e) => e.m3 >= 1.6)
    if (pressureGoals.length >= 2) {
      const best = pressureGoals.reduce((b, e) => (e.pts > b.pts ? e : b), pressureGoals[0])
      const bf = fixtureMap.get(best.fixture_id) ?? fixtures[0]
      result.push({
        id: 'pressure_goals',
        fixture: bf,
        headline: 'GOLES EN PRESIÓN',
        stat: `${pressureGoals.length}`,
        chips: ['M3 ≥ 1.6', `Mejor: +${fmt(Math.round(best.pts))} pts`],
        context: `Goles en situaciones de alta presión · Mejor: ${matchup(bf)} · ${formatDate(bf.played_at)}`,
        variant: 'gold',
        modal: {
          title: 'Goles en Presión',
          subtitle: `${pressureGoals.length} goles con M3 ≥ 1.6`,
          items: [...pressureGoals]
            .sort((a, b) => b.pts - a.pts)
            .map((e) => ({ type: 'event' as const, event: e, fixture: fixtureMap.get(e.fixture_id) ?? fixtures[0] })),
        },
      })
    }

    // ── 8. Actuaciones élite · gold (nuevo) ──────────────────────
    const eliteFixtures = fixtures
      .filter((f) => f.sfa_pts >= 2500)
      .sort((a, b) => b.sfa_pts - a.sfa_pts)
    if (eliteFixtures.length >= 2) {
      const best = eliteFixtures[0]
      result.push({
        id: 'elite_perf',
        fixture: best,
        headline: 'ACTUACIONES ÉLITE',
        stat: `${eliteFixtures.length}`,
        chips: ['≥ 2500 pts', `Mejor: ${fmt(Math.round(best.sfa_pts))} pts`],
        context: `Partidos por encima de 2500 SFA pts · Mejor: ${matchup(best)}`,
        variant: 'gold',
        modal: {
          title: 'Actuaciones Élite',
          subtitle: `${eliteFixtures.length} partidos ≥ 2500 pts`,
          items: eliteFixtures.map((f) => ({ type: 'fixture' as const, fixture: f })),
        },
      })
    }

    // ── 9. Penales ganados · gold ─────────────────────────────────
    const totalPenalties = fixtures.reduce(
      (acc, f) => acc + (f.breakdown?.['penalty_won']?.count ?? 0),
      0,
    )
    if (totalPenalties >= 2) {
      const topPen = fixtures
        .filter((f) => (f.breakdown?.['penalty_won']?.count ?? 0) > 0)
        .sort((a, b) => (b.breakdown?.['penalty_won']?.count ?? 0) - (a.breakdown?.['penalty_won']?.count ?? 0))[0]
      result.push({
        id: 'penalties',
        fixture: topPen,
        headline: 'PENALES GANADOS',
        stat: `${totalPenalties} EN LA TEMP.`,
        chips: [topPen.competition, formatDate(topPen.played_at)],
        context: `${matchup(topPen)} · ${formatDate(topPen.played_at)}`,
        variant: 'gold',
      })
    }

    // ── 10. Racha anotadora · accent ──────────────────────────────
    let maxStreak = 0
    let streak = 0
    let streakFixture = sortedByDate[0]
    let tempEnd = sortedByDate[0]
    for (const f of sortedByDate) {
      if (goalCount(f) > 0 || assistCount(f) > 0) {
        streak++
        tempEnd = f
        if (streak > maxStreak) { maxStreak = streak; streakFixture = tempEnd }
      } else {
        streak = 0
      }
    }
    if (maxStreak >= 3) {
      result.push({
        id: 'streak',
        fixture: streakFixture,
        headline: 'RACHA ANOTADORA',
        stat: `${maxStreak} PARTIDOS`,
        chips: ['Seguidos con gol o asist.', `Hasta ${formatDate(streakFixture.played_at)}`],
        context: `Partidos seguidos con gol o asistencia · hasta ${formatDate(streakFixture.played_at)}`,
        variant: 'accent',
      })
    }

    // ── 11. Acciones vs élite · accent ────────────────────────────
    const eliteEvents = events.filter(
      (e) =>
        (e.event_type === 'goal' || e.event_type === 'goal_penalty' || e.event_type === 'assist') &&
        e.m1 >= 1.3,
    )
    if (eliteEvents.length > 0) {
      const best = eliteEvents.reduce((b, e) => (e.pts > b.pts ? e : b), eliteEvents[0])
      const bf = fixtureMap.get(best.fixture_id) ?? fixtures[0]
      result.push({
        id: 'elite',
        fixture: bf,
        headline: eliteEvents.length > 1 ? 'ACCIONES VS ÉLITE' : 'CONTRA ÉLITE',
        stat: eliteEvents.length > 1 ? `${eliteEvents.length}` : `+${fmt(Math.round(best.pts))} pts`,
        chips: ['M1 ≥ 1.3', `Mejor: +${fmt(Math.round(best.pts))} pts`],
        context: eliteEvents.length > 1
          ? `En la temporada · Mejor: ${matchup(bf)} · ${formatDate(bf.played_at)}`
          : `${matchup(bf)} · ${bf.competition} · ${formatDate(bf.played_at)}`,
        variant: 'accent',
        modal: eliteEvents.length > 1 ? {
          title: 'Acciones vs Élite',
          subtitle: `${eliteEvents.length} acciones con M1 ≥ 1.3`,
          items: [...eliteEvents]
            .sort((a, b) => b.pts - a.pts)
            .map((e) => ({ type: 'event' as const, event: e, fixture: fixtureMap.get(e.fixture_id) ?? fixtures[0] })),
        } : undefined,
      })
    }

    // ── 12. Momentos clave · accent (nuevo) ──────────────────────
    const keyMomentEvents = events.filter(
      (e) =>
        e.m3 >= 1.3 &&
        (e.event_type === 'goal' || e.event_type === 'goal_penalty' || e.event_type === 'assist'),
    )
    if (keyMomentEvents.length >= 3) {
      const best = keyMomentEvents.reduce((b, e) => (e.pts > b.pts ? e : b), keyMomentEvents[0])
      const bf = fixtureMap.get(best.fixture_id) ?? fixtures[0]
      result.push({
        id: 'key_moments',
        fixture: bf,
        headline: 'MOMENTOS CLAVE',
        stat: `${keyMomentEvents.length}`,
        chips: ['M3 ≥ 1.3', `Mejor: +${fmt(Math.round(best.pts))} pts`],
        context: `Acciones en momentos de alta presión temporal · Mejor: ${matchup(bf)}`,
        variant: 'accent',
        modal: {
          title: 'Momentos Clave',
          subtitle: `${keyMomentEvents.length} acciones con M3 ≥ 1.3`,
          items: [...keyMomentEvents]
            .sort((a, b) => b.pts - a.pts)
            .map((e) => ({ type: 'event' as const, event: e, fixture: fixtureMap.get(e.fixture_id) ?? fixtures[0] })),
        },
      })
    }

    // ── 13. Doble asistencia · accent ─────────────────────────────
    const multiAssistMatches = fixtures
      .filter((f) => assistCount(f) >= 2)
      .sort((a, b) => assistCount(b) - assistCount(a))
    if (multiAssistMatches.length > 0) {
      const best = multiAssistMatches[0]
      const a = assistCount(best)
      result.push({
        id: 'multi_assist',
        fixture: best,
        headline: a >= 3 ? 'MAESTRO DE ASISTENCIAS' : multiAssistMatches.length > 1 ? 'DOBLES ASISTENCIAS' : 'DOBLE ASISTENCIA',
        stat: multiAssistMatches.length > 1 ? `${multiAssistMatches.length} VECES` : `${a} ASIST.`,
        chips: [best.competition, formatDate(best.played_at)],
        context: `${matchup(best)} · ${formatDate(best.played_at)}`,
        variant: 'accent',
        modal: multiAssistMatches.length > 1 ? {
          title: 'Dobles Asistencias en la temporada',
          subtitle: `${multiAssistMatches.length} veces`,
          items: multiAssistMatches.map((f) => ({ type: 'fixture' as const, fixture: f, extra: `${assistCount(f)}A` })),
        } : undefined,
      })
    }

    // ── 14. Rey del regate · accent ───────────────────────────────
    const topDribbles = fixtures.reduce((b, f) => (f.dribbles_won > b.dribbles_won ? f : b), fixtures[0])
    if (topDribbles.dribbles_won >= 5) {
      result.push({
        id: 'dribbles',
        fixture: topDribbles,
        headline: 'REY DEL REGATE',
        stat: `${topDribbles.dribbles_won} REGATES`,
        chips: [topDribbles.competition, formatDate(topDribbles.played_at)],
        context: `${matchup(topDribbles)} · ${formatDate(topDribbles.played_at)}`,
        variant: 'accent',
      })
    }

    // ── 15. Muro defensivo · accent ───────────────────────────────
    const defValue = (f: PlayerFixture) => f.tackles_won + f.interceptions + f.blocks
    const topDef = fixtures.reduce((b, f) => (defValue(f) > defValue(b) ? f : b), fixtures[0])
    if (defValue(topDef) >= 7) {
      result.push({
        id: 'defensive',
        fixture: topDef,
        headline: 'MURO DEFENSIVO',
        stat: `${defValue(topDef)} ACCIONES`,
        chips: [topDef.competition, formatDate(topDef.played_at)],
        context: `${matchup(topDef)} · ${formatDate(topDef.played_at)}`,
        variant: 'accent',
      })
    }

    return result
  }, [fixtures, events])

  if (cards.length === 0) {
    return <div className="empty-state">Sin datos destacados esta temporada.</div>
  }

  return (
    <>
      <div className="hl-grid">
        {cards.map((card, i) => {
          const isClickable = !!card.modal
          return (
            <article
              key={card.id}
              className={`hl-card hl-card--${card.variant}${card.id === 'best' ? ' hl-card--featured' : ''}${isClickable ? ' hl-card--clickable' : ''}`}
              style={{ animationDelay: `${i * 40}ms` }}
              onClick={isClickable ? () => setModal(card.modal!) : undefined}
              role={isClickable ? 'button' : undefined}
              tabIndex={isClickable ? 0 : undefined}
              onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') setModal(card.modal!) } : undefined}
            >
              <div className="hl-card__top">
                <span className="hl-card__headline">{card.headline}</span>
                {card.tag && <span className="hl-card__tag">{card.tag}</span>}
              </div>
              <div className="hl-card__stat">{card.stat}</div>
              <div className="hl-card__bottom">
                {card.id === 'best' && card.chips && card.chips.length > 0 && (
                  <div className="hl-card__chips">
                    {card.chips.map((chip, ci) => (
                      <span key={ci} className="hl-chip">{chip}</span>
                    ))}
                  </div>
                )}
                <div className="hl-card__context">
                  {card.id === 'best' ? card.context : card.fixture
                    ? matchup(card.fixture)
                    : card.context}
                </div>
                {isClickable && <span className="hl-card__cta">Ver todos</span>}
              </div>
            </article>
          )
        })}
      </div>


      {modal && (
        <MatchListModal
          title={modal.title}
          subtitle={modal.subtitle}
          items={modal.items}
          onClose={() => setModal(null)}
        />
      )}
    </>
  )
}
