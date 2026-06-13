import type { Competition, CompareResponse, PlayerCompetitionAchievement, PlayerDetail, PlayerEvent, PlayerFixture, PlayerSeasonStats, RankingResponse, SeasonsResponse } from '../types'

const BASE = '/api/v1'

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
  position?: string
  competition_id?: number
  limit?: number
  name?: string
}): Promise<RankingResponse> {
  const q = new URLSearchParams()
  if (params.season)        q.set('season', params.season)
  if (params.position)      q.set('position', params.position)
  if (params.competition_id != null) q.set('competition_id', String(params.competition_id))
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.name)          q.set('name', params.name)
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

export async function fetchPlayer(id: number, season?: string): Promise<PlayerDetail> {
  const key = `player:${id}:${season ?? ''}:active`
  const cached = getCached<PlayerDetail>(key)
  if (cached) return cached
  const q = new URLSearchParams()
  if (season) q.set('season', season)
  const data = await get<PlayerDetail>(`/players/${id}?${q.toString()}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerEvents(id: number, season?: string): Promise<PlayerEvent[]> {
  const key = `events:${id}:${season ?? ''}`
  const cached = getCached<PlayerEvent[]>(key)
  if (cached) return cached
  const q = season && season !== 'all' ? `?season=${season}` : ''
  const data = await get<PlayerEvent[]>(`/players/${id}/events${q}`)
  setCache(key, data)
  return data
}

export async function fetchPlayerFixtures(id: number, season?: string): Promise<PlayerFixture[]> {
  const key = `fixtures:${id}:${season ?? ''}`
  const cached = getCached<PlayerFixture[]>(key)
  if (cached) return cached
  const q = season && season !== 'all' ? `?season=${season}` : ''
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
  season: string,
): Promise<PlayerSeasonStats | null> {
  const key = `seasonstats:${id}:${season}`
  const cached = getCached<PlayerSeasonStats>(key)
  if (cached) return cached
  try {
    const data = await get<PlayerSeasonStats>(
      `/players/${id}/stats?season=${season}`,
    )
    setCache(key, data)
    return data
  } catch {
    return null
  }
}

export async function fetchPlayerAchievements(
  id: number,
  season?: string,
): Promise<PlayerCompetitionAchievement[]> {
  const key = `achievements:${id}:${season ?? ''}:active`
  const cached = getCached<PlayerCompetitionAchievement[]>(key)
  if (cached) return cached
  const params = new URLSearchParams()
  if (season) params.set('season', season)
  const data = await get<PlayerCompetitionAchievement[]>(
    `/players/${id}/achievements?${params.toString()}`,
  )
  setCache(key, data)
  return data
}
