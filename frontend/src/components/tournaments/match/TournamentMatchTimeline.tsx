import type { TournamentMatchEvent } from '../../../types'

const EVENT_LABELS: Record<string, string> = {
  goal: 'Gol', penalty: 'Gol de penal', own_goal: 'Autogol', missed_penalty: 'Penal fallado',
  yellow_card: 'Tarjeta amarilla', red_card: 'Tarjeta roja', yellow_red_card: 'Doble amarilla', substitution: 'Cambio',
}

function minute(event: TournamentMatchEvent) {
  return event.extra_minute > 0 ? `${event.minute}+${event.extra_minute}'` : `${event.minute}'`
}

export default function TournamentMatchTimeline({ events, homeTeamExternalId }: { events: TournamentMatchEvent[]; homeTeamExternalId: number | null }) {
  if (events.length === 0) return <div className="trm-empty">La cronología todavía no está disponible.</div>
  const ordered = [...events].sort((a, b) => a.minute - b.minute || a.extra_minute - b.extra_minute)
  return (
    <section className="trm-section trm-timeline">
      <header><span>Minuto a minuto</span><h2>Cronología</h2></header>
      <div className="trm-timeline__list">
        {ordered.map((event, index) => {
          const home = event.team_external_id === homeTeamExternalId
          return (
            <div className={`trm-event ${home ? 'is-home' : 'is-away'}`} key={`${event.minute}-${event.extra_minute}-${index}`}>
              <time>{minute(event)}</time>
              <i aria-hidden="true" />
              <div>
                <span>{EVENT_LABELS[event.event_type] ?? event.event_type}</span>
                <strong>{event.player_name || 'Jugador por confirmar'}</strong>
                {event.assist_name && <small>{event.event_type === 'substitution' ? `Entra ${event.assist_name}` : `Asistencia: ${event.assist_name}`}</small>}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
