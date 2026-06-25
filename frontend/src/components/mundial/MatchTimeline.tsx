import type { WcFixtureEvent } from '../../types'

const GOAL_TYPES = new Set(['goal', 'own_goal', 'penalty'])

function minuteLabel(event: WcFixtureEvent): string {
  return event.extra_minute > 0
    ? `${event.minute}+${event.extra_minute}'`
    : `${event.minute}'`
}

function SoccerBallPattern({ ring }: { ring: string }) {
  return (
    <svg className="wmd-tl-icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      {/* Colored outer ring */}
      <circle cx="9" cy="9" r="8.5" fill={ring} />
      {/* White ball surface */}
      <circle cx="9" cy="9" r="7.2" fill="#f2f2f2" />
      {/* Soccer ball pentagon pattern — 1 center + 5 outer (truncated icosahedron projection) */}
      <g fill="#1c1c1c">
        {/* Center pentagon (circumradius 2.6, pointing up) */}
        <path d="M9,6.4 L11.5,8.2 L10.5,11.1 L7.5,11.1 L6.5,8.2 Z" />
        {/* Pentagon A — upper-right (center at 306°, r=5) */}
        <path d="M10.6,6.8 L9.8,4.2 L11.9,2.7 L14.1,4.2 L13.3,6.8 Z" />
        {/* Pentagon B — right (center at 18°, r=5) */}
        <path d="M11.6,9.8 L13.8,8.3 L16.0,9.8 L15.1,12.4 L12.4,12.4 Z" />
        {/* Pentagon C — bottom (center at 90°, r=5) */}
        <path d="M9,11.7 L11.2,13.3 L10.4,15.9 L7.6,15.9 L6.8,13.3 Z" />
        {/* Pentagon D — left (center at 162°, r=5) */}
        <path d="M6.4,9.8 L5.6,12.4 L2.9,12.4 L2.0,9.8 L4.2,8.3 Z" />
        {/* Pentagon E — upper-left (center at 234°, r=5) */}
        <path d="M7.4,6.8 L4.7,6.8 L3.9,4.2 L6.1,2.7 L8.2,4.2 Z" />
      </g>
      {/* Specular highlight */}
      <circle cx="7" cy="6.5" r="2.2" fill="white" opacity="0.18" />
    </svg>
  )
}

function GoalIcon() {
  return <SoccerBallPattern ring="#C9A84C" />
}

function OwnGoalIcon() {
  return <SoccerBallPattern ring="#d33f49" />
}

function MissedPenaltyIcon() {
  return (
    <svg className="wmd-tl-icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="7.5" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
      <line x1="6" y1="6" x2="12" y2="12" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="12" y1="6" x2="6" y2="12" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function YellowCardIcon() {
  return (
    <svg className="wmd-tl-icon wmd-tl-icon--card" viewBox="0 0 12 16" fill="none" aria-hidden="true">
      <rect x="0.5" y="0.5" width="11" height="15" rx="1.5" fill="#e8c44a" stroke="rgba(0,0,0,0.12)" strokeWidth="0.5" />
    </svg>
  )
}

function RedCardIcon() {
  return (
    <svg className="wmd-tl-icon wmd-tl-icon--card" viewBox="0 0 12 16" fill="none" aria-hidden="true">
      <rect x="0.5" y="0.5" width="11" height="15" rx="1.5" fill="#d33f49" stroke="rgba(0,0,0,0.12)" strokeWidth="0.5" />
    </svg>
  )
}

function YellowRedCardIcon() {
  return (
    <svg className="wmd-tl-icon wmd-tl-icon--card" viewBox="0 0 18 16" fill="none" aria-hidden="true">
      <rect x="0.5" y="2.5" width="11" height="13" rx="1.5" fill="#e8c44a" stroke="rgba(0,0,0,0.1)" strokeWidth="0.5" />
      <rect x="6.5" y="0.5" width="11" height="13" rx="1.5" fill="#d33f49" stroke="rgba(0,0,0,0.1)" strokeWidth="0.5" />
    </svg>
  )
}

function SubstitutionIcon() {
  return (
    <svg className="wmd-tl-icon" viewBox="0 0 16 18" fill="none" aria-hidden="true">
      <path d="M8 1L13 7H3L8 1Z" fill="#15965b" />
      <path d="M8 17L3 11H13L8 17Z" fill="#d33f49" />
    </svg>
  )
}

function EventIcon({ type }: { type: string }) {
  switch (type) {
    case 'goal':
    case 'penalty':
      return <GoalIcon />
    case 'own_goal':
      return <OwnGoalIcon />
    case 'missed_penalty':
      return <MissedPenaltyIcon />
    case 'yellow_card':
      return <YellowCardIcon />
    case 'red_card':
      return <RedCardIcon />
    case 'yellow_red_card':
      return <YellowRedCardIcon />
    case 'substitution':
      return <SubstitutionIcon />
    default:
      return null
  }
}

function EventContent({ event, side }: { event: WcFixtureEvent; side: 'home' | 'away' }) {
  const isSubst = event.event_type === 'substitution'
  const isGoal = GOAL_TYPES.has(event.event_type)

  return (
    <div className={`wmd-tl-event wmd-tl-event--${event.event_type} wmd-tl-event--${side}`}>
      <span className="wmd-tl-icon-wrap">
        <EventIcon type={event.event_type} />
      </span>
      <div className="wmd-tl-event__text">
        {isSubst ? (
          <>
            {event.assist_name && (
              <strong className="wmd-tl-event__player">{event.assist_name}</strong>
            )}
            {event.player_name && (
              <span className="wmd-tl-event__sub-out">sale {event.player_name}</span>
            )}
          </>
        ) : (
          <>
            <strong className={`wmd-tl-event__player${isGoal ? ' wmd-tl-event__player--goal' : ''}`}>
              {event.player_name}
            </strong>
            {event.assist_name && (
              <span className="wmd-tl-event__assist">Asistencia: {event.assist_name}</span>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function MatchTimeline({
  events,
  homeTeamExternalId,
}: {
  events: WcFixtureEvent[]
  homeTeamExternalId: number
}) {
  if (events.length === 0) return null

  return (
    <section className="wmd-timeline">
      <header className="wmd-timeline__header">
        <span>Cronología</span>
      </header>
      <div className="wmd-timeline__rows">
        {events.map((event, index) => {
          const side = event.team_external_id === homeTeamExternalId ? 'home' : 'away'
          const isGoal = GOAL_TYPES.has(event.event_type)
          return (
            <div
              key={index}
              className={`wmd-timeline__row${isGoal ? ' wmd-timeline__row--goal' : ''}`}
            >
              <div className="wmd-timeline__cell wmd-timeline__cell--home">
                {side === 'home' && <EventContent event={event} side="home" />}
              </div>
              <div className="wmd-timeline__spine">
                <time className={`wmd-timeline__minute${isGoal ? ' wmd-timeline__minute--goal' : ''}`}>
                  {minuteLabel(event)}
                </time>
              </div>
              <div className="wmd-timeline__cell wmd-timeline__cell--away">
                {side === 'away' && <EventContent event={event} side="away" />}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
