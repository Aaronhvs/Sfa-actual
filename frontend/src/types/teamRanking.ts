export interface RankedTeam {
  rank: number
  id: number
  name: string
  team_logo_url: string | null
  competition_id: number
  competition: string
  score: number | null
  elo_raw: number | null
  elo_score: number | null
  squad_score: number | null
  effective_elo_weight: number
  effective_squad_weight: number
  elo_season: string | null
  elo_source: string | null
  squad_season: string | null
  observed_players: number
  scored_players: number
  observed_appearances: number
  scored_appearances: number
  coverage: number | null
  squad_data_cutoff: string | null
  elo_data_cutoff: string | null
  availability: null
}

export interface TeamRankingResponse {
  season: string
  scope: string | null
  total: number
  pagination: { page: number; limit: number; total_items: number; total_pages: number; has_next: boolean; has_prev: boolean }
  model: {
    version: string
    descriptive_only: boolean
    experimental: boolean
    feeds_m1: boolean
    elo_weight: number
    squad_weight: number
    recent_matches: number
    shrinkage_minutes: number
    as_of: string
    data_cutoff: string | null
    rules_version_id: number | null
    population_teams: number
  }
  ranking: RankedTeam[]
}
