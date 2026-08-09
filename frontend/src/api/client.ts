import type { Competition, CompareResponse, PlayerCompetitionAchievement, PlayerDetail, PlayerEvent, PlayerFixture, PlayerIndividualHonor, PlayerSeasonStats, RankingExplanationsResponse, RankingPlayerExplanation, RankingResponse, SeasonsResponse, WcFixtureDetailResponse, WcFixturesResponse, WcLiveResponse, WcStandingsResponse, WcTeamProfileResponse, WcTeamSFARankingResponse } from '../types'

const BASE = `${import.meta.env.VITE_API_BASE ?? ''}/api/v1`

const TTL_MS = 60_000
const _cache = new Map<string, { data: unknown; ts: number }>()

function getCached<T>(key: string): T | null {
  const entry = _cache.get(key)
  if (!entry) return null
  if (Date.now() - entry.ts > TTL_MS) { _cache.delete(key); return null }
  return entry.data as T
}

function setCache(key: string, data: unknown): void {
  _cache.set(key, { data, ts: Date.now() })
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export async function fetchRanking(params: {
  season?: string
  scope?: string
  position?: string
  competition_id?: number
  page?: number
  limit?: number
  offset?: number
  name?: string
  bonus_label?: string
}): Promise<RankingResponse> {
  const q = new URLSearchParams()
  if (params.season)        q.set('season', params.season)
  if (params.scope)         q.set('scope', params.scope)
  if (params.position)      q.set('position', params.position)
  if (params.competition_id != null) q.set('competition_id', String(params.competition_id))
  if (params.page != null)  q.set('page', String(params.page))
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.offset != null) q.set('offset', String(params.offset))
  if (params.name)          q.set('name', params.name)
  if (params.bonus_label)   q.set('bonus_label', params.bonus_label)
  q.set('use_total', 'true')
  const qs = q.toString()
  const key = `ranking:${qs}`
  const cached = getCached<RankingResponse>(key)
  if (cached) return cached
  const data = await get<RankingResponse>(`/ranking${qs ? `?${qs}` : ''}`)
  setCache(key, data)
  return data
}

export async function fetchSeasons(): Promise<SeasonsResponse> {
  const key = 'seasons'
  const cached = getCached<SeasonsResponse>(key)
  if (cached) return cached
  const data = await get<SeasonsResponse>('/seasons')
  setCache(key, data)
  return data
}

export async function fetchCompetitions(): Promise<Competition[]> {
  const key = 'competitions'
  const cached = getCached<Competition[]>(key)
  if (cached) return cached
  const data = await get<Competition[]>('/competitions')
  setCache(key, data)
  return data
}

