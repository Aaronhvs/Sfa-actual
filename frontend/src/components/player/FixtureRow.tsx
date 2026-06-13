import { useState } from 'react'
import type { PlayerEvent, PlayerFixture } from '../../types'

interface Props {
  fixture: PlayerFixture
  events: PlayerEvent[]
}

const GOAL_TYPES = new Set(['goal', 'goal_penalty', 'goal_shootout'])
const CREATION_TYPES = new Set(['assist', 'corner_assist'])

const EVENT_LABELS: Record<string, string> = {
  goal: 'GOL',
  goal_penalty: 'PENALTI',
  goal_shootout: 'TANDA',
  assist: 'ASIST.',
  corner_assist: 'PRE-ASIST.',
}

const SCORING_ACTIONS = [
  { key: 'goal', label: 'Goles' },
  { key: 'goal_penalty', label: 'Penaltis' },
  { key: 'goal_shootout', label: 'Tanda' },
  { key: 'assist', label: 'Asistencias' },
  { key: 'corner_assist', label: 'Pre-asist.' },
]

const HEADER_CHIPS = [
  { key: 'goal', label: 'GOL', type: 'goal' as const },
  { key: 'goal_penalty', label: 'PEN', type: 'goal' as const },
  { key: 'goal_shootout', label: 'TAN', type: 'goal' as const },
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
      {pts != null && pts > 0 ? (
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
    fixture.shots_on +
    fixture.dribbles_won +
    fixture.duels_won +
    fixture.tackles_won +
    fixture.interceptions +
    fixture.blocks

  return (
    <div className="fac-section">
      <div className="event-category">Desglose de acciones</div>
      <div className="fac-grid">
        {SCORING_ACTIONS.map(({ key, label }) => {
          const entry = bd[key]
          return (
            <StatCard
              key={key}
              label={label}
              value={entry?.count ?? 0}
              pts={entry?.pts}
              zero
            />
          )
        })}

        {totalStatCount > 0 && (
          <>
            <div className="fac-divider" />
            {fixture.shots_on > 0 && (
              <StatCard label="Disparos" value={fixture.shots_on} />
            )}
            {fixture.dribbles_won > 0 && (
              <StatCard label="Regates" value={fixture.dribbles_won} />
            )}
            {fixture.duels_won > 0 && (
              <StatCard label="Duelos" value={fixture.duels_won} />
            )}
            {(fixture.tackles_won > 0 || fixture.interceptions > 0) && (
              <StatCard
                label="Tackles/Int"
                value={fixture.tackles_won + fixture.interceptions}
              />
            )}
            {fixture.blocks > 0 && (
              <StatCard label="Bloqueos" value={fixture.blocks} />
            )}
            {fixture.clearances > 0 && (
              <StatCard label="Despejes" value={fixture.clearances} />
            )}
            {fixture.fouls_drawn > 0 && (
              <StatCard label="Faltas rec." value={fixture.fouls_drawn} />
            )}
            {statsPts > 0 && (
              <div className="fac fac--stats-total">
                <span className="fac__label">Total stats</span>
                <span className="fac__count fac__count--gold">{fmt(statsPts)}</span>
                <span className="fac__pts">pts</span>
              </div>
            )}
          </>
        )}

        {totalStatCount === 0 && statsPts > 0 && (
          <>
            <div className="fac-divider" />
            <div className="fac fac--stats-total">
              <span className="fac__label">Stats</span>
              <span className="fac__count fac__count--gold">{fmt(statsPts)}</span>
              <span className="fac__pts">pts</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function FixtureContextBar({ fixture, events }: { fixture: PlayerFixture; events: PlayerEvent[] }) {
  const keyEvents = events.filter(
    (event) => GOAL_TYPES.has(event.event_type) || CREATION_TYPES.has(event.event_type),
  )
  const avgM1 = keyEvents.length > 0
    ? keyEvents.reduce((sum, event) => sum + event.m1, 0) / keyEvents.length
    : null
  const isVisitor = keyEvents.some((event) => event.mvisit > 1)

  const items: { label: string; value: string }[] = []

  if (fixture.minutes > 0) {
    items.push({ label: 'Jugó', value: `${fixture.minutes}'` })
  }

  if (avgM1 !== null) {
    const rivalDesc =
      avgM1 >= 1.4 ? 'Élite' :
      avgM1 >= 1.1 ? 'Superior' :
      avgM1 >= 0.9 ? 'Similar' : 'Inferior'
    items.push({ label: 'Rival', value: `M1 ×${avgM1.toFixed(2)} · ${rivalDesc}` })
  }

  if (keyEvents.length > 0) {
    items.push({ label: 'Campo', value: isVisitor ? 'Visitante ×1.15' : 'Local' })
  }

  if (items.length === 0) return null

  return (
    <div className="fxctx">
      {items.map((item) => (
        <div key={item.label} className="fxctx__item">
          <span className="fxctx__label">{item.label}</span>
          <span className="fxctx__value">{item.value}</span>
        </div>
      ))}
    </div>
  )
}

function EventsPanel({ events, fixture }: { events: PlayerEvent[]; fixture: PlayerFixture }) {
  const attackEvents = events.filter((e) => GOAL_TYPES.has(e.event_type))
  const creationEvents = events.filter((e) => CREATION_TYPES.has(e.event_type))
  const hasDetail = attackEvents.length > 0 || creationEvents.length > 0

  return (
    <div className="events-panel">
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

  return (
    <div className={`fixture-row${isExcellent ? ' fixture-row--excellent' : ''}`}>
      <button className="fixture-row__header" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <div className="fixture-row__match">
          <div className="fixture-row__shield">
            <TeamLogo name={fixture.home_team} logo={fixture.home_team_logo} />
            <span className="fixture-row__vs">vs</span>
            <TeamLogo name={fixture.away_team} logo={fixture.away_team_logo} />
          </div>
          <div className="fixture-row__teams">
            <div className="fixture-row__matchup">
              {fixture.home_team} vs {fixture.away_team}
            </div>
            <div className="fixture-row__meta">
              {fixture.competition} &middot; {fixture.stage} &middot; {formatDate(fixture.played_at)}
            </div>
            <SummaryChips fixture={fixture} />
          </div>
        </div>

        <div className="fixture-row__score-col">
          <div>
            {fixture.minutes > 0 && (
              <span className="fixture-row__mins">{fixture.minutes}'</span>
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
