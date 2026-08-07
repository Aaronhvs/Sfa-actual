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
    const item = items.find((candidate) => candidate.key === season || candidate.season === season)
    if (item?.label) return item.label
    if (item?.is_world_cup) return `Mundial ${item.season}`
  }
  return seasonLabel(season)
}

export function isWorldCupSeason(season: string, items?: SeasonItem[]): boolean {
  if (!items) return false
  return items.some((item) => (
    (item.key === season || item.season === season) && item.kind === 'tournament'
  ))
}

export function isSeasonReceivingWcPoints(
  season: string,
  items?: SeasonItem[],
): boolean {
  if (!items) return false
  return items.some((item) => item.key === season && item.includes_world_cup === true)
}

export function seasonItemValue(item: SeasonItem): string {
  return item.key || item.season
}
