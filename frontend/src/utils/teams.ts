/** Club pages are keyed by the provider's team id (it is what every crest URL carries). */
export function teamHref(name: string, externalId: number | null | undefined) {
  if (externalId == null) return null
  return `/equipo/${externalId}?${new URLSearchParams({ name })}`
}

export function externalIdFromLogo(url: string | null | undefined) {
  const match = url ? /\/teams\/(\d+)\.png/.exec(url) : null
  return match ? Number(match[1]) : null
}

/** Plain-language band for a 0–100 competitive level (ELO score). */
export function levelBand(score: number) {
  if (score >= 90) return 'Élite'
  if (score >= 75) return 'Alto'
  if (score >= 55) return 'Medio'
  return 'Bajo'
}
