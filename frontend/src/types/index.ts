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
