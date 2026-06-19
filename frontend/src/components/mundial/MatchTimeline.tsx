import type { WcFixtureEvent } from '../../types'

const GOAL_TYPES = new Set(['goal', 'own_goal', 'penalty'])

function minuteLabel(event: WcFixtureEvent): string {
  return event.extra_minute > 0
    ? `${event.minute}+${event.extra_minute}'`
    : `${event.minute}'`
}

function GoalIcon() {
  return (
    <svg className="wmd-tl-icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="8.5" fill="#C9A84C" />
      <circle cx="9" cy="9" r="4" fill="rgba(0,0,0,0.22)" />
      <circle cx="9" cy="9" r="1.8" fill="rgba(255,255,255,0.15)" />
    </svg>
  )
}

function OwnGoalIcon() {
  return (
    <svg className="wmd-tl-icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="8.5" fill="#d33f49" />
      <circle cx="9" cy="9" r="4" fill="rgba(0,0,0,0.22)" />
      <circle cx="9" cy="9" r="1.8" fill="rgba(255,255,255,0.15)" />
    </svg>
  )
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
              <span className="wmd-tl-event__assist">Asist. {event.assist_name}</span>
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
