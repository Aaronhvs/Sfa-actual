import type { SeasonItem } from '../types'

export function seasonLabel(season: string): string {
  if (season === 'all') return 'Total histórico'
  const year = parseInt(season, 10)
  if (isNaN(year)) return season
  const next = (year + 1).toString().slice(-2)
  return `${season}/${next}`
}

export function getSeasonLabel(season: string, items?: SeasonItem[]): string {
  if (items) {
    const item = items.find((candidate) => candidate.season === season)
    if (item?.label) return item.label
    if (item?.is_world_cup) return `Mundial ${item.season}`
  }
  return seasonLabel(season)
}

export function isWorldCupSeason(season: string, items?: SeasonItem[]): boolean {
  if (!items) return false
  return items.some((item) => item.season === season && item.is_world_cup === true)
}

export function isSeasonReceivingWcPoints(
  season: string,
  items?: SeasonItem[],
): boolean {
  if (!items) return false
  const worldCupItem = items.find((item) => item.is_world_cup)
  if (!worldCupItem) return false
  const worldCupYear = parseInt(worldCupItem.season, 10)
  const seasonYear = parseInt(season, 10)
  return seasonYear === worldCupYear - 1
}
