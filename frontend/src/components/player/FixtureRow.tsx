import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { PlayerEvent, PlayerFixture } from '../../types'
import { competitionLabel, stageLabel } from '../../utils/footballLabels'
import { worldCupTeamNameFromString } from '../../utils/worldCupTeams'

const WC_COMPETITION_ID = 350

interface Props {
  fixture: PlayerFixture
  events: PlayerEvent[]
}

const SHOOTOUT_TYPES = new Set([
  'goal_shootout',
  'goal_shootout_decisive',
  'missed_shootout',
  'missed_shootout_decisive',
])
const GOAL_TYPES = new Set(['goal', 'goal_penalty', ...SHOOTOUT_TYPES])
const CREATION_TYPES = new Set(['assist', 'corner_assist'])

const EVENT_LABELS: Record<string, string> = {
  goal: 'GOL',
  goal_penalty: 'PENALTI',
  goal_shootout: 'TANDA',
  goal_shootout_decisive: 'TANDA DEC.',
  missed_shootout: 'TANDA FALL.',
  missed_shootout_decisive: 'TANDA DEC. FALL.',
  assist: 'ASIST.',
  corner_assist: 'PRE-ASIST.',
}

const SCORING_ACTIONS = [
  { key: 'goal', label: 'Goles' },
  { key: 'goal_penalty', label: 'Penaltis' },
  { key: 'goal_shootout', label: 'Tanda conv.' },
  { key: 'goal_shootout_decisive', label: 'Tanda decisiva' },
  { key: 'missed_shootout', label: 'Tanda fallada' },
  { key: 'missed_shootout_decisive', label: 'Fallo decisivo' },
  { key: 'assist', label: 'Asistencias' },
  { key: 'corner_assist', label: 'Pre-asist.' },
]

const HEADER_CHIPS = [
  { key: 'goal', label: 'GOL', type: 'goal' as const },
  { key: 'goal_penalty', label: 'PEN', type: 'goal' as const },
  { key: 'goal_shootout', label: 'TAN', type: 'goal' as const },
  { key: 'goal_shootout_decisive', label: 'DEC', type: 'goal' as const },
  { key: 'missed_shootout', label: 'FAL', type: 'goal' as const },
  { key: 'missed_shootout_decisive', label: 'FDEC', type: 'goal' as const },
  { key: 'assist', label: 'AST', type: 'assist' as const },
  { key: 'corner_assist', label: 'PRE', type: 'assist' as const },
]

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })
}

function teamAbbr(name: string): string {
  return name.split(' ').map((w) => w[0]).slice(0, 3).join('').toUpperCase()
}

interface TeamLogoProps {
  name: string
  logo: string | null
}

function TeamLogo({ name, logo }: TeamLogoProps) {
  const [failed, setFailed] = useState(false)
  if (logo && !failed) {
    return (
      <img
        className="team-logo"
        src={logo}
        alt={name}
        onError={() => setFailed(true)}
      />
    )
  }
  return <div className="team-logo-placeholder">{teamAbbr(name)}</div>
}

function eventContext(e: PlayerEvent): string {
  const parts: string[] = []
  if (e.score_before) {
    const score = e.score_before.replace(':', '-')
    if (e.score_diff != null && e.score_diff < 0) parts.push(`Perdiendo ${score}`)
    else if (e.score_diff === 0) parts.push(`Empatando ${score}`)
    else parts.push(`Ganando ${score}`)
  }
  if (e.m3 >= 1.5) parts.push('Alta presión')
  else if (e.m3 >= 1.2) parts.push('Momento clave')
  return parts.join(' · ')
}

