const LOCALE = 'es-ES'
const MATCH_TIME_ZONE = 'America/Santiago'

function localDate(iso: string): Date {
  return new Date(iso)
}

export function formatLocalDateShort(iso: string): string {
  return localDate(iso).toLocaleDateString(LOCALE, {
    timeZone: MATCH_TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function formatLocalDateLong(iso: string): string {
  return localDate(iso).toLocaleDateString(LOCALE, {
    timeZone: MATCH_TIME_ZONE,
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export function formatLocalTime(iso: string): string {
  return localDate(iso).toLocaleTimeString(LOCALE, {
    timeZone: MATCH_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatLocalDateTimeShort(iso: string): string {
  return localDate(iso).toLocaleString(LOCALE, {
    timeZone: MATCH_TIME_ZONE,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function localDateKey(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: MATCH_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(localDate(iso))
  const year = parts.find((part) => part.type === 'year')?.value ?? '0000'
  const month = parts.find((part) => part.type === 'month')?.value ?? '01'
  const day = parts.find((part) => part.type === 'day')?.value ?? '01'
  return `${year}-${month}-${day}`
}

export function compactLocalDateLabel(key: string): string {
  return new Date(`${key}T12:00:00`).toLocaleDateString(LOCALE, {
    timeZone: MATCH_TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function localTimeZoneLabel(): string {
  return 'hora Chile'
}
