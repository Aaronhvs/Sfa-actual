export interface SeasonItem {
  season: string
  is_latest: boolean
  is_world_cup?: boolean
  label?: string
}

export function isWorldCupItem(item: SeasonItem): boolean {
  return item.is_world_cup === true
}

export interface SeasonsResponse {
  seasons: SeasonItem[]
}

export interface Competition {
  id: number
  name: string
  country: string
  factor: number
}

export interface RankedPlayer {
  rank: number
  id: number
  name: string
  team: string
  team_logo_url: string | null
  position: string
  competition: string
  sfa_pts: number
  matches: number
  photo_url: string | null
  goals: number
  assists: number
  dribbles_won: number
  duels_won: number
}

export interface RankingResponse {
  season: string
  total: number
  ranking: RankedPlayer[]
}

export interface BreakdownEntry {
  count: number
  pts: number
}

export interface PlayerDetail {
  id: number
  name: string
  team: string
  position: string
  competition: string
  sfa_pts: number
  matches: number
  total_goals: number
  total_assists: number
  photo_url: string | null
  global_rank: number
  season: string
  breakdown: Record<string, BreakdownEntry> | null
  competitions: string[]
  available_seasons: string[]
}

export interface PlayerEvent {
  id: number
  competition: string
  stage: string
  fixture_id: number
  home_team: string
  away_team: string
  played_at: string
  minute: number
  event_type: string
  score_before: string | null
  score_diff: number | null
  m1: number
  m2: number
  m3: number
  m4: number
  mvisit: number
  pts: number
}

export interface FixtureBreakdownEntry {
  count: number
  pts: number
}

export interface PlayerFixture {
  fixture_id: number
  competition: string
  stage: string
  home_team: string
  away_team: string
  played_at: string
  sfa_pts: number
  events_count: number
  minutes: number
  shots_on: number
  dribbles_won: number
  duels_won: number
  tackles_won: number
  interceptions: number
  blocks: number
  fouls_drawn: number
  clearances: number
  home_team_logo: string | null
  away_team_logo: string | null
  breakdown: Record<string, FixtureBreakdownEntry> | null
  rating: number | null
}

export interface CompareResponse {
  season: string
  player_a: PlayerDetail
  player_b: PlayerDetail
}

export interface PlayerSeasonStats {
  player_id: number
  competition_id: number | null
  season: string
  matches: number
  minutes: number
  goals: number
  assists: number
  shots_total: number
  shots_on: number
  passes_total: number
  passes_accuracy_avg: number
  passes_key: number
  dribbles_won: number
  dribbles_attempts: number
  dribbles_past: number
  duels_won: number
  duels_total: number
  tackles_won: number
  interceptions: number
  blocks: number
  fouls_drawn: number
  fouls_committed: number
  cards_yellow: number
  cards_red: number
  penalty_won: number
  saves: number
  goals_conceded: number
  dribble_success_rate: number | null
  duel_win_rate: number | null
}

export interface WcTeam {
  id: number
  name: string
  external_id: number | null
}

export interface WcFixture {
  id: number
  external_id: number
  stage: string
  matchday: number | null
  played_at: string
  is_live: boolean
  status: string
  status_label: string
  elapsed: number | null
  home_goals: number | null
  away_goals: number | null
  home_team: WcTeam
  away_team: WcTeam
}

export interface WcFixturesResponse {
  fixtures: WcFixture[]
  season: string
}

export interface WcLiveResponse {
  live: WcFixture[]
  has_live: boolean
}

export interface WcStanding {
  group: string
  position: number
  team: WcTeam
  played: number
  won: number
  drawn: number
  lost: number
  goals_for: number
  goals_against: number
  goal_difference: number
  points: number
  form: string | null
}

export interface WcStandingsResponse {
  standings: WcStanding[]
  season: string
}

export interface WcVenue {
  name: string | null
  city: string | null
}

export interface WcLineupPlayer {
  external_id: number | null
  name: string
  number: number | null
  position: string | null
  grid: string | null
  player_id: number | null
  sfa_points: number | null
}

export interface WcTeamLineup {
  team: WcTeam
  formation: string | null
  coach_name: string | null
  coach_photo: string | null
  start_xi: WcLineupPlayer[]
  substitutes: WcLineupPlayer[]
}

export interface WcStatistic {
  label: string
  home_value: string | null
  away_value: string | null
  home_numeric: number | null
  away_numeric: number | null
}

export interface WcFixtureEvent {
  minute: number
  extra_minute: number
  team_external_id: number
  event_type: string
  player_name: string
  assist_name: string | null
}

export interface WcFixtureDetailResponse {
  fixture: WcFixture
  venue: WcVenue
  referee: string | null
  lineups: WcTeamLineup[]
  statistics: WcStatistic[]
  events: WcFixtureEvent[]
}

export interface PlayerCompetitionAchievement {
  achievement_id: number
  competition_id: number
  competition_name: string
  team_id: number
  team_name: string
  season: string
  phase: string
  title_count: number
  bonus_pts: number
}
