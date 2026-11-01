import { useSyncExternalStore } from 'react'

const BASE = `${import.meta.env.VITE_API_BASE ?? ''}/api/v1`
const POLL_MS = 90_000

// One shared poller for every row on screen; it only runs while something is subscribed
// and the tab is visible.
let live: ReadonlySet<number> = new Set()
const listeners = new Set<() => void>()
let timer: number | undefined

async function refresh() {
  if (document.visibilityState !== 'visible') return
  try {
    const res = await fetch(`${BASE}/live/teams`)
    if (!res.ok) return
    const data = (await res.json()) as { team_ids?: number[] }
    const next = new Set(data.team_ids ?? [])
    if (next.size === live.size && [...next].every((id) => live.has(id))) return
    live = next
    listeners.forEach((notify) => notify())
  } catch {
    // The indicator is decorative: a failed poll keeps the previous state.
  }
}

function onVisible() {
  if (document.visibilityState === 'visible') void refresh()
}

function subscribe(notify: () => void) {
  listeners.add(notify)
  if (listeners.size === 1) {
    void refresh()
    timer = window.setInterval(refresh, POLL_MS)
    document.addEventListener('visibilitychange', onVisible)
  }
  return () => {
    listeners.delete(notify)
    if (listeners.size === 0) {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }
}

const getSnapshot = () => live

/** Crest URLs are built server-side as .../football/teams/{external_id}.png. */
export function teamIdFromLogo(url: string | null | undefined): number | null {
  const match = url?.match(/\/teams\/(\d+)\.png/)
  return match ? Number(match[1]) : null
}

export function useIsTeamLive(logoUrl: string | null | undefined): boolean {
  const teams = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  const id = teamIdFromLogo(logoUrl)
  return id != null && teams.has(id)
}