export async function fetchPlayer(id: number, season?: string, scope?: string): Promise<PlayerDetail> {
  const key = `player:${id}:${season ?? ''}:${scope ?? ''}:active`
  const cached = getCached<PlayerDetail>(key)
  if (cached) return cached
  const q = new URLSearchParams()
  if (season) q.set('season', season)
  if (scope) q.set('scope', scope)
  const data = await get<PlayerDetail>(`/players/${id}?${q.toString()}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerEvents(id: number, season?: string, scope?: string): Promise<PlayerEvent[]> {
  const key = `events:${id}:${season ?? ''}:${scope ?? ''}`
  const cached = getCached<PlayerEvent[]>(key)
  if (cached) return cached
  const q = scope ? `?scope=${encodeURIComponent(scope)}` : season && season !== 'all' ? `?season=${season}` : ''
  const data = await get<PlayerEvent[]>(`/players/${id}/events${q}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerFixtures(id: number, season?: string, scope?: string): Promise<PlayerFixture[]> {
  const key = `fixtures:${id}:${season ?? ''}:${scope ?? ''}`
  const cached = getCached<PlayerFixture[]>(key)
  if (cached) return cached
  const q = scope ? `?scope=${encodeURIComponent(scope)}` : season && season !== 'all' ? `?season=${season}` : ''
  const data = await get<PlayerFixture[]>(`/players/${id}/fixtures${q}`)
  setCache(key, data)
  return data
}

export async function fetchCompare(playerA: number, playerB: number, season?: string): Promise<CompareResponse> {
  const key = `compare:${playerA}:${playerB}:${season ?? ''}`
  const cached = getCached<CompareResponse>(key)
  if (cached) return cached
  const q = new URLSearchParams()
  q.set('player_a', String(playerA))
  q.set('player_b', String(playerB))
  if (season) q.set('season', season)
  const data = await get<CompareResponse>(`/compare?${q.toString()}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerSeasonStats(
  id: number,
  season?: string,
  scope?: string,
): Promise<PlayerSeasonStats | null> {
  const key = `seasonstats:${id}:${season ?? ''}:${scope ?? ''}`
  const cached = getCached<PlayerSeasonStats>(key)
  if (cached) return cached
  try {
    const data = await get<PlayerSeasonStats>(
      `/players/${id}/stats?${scope ? `scope=${encodeURIComponent(scope)}` : `season=${season}`}`,
    )
    setCache(key, data)
    return data
  } catch {
    return null
  }
}

export async function fetchWcFixtures(fresh = false): Promise<WcFixturesResponse> {
  const key = 'wc:fixtures'
  if (!fresh) {
    const cached = getCached<WcFixturesResponse>(key)
    if (cached) return cached
  }
  const data = await get<WcFixturesResponse>('/wc/fixtures')
  setCache(key, data)
  return data
}

export async function fetchWcLive(): Promise<WcLiveResponse> {
  const key = 'wc:live'
  const cached = getCached<WcLiveResponse>(key)
  if (cached) return cached
  const data = await get<WcLiveResponse>('/wc/live')
  setCache(key, data)
  return data
}

export async function fetchRankingExplanations(params: {
  season: string
  competition_id?: number
  rules_version_id?: number
  scope?: string
  scope_key?: string
  position?: string
  bonus_label?: string
  limit?: number
  use_total?: boolean
}): Promise<RankingExplanationsResponse> {
  const q = new URLSearchParams()
  q.set('season', params.season)
  if (params.competition_id != null) q.set('competition_id', String(params.competition_id))
  if (params.rules_version_id != null) q.set('rules_version_id', String(params.rules_version_id))
  if (params.scope) q.set('scope', params.scope)
  if (params.scope_key) q.set('scope_key', params.scope_key)
  if (params.position) q.set('position', params.position)
  if (params.bonus_label) q.set('bonus_label', params.bonus_label)
  if (params.limit != null) q.set('limit', String(params.limit))
  q.set('use_total', params.use_total === false ? 'false' : 'true')
  const qs = q.toString()
  const key = `ranking-explanations:${qs}`
  const cached = getCached<RankingExplanationsResponse>(key)
  if (cached) return cached
  const data = await get<RankingExplanationsResponse>(`/ranking/explanations?${qs}`)
  setCache(key, data)
  return data
}

export async function fetchWcStandings(): Promise<WcStandingsResponse> {
  const key = 'wc:standings'
  const cached = getCached<WcStandingsResponse>(key)
  if (cached) return cached
  const data = await get<WcStandingsResponse>('/wc/standings')
  setCache(key, data)
  return data
}

export async function fetchWcFixtureDetail(
  fixtureId: number,
  fresh = false,
): Promise<WcFixtureDetailResponse> {
  const key = `wc:fixture-detail:${fixtureId}`
  if (!fresh) {
    const cached = getCached<WcFixtureDetailResponse>(key)
    if (cached) return cached
  }
  const data = await get<WcFixtureDetailResponse>(`/wc/fixtures/${fixtureId}`)
  setCache(key, data)
  return data
}

export async function fetchWcTeamSFARanking(): Promise<WcTeamSFARankingResponse> {
  const key = 'wc:team-sfa-ranking'
  const cached = getCached<WcTeamSFARankingResponse>(key)
  if (cached) return cached
  const data = await get<WcTeamSFARankingResponse>('/wc/teams/sfa-ranking')
  setCache(key, data)
  return data
}

export async function fetchWcTeamProfile(teamExternalId: number): Promise<WcTeamProfileResponse> {
  const key = `wc:team-profile:${teamExternalId}`
  const cached = getCached<WcTeamProfileResponse>(key)
  if (cached) return cached
  const data = await get<WcTeamProfileResponse>(`/wc/teams/${teamExternalId}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerAchievements(
  id: number,
  season?: string,
  scope?: string,
): Promise<PlayerCompetitionAchievement[]> {
  const key = `achievements:${id}:${season ?? ''}:${scope ?? ''}:active`
  const cached = getCached<PlayerCompetitionAchievement[]>(key)
  if (cached) return cached
  const params = new URLSearchParams()
  if (season) params.set('season', season)
  if (scope) params.set('scope', scope)
  const data = await get<PlayerCompetitionAchievement[]>(
    `/players/${id}/achievements?${params.toString()}`,
  )
  setCache(key, data)
  return data
}

export async function fetchPlayerIndividualHonors(
  id: number,
  season?: string,
  scope?: string,
): Promise<PlayerIndividualHonor[]> {
  const key = `individual-honors:${id}:${season ?? ''}:${scope ?? ''}:active`
  const cached = getCached<PlayerIndividualHonor[]>(key)
  if (cached) return cached
  const params = new URLSearchParams()
  if (season) params.set('season', season)
  if (scope) params.set('scope', scope)
  const data = await get<PlayerIndividualHonor[]>(
    `/players/${id}/individual-honors?${params.toString()}`,
  )
  setCache(key, data)
  return data
}

export async function fetchPlayerExplanation(params: {
  player_id: number
  season: string
  competition_id?: number
  rules_version_id?: number
  scope?: string
  use_total?: boolean
}): Promise<RankingPlayerExplanation | null> {
  const q = new URLSearchParams()
  q.set('season', params.season)
  if (params.competition_id != null) q.set('competition_id', String(params.competition_id))
  if (params.rules_version_id != null) q.set('rules_version_id', String(params.rules_version_id))
  if (params.scope) q.set('scope', params.scope)
  q.set('use_total', params.use_total === false ? 'false' : 'true')
  const qs = q.toString()
  const key = `player-explanation:${params.player_id}:${qs}`
  const cached = getCached<RankingPlayerExplanation>(key)
  if (cached) return cached
  try {
    const data = await get<RankingPlayerExplanation>(`/players/${params.player_id}/explanation?${qs}`)
    setCache(key, data)
    return data
  } catch {
    return null
  }
}
