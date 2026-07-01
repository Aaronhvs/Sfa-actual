const LOCALE = 'es-ES'

function localDate(iso: string): Date {
  return new Date(iso)
}

export function formatLocalDateShort(iso: string): string {
  return localDate(iso).toLocaleDateString(LOCALE, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function formatLocalDateLong(iso: string): string {
  return localDate(iso).toLocaleDateString(LOCALE, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export function formatLocalTime(iso: string): string {
  return localDate(iso).toLocaleTimeString(LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatLocalDateTimeShort(iso: string): string {
  return localDate(iso).toLocaleString(LOCALE, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function localDateKey(iso: string): string {
  const date = localDate(iso)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function compactLocalDateLabel(key: string): string {
  return new Date(`${key}T12:00:00`).toLocaleDateString(LOCALE, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function localTimeZoneLabel(): string {
  const parts = new Intl.DateTimeFormat(LOCALE, { timeZoneName: 'short' }).formatToParts(new Date())
  return parts.find((part) => part.type === 'timeZoneName')?.value ?? 'hora local'
}
