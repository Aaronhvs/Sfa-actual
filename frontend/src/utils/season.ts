export function seasonLabel(season: string): string {
  if (season === 'all') return 'Total histórico'
  const year = parseInt(season, 10)
  if (isNaN(year)) return season
  const next = (year + 1).toString().slice(-2)
  return `${season}/${next}`
}
