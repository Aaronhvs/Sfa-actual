import type {
  TournamentMatchDetail,
  TournamentMatchEvent,
  TournamentMatchLineupPlayer,
  TournamentMatchTeam,
} from '../../../types'

export type Side = 'home' | 'away'

export type PlayerMarks = {
  goals: number
  assists: number
  yellow: boolean
  red: boolean
  /** Minute the player left the pitch (substituted out). */
  off: number | null
  /** Minute the player came on (substitute). */
  on: number | null
  /** The other half of his substitution: who replaced him, or whom he replaced. */
  swap: string | null
}

export type MatchPlayer = TournamentMatchLineupPlayer & {
  side: Side
  team: TournamentMatchTeam
  starter: boolean
  marks: PlayerMarks
}

export type ResolvedEvent = TournamentMatchEvent & {
  /** Lineup player behind player_name (scorer, booked player, player going off). */
  actor: MatchPlayer | null
  /** Lineup player behind assist_name (assist provider, player coming on). */
  secondary: MatchPlayer | null
}

export type GoalEvent = ResolvedEvent & { side: Side; score: [number, number]; scorer: MatchPlayer | null }

const GOAL_TYPES = new Set(['goal', 'penalty', 'own_goal'])

export const isGoalEvent = (event: TournamentMatchEvent) => GOAL_TYPES.has(event.event_type)

export function minuteLabel(event: Pick<TournamentMatchEvent, 'minute' | 'extra_minute'>) {
  return event.extra_minute > 0 ? `${event.minute}+${event.extra_minute}'` : `${event.minute}'`
}

export function playerPhoto(externalId: number | null) {
  return externalId ? `https://media.api-sports.io/football/players/${externalId}.png` : null
}

export function teamLogo(team: TournamentMatchTeam) {
  return team.external_id ? `https://media.api-sports.io/football/teams/${team.external_id}.png` : null
}

/** Short display name for tight spots (pitch, chips): drops initials, keeps the last real token. */
export function shortName(name: string) {
  const tokens = name.split(' ').filter((token) => token && !/^[A-ZÁÉÍÓÚÑ]\.$/u.test(token))
  return tokens.length > 1 ? tokens[tokens.length - 1] : tokens[0] ?? name
}

function normalize(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

function tokens(value: string) {
  return normalize(value).split(/[\s.\-']+/).filter((token) => token.length >= 3)
}

/**
 * Events use full names ("Rodrigo Hernandez Cascante") while lineups use short ones ("Rodri").
 * Match within the same team by shared tokens, allowing a short token to prefix a longer one.
 * The lineup's last token (usually the surname) weighs double, so "Diego Valentín Gómez"
 * resolves to "V. Gómez" rather than "Diego Llorente".
 */
export function findPlayer(name: string | null, candidates: MatchPlayer[], loose = false) {
  if (!name) return null
  const eventTokens = tokens(name)
  // `loose` also accepts a shared 4-letter stem ("Raphinha" ~ "Raphael"); only safe on a small candidate set.
  const hit = (token: string) => eventTokens.some((other) => (
    other === token || (token.length >= 4 && other.startsWith(token)) || (other.length >= 4 && token.startsWith(other))
    || (loose && token.length >= 4 && other.length >= 4 && token.slice(0, 4) === other.slice(0, 4))
  ))
  let best: MatchPlayer | null = null
  let bestScore = 0
  for (const player of candidates) {
    const own = tokens(player.name)
    const score = own.reduce((sum, token, index) => sum + (hit(token) ? (index === own.length - 1 ? 2 : 1) : 0), 0)
    if (score > bestScore) {
      best = player
      bestScore = score
    }
  }
  return best
}

export function buildMatchModel(detail: TournamentMatchDetail) {
  const { fixture } = detail
  const sideOf = (teamExternalId: number | null): Side => (teamExternalId === fixture.home_team.external_id ? 'home' : 'away')

  const players: MatchPlayer[] = detail.lineups.flatMap((lineup) => {
    const side = sideOf(lineup.team.external_id)
    const make = (player: TournamentMatchLineupPlayer, starter: boolean): MatchPlayer => ({
      ...player,
      side,
      team: lineup.team,
      starter,
      marks: { goals: 0, assists: 0, yellow: false, red: false, off: null, on: null, swap: null },
    })
    return [...lineup.start_xi.map((player) => make(player, true)), ...lineup.substitutes.map((player) => make(player, false))]
  })

  const ordered = [...detail.events].sort((a, b) => a.minute - b.minute || a.extra_minute - b.extra_minute)
  const events: ResolvedEvent[] = []
  const goals: GoalEvent[] = []
  const score: [number, number] = [0, 0]

  for (const event of ordered) {
    const side = sideOf(event.team_external_id)
    const team = players.filter((player) => player.side === side)
    const isSub = event.event_type === 'substitution'
    // A substitution narrows the search: only someone on the pitch can go off, only an unused substitute can come on.
    const onPitch = team.filter((player) => (player.starter || player.marks.on != null) && player.marks.off == null)
    const bench = team.filter((player) => !player.starter && player.marks.on == null)
    const actor = findPlayer(event.player_name, isSub ? onPitch : team)
    const secondary = findPlayer(event.assist_name, isSub ? bench : team, isSub)
    events.push({ ...event, actor, secondary })
    if (isGoalEvent(event)) {
      // An own goal counts for the opposite side.
      const scoringSide: Side = event.event_type === 'own_goal' ? (side === 'home' ? 'away' : 'home') : side
      score[scoringSide === 'home' ? 0 : 1] += 1
      goals.push({ ...event, actor, secondary, side: scoringSide, score: [...score] as [number, number], scorer: actor })
      if (actor && event.event_type !== 'own_goal') actor.marks.goals += 1
      if (secondary) secondary.marks.assists += 1
    } else if (event.event_type === 'yellow_card') {
      if (actor) actor.marks.yellow = true
    } else if (event.event_type === 'red_card' || event.event_type === 'yellow_red_card') {
      if (actor) actor.marks.red = true
    } else if (isSub) {
      // Pair the two players from the event itself; matching by minute breaks when two changes share it.
      if (actor) { actor.marks.off = event.minute; actor.marks.swap = secondary?.name ?? event.assist_name ?? null }
      if (secondary) { secondary.marks.on = event.minute; secondary.marks.swap = actor?.name ?? event.player_name ?? null }
    }
  }

  const scored = players.filter((player) => player.sfa_points != null)
  const ranked = [...scored].sort((a, b) => (b.sfa_points ?? 0) - (a.sfa_points ?? 0))
  const teamPoints = (side: Side) => scored.filter((player) => player.side === side).reduce((sum, player) => sum + (player.sfa_points ?? 0), 0)

  return {
    players,
    events,
    goals,
    ranked,
    topIds: new Set(ranked.slice(0, 3).map((player) => player.external_id)),
    teamPoints: { home: teamPoints('home'), away: teamPoints('away') },
    sideOf,
  }
}

export type MatchModel = ReturnType<typeof buildMatchModel>