function fmt(n: number): string {
  return n.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function SummaryChips({ fixture }: { fixture: PlayerFixture }) {
  const bd = fixture.breakdown ?? {}
  const chips = HEADER_CHIPS.filter(({ key }) => (bd[key]?.count ?? 0) > 0)
  const hasDribbles = fixture.dribbles_won > 0
  const hasStats = chips.length > 0 || hasDribbles
  if (!hasStats) return null

  return (
    <div className="fsc-row">
      {chips.map(({ key, label, type }) => (
        <span key={key} className={`fsc fsc--${type}`}>
          {label} {bd[key].count}
        </span>
      ))}
      {hasDribbles && (
        <span className="fsc fsc--stat">REG {fixture.dribbles_won}</span>
      )}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: number | string
  pts?: number
  zero?: boolean
}

function StatCard({ label, value, pts, zero }: StatCardProps) {
  const isEmpty = value === 0 || value === '—'
  return (
    <div className={`fac${isEmpty && zero ? ' fac--zero' : ''}`}>
      <span className="fac__label">{label}</span>
      <span className="fac__count">{value === 0 && zero ? '0' : value}</span>
      {pts != null && pts !== 0 ? (
        <span className="fac__pts">{fmt(pts)} pts</span>
      ) : (
        <span className="fac__pts fac__pts--empty">—</span>
      )}
    </div>
  )
}

function ActionBreakdownGrid({ fixture }: { fixture: PlayerFixture }) {
  const bd = fixture.breakdown ?? {}
  const statsPts = bd['stats']?.pts ?? 0

  const totalStatCount =
    fixture.shots_total +
    fixture.shots_on +
    fixture.passes_total +
    fixture.passes_key +
    fixture.dribbles_won +
    fixture.duels_won +
    fixture.tackles_won +
    fixture.interceptions +
    fixture.blocks

  return (
    <div className="fac-section">
      <div className="event-category">Desglose de acciones</div>

      {/* Scoring zone: equal-width table row, large numbers */}
      <div className="fac-scoring-zone">
        {SCORING_ACTIONS.map(({ key, label }) => {
          const entry = bd[key]
          return (
            <StatCard key={key} label={label} value={entry?.count ?? 0} pts={entry?.pts} zero />
          )
        })}
        {statsPts > 0 && (
          <div className="fac fac--stats-total">
            <span className="fac__label">Total estadísticas</span>
            <span className="fac__count fac__count--gold">{fmt(statsPts)}</span>
            <span className="fac__pts">pts</span>
          </div>
        )}
        {totalStatCount === 0 && statsPts === 0 && null}
      </div>

      {/* Volume zone: compact chips */}
      {totalStatCount > 0 && (
        <div className="fac-volume-zone">
          {fixture.shots_total > 0 && <StatCard label="Remates" value={fixture.shots_total} />}
          {fixture.shots_on > 0 && <StatCard label="Al arco" value={fixture.shots_on} />}
          {fixture.passes_total > 0 && <StatCard label="Pases" value={fixture.passes_total} />}
          {fixture.passes_accurate > 0 && <StatCard label="Pases comp." value={fixture.passes_accurate} />}
          {fixture.passes_key > 0 && <StatCard label="Pases clave" value={fixture.passes_key} />}
          {fixture.dribbles_won > 0 && <StatCard label="Regates" value={fixture.dribbles_won} />}
          {fixture.duels_won > 0 && <StatCard label="Duelos" value={fixture.duels_won} />}
          {(fixture.tackles_won > 0 || fixture.interceptions > 0) && (
            <StatCard label="Entradas/Int" value={fixture.tackles_won + fixture.interceptions} />
          )}
          {fixture.blocks > 0 && <StatCard label="Bloqueos" value={fixture.blocks} />}
          {fixture.clearances > 0 && <StatCard label="Despejes" value={fixture.clearances} />}
          {fixture.fouls_drawn > 0 && <StatCard label="Faltas rec." value={fixture.fouls_drawn} />}
        </div>
      )}
    </div>
  )
}

function multiplierAvg(events: PlayerEvent[], key: 'm1' | 'm2' | 'm3'): number | null {
  if (events.length === 0) return null
  return events.reduce((sum, event) => sum + event[key], 0) / events.length
}

function rivalContext(avgM1: number): { title: string; detail: string; tone: 'up' | 'down' | 'flat' } {
  if (avgM1 >= 1.4) {
    return {
      title: 'Rival élite',
      detail: 'M1 subió fuerte el valor porque el rival era de máxima dificultad.',
      tone: 'up',
    }
  }
  if (avgM1 >= 1.1) {
    return {
      title: 'Rival superior',
      detail: 'M1 premió las acciones por hacerse contra un rival más fuerte.',
      tone: 'up',
    }
  }
  if (avgM1 >= 0.9) {
    return {
      title: 'Rival similar',
      detail: 'M1 mantuvo el valor cerca de la base por dificultad pareja.',
      tone: 'flat',
    }
  }
  return {
    title: 'Rival inferior',
    detail: 'M1 redujo el valor porque el rival tenía menor dificultad.',
    tone: 'down',
  }
}

function matchLocationContext(fixture: PlayerFixture, isVisitor: boolean) {
  if (fixture.competition_id === WC_COMPETITION_ID) {
    return {
      title: 'Sede neutral',
      factor: 'Mvisit ×1.00',
      detail: 'En Mundial no se suma bonus local ni visitante.',
      tone: 'flat' as const,
    }
  }
  if (isVisitor) {
    return {
      title: 'Visitante',
      factor: 'Mvisit ×1.15',
      detail: 'Se aplicó bonus por jugar fuera de casa.',
      tone: 'up' as const,
    }
  }
  return {
    title: 'Local',
    factor: 'Mvisit ×1.00',
    detail: 'No se aplicó bonus visitante.',
    tone: 'flat' as const,
  }
}

function FixtureContextBar({ fixture, events }: { fixture: PlayerFixture; events: PlayerEvent[] }) {
  const [expandedCard, setExpandedCard] = useState<string | null>(null)

  const keyEvents = events.filter(
    (event) => GOAL_TYPES.has(event.event_type) || CREATION_TYPES.has(event.event_type),
  )
  const avgM1 = multiplierAvg(keyEvents, 'm1')
  const avgM2 = multiplierAvg(keyEvents, 'm2')
  const avgM3 = multiplierAvg(keyEvents, 'm3')
  const isVisitor = keyEvents.some((event) => event.mvisit > 1)
  const location = keyEvents.length > 0 ? matchLocationContext(fixture, isVisitor) : null

  const cards: {
    label: string
    title: string
    factor?: string
    detail: string
    tone?: 'up' | 'down' | 'flat'
  }[] = []

  if (fixture.minutes > 0) {
    cards.push({
      label: 'Minutos',
      title: `${fixture.minutes} min`,
      detail: 'Tiempo jugado en este partido.',
      tone: 'flat',
    })
  }

  if (avgM1 !== null) {
    const rival = rivalContext(avgM1)
    cards.push({
      label: 'Dificultad rival',
      title: rival.title,
      factor: `M1 ×${avgM1.toFixed(2)}`,
      detail: rival.detail,
      tone: rival.tone,
    })
  }

  if (avgM2 !== null) {
    cards.push({
      label: 'Fase del torneo',
      title: 'Impacto de fase',
      factor: `M2 ×${avgM2.toFixed(2)}`,
      detail: 'Ajusta el valor según la etapa competitiva del partido.',
      tone: avgM2 > 1 ? 'up' : 'flat',
    })
  }

  if (avgM3 !== null) {
    cards.push({
      label: 'Momento del partido',
      title: avgM3 >= 1.2 ? 'Momento clave' : 'Contexto normal',
      factor: `M3 ×${avgM3.toFixed(2)}`,
      detail: avgM3 >= 1.2
        ? 'El marcador o el minuto aumentaron el peso de la acción.'
        : 'La acción se valoró con presión normal de partido.',
      tone: avgM3 >= 1.2 ? 'up' : 'flat',
    })
  }

  if (location) {
    cards.push({
      label: 'Campo',
      title: location.title,
      factor: location.factor,
      detail: location.detail,
      tone: location.tone,
    })
  }

  if (cards.length === 0) return null

  return (
    <div className="fxctx">
      {cards.map((card) => {
        const isExpanded = expandedCard === card.label
        return (
          <div
            key={card.label}
            className={`fxctx__card fxctx__card--${card.tone ?? 'flat'}${isExpanded ? ' fxctx__card--expanded' : ''}`}
            onClick={() => setExpandedCard(isExpanded ? null : card.label)}
            role="button"
            tabIndex={0}
            aria-expanded={isExpanded}
            onKeyDown={(e) => e.key === 'Enter' && setExpandedCard(isExpanded ? null : card.label)}
          >
            <span className="fxctx__label">{card.label}</span>
            <span className="fxctx__hero">{card.factor ?? card.title}</span>
            {card.factor && <span className="fxctx__verdict">{card.title}</span>}
            <div className="fxctx__detail-wrapper">
              <div className="fxctx__detail-inner">
                <p className="fxctx__detail">{card.detail}</p>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function WorldCupMatchLink({ fixture }: { fixture: PlayerFixture }) {
  if (fixture.competition_id !== WC_COMPETITION_ID || fixture.fixture_external_id == null) {
    return null
  }

  return (
    <Link to={`/mundial/partido/${fixture.fixture_external_id}`} className="fixture-row__wc-link">
      <span className="fixture-row__wc-link-text">Ver resultado y cronología del Mundial</span>
      <span className="fixture-row__wc-link-icon" aria-hidden="true">
        <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
          <path d="M2 10L10 2M10 2H4M10 2V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </span>
    </Link>
  )
}

function EventsPanel({ events, fixture }: { events: PlayerEvent[]; fixture: PlayerFixture }) {
  const attackEvents = events.filter((e) => GOAL_TYPES.has(e.event_type))
  const creationEvents = events.filter((e) => CREATION_TYPES.has(e.event_type))
  const hasDetail = attackEvents.length > 0 || creationEvents.length > 0

  return (
    <div className="events-panel">
      <WorldCupMatchLink fixture={fixture} />
      <FixtureContextBar fixture={fixture} events={events} />
      <ActionBreakdownGrid fixture={fixture} />
      {hasDetail && (
        <div className="event-category-group">
          <div className="event-category">Detalle de eventos</div>
          {[...attackEvents, ...creationEvents].map((e) => (
            <div key={e.id} className="event-row">
              <div>
                <div className="event-row__minute">{e.minute}'</div>
                <div className="event-row__minute-label">min</div>
              </div>
              <div className="event-row__desc">{eventContext(e) || e.competition}</div>
              <span className={`event-type-badge${GOAL_TYPES.has(e.event_type) ? ' event-type-badge--goal' : ''}`}>
                {EVENT_LABELS[e.event_type] ?? e.event_type.toUpperCase()}
              </span>
              <div className="event-row__pts">
                {fmt(e.pts)}
                <span style={{ fontSize: '0.58rem', color: 'var(--text-faint)', marginLeft: 2 }}>pts</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const EXCELLENT_THRESHOLD = 3000

export default function FixtureRow({ fixture, events }: Props) {
  const [open, setOpen] = useState(false)
  const fixtureEvents = events.filter((e) => e.event_type !== 'stats')
  const isExcellent = fixture.sfa_pts >= EXCELLENT_THRESHOLD
  const isWorldCup = fixture.competition_id === WC_COMPETITION_ID
  const homeTeamName = isWorldCup ? worldCupTeamNameFromString(fixture.home_team) : fixture.home_team
  const awayTeamName = isWorldCup ? worldCupTeamNameFromString(fixture.away_team) : fixture.away_team

  return (
    <div className={`fixture-row${isExcellent ? ' fixture-row--excellent' : ''}`}>
      <button className="fixture-row__header" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <div className="fixture-row__match">
          <div className="fixture-row__shield">
            <TeamLogo name={homeTeamName} logo={fixture.home_team_logo} />
            <span className="fixture-row__vs">vs</span>
            <TeamLogo name={awayTeamName} logo={fixture.away_team_logo} />
          </div>
          <div className="fixture-row__teams">
            <div className="fixture-row__matchup">
              {homeTeamName} vs {awayTeamName}
            </div>
            <div className="fixture-row__meta">
              {competitionLabel(fixture.competition)} &middot; {stageLabel(fixture.stage)} &middot; {formatDate(fixture.played_at)}
            </div>
            <SummaryChips fixture={fixture} />
          </div>
        </div>

        <div className="fixture-row__score-col">
          <div>
            {fixture.minutes > 0 && (
              <span className="fixture-row__mins">{fixture.minutes} min</span>
            )}
            <span className="fixture-row__pts">{fmt(fixture.sfa_pts)}</span>
            <span className="fixture-row__pts-label">pts</span>
          </div>
        </div>

        <svg className={`fixture-row__chevron${open ? ' fixture-row__chevron--open' : ''}`} width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div className={`fixture-row__panel-wrap${open ? ' fixture-row__panel-wrap--open' : ''}`}>
        <div className="fixture-row__panel-inner">
          <EventsPanel events={fixtureEvents} fixture={fixture} />
        </div>
      </div>
    </div>
  )
}
