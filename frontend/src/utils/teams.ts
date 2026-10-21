/** Club pages are keyed by the provider's team id (it is what every crest URL carries). */
export function teamHref(name: string, externalId: number | null | undefined) {
  if (externalId == null) return null
  return `/equipo/${externalId}?${new URLSearchParams({ name })}`
}

export function externalIdFromLogo(url: string | null | undefined) {
  const match = url ? /\/teams\/(\d+)\.png/.exec(url) : null
  return match ? Number(match[1]) : null
}

/**
 * Team strength on the scoring engine's own 0-100 scale (the input to the rival multiplier, M1):
 * (ELO - 1400) / 700, clamped. Mirrors backend `EloCalculatorService.normalize`.
 * Not a percentile: a percentile over every catalogued club (amateur cup sides included)
 * pushed any decent team above 85.
 */
export function strengthFromElo(elo: number | null | undefined) {
  if (elo == null) return null
  return Math.max(0, Math.min(100, ((elo - 1400) / 700) * 100))
}

/** Plain-language band for the engine's 0-100 strength. */
export function levelBand(score: number) {
  if (score >= 70) return 'Élite'
  if (score >= 50) return 'Alto'
  if (score >= 30) return 'Medio'
  return 'Bajo'
}
