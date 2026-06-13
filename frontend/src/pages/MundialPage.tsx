import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { WcFixture, WcFixturesResponse } from '../types'
import { fetchWcFixtures, fetchWcLive } from '../api/client'

const TEAM_LOGO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/teams/${externalId}.png` : null

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  })
}

function groupByRound(fixtures: WcFixture[]): Map<string, WcFixture[]> {
  const map = new Map<string, WcFixture[]>()
  for (const f of fixtures) {
    const label = f.matchday != null ? `Jornada ${f.matchday}` : f.stage
    const group = map.get(label) ?? []
    group.push(f)
    map.set(label, group)
  }
  return map
}

interface FixtureCardProps {
  fixture: WcFixture
  liveIds: Set<number>
}

function FixtureCard({ fixture, liveIds }: FixtureCardProps) {
  const isLive = liveIds.has(fixture.id)
  const homeLogo = TEAM_LOGO(fixture.home_team.external_id)
  const awayLogo = TEAM_LOGO(fixture.away_team.external_id)

  return (
    <article className={`wm-fixture${isLive ? ' wm-fixture--live' : ''}`}>
      {isLive && <div className="wm-fixture__spectrum-bar" aria-hidden="true" />}

      <div className="wm-fixture__team wm-fixture__team--home">
        {homeLogo && (
          <img
            src={homeLogo}
            alt=""
            className="wm-fixture__logo"
            loading="lazy"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        )}
        <span className="wm-fixture__team-name">{fixture.home_team.name}</span>
      </div>

      <div className="wm-fixture__center">
        {isLive ? (
          <span className="wm-fixture__live-badge" aria-label="Partido en curso">
            <span className="wm-fixture__live-dot" aria-hidden="true" />
            EN VIVO
          </span>
        ) : (
          <>
            <time className="wm-fixture__date" dateTime={fixture.played_at}>
              {formatDate(fixture.played_at)}
            </time>
            <span className="wm-fixture__time">{formatTime(fixture.played_at)}</span>
          </>
        )}
      </div>

      <div className="wm-fixture__team wm-fixture__team--away">
        <span className="wm-fixture__team-name">{fixture.away_team.name}</span>
        {awayLogo && (
          <img
            src={awayLogo}
            alt=""
            className="wm-fixture__logo"
            loading="lazy"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        )}
      </div>
    </article>
  )
}

export default function MundialPage() {
  const [data, setData] = useState<WcFixturesResponse | null>(null)
  const [liveIds, setLiveIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

  useEffect(() => {
    fetchWcFixtures()
      .then(setData)
      .catch((e) => setError(e.message ?? 'Error al cargar partidos'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    function refreshLive() {
      fetchWcLive()
        .then((res) => setLiveIds(new Set(res.live.map((f) => f.id))))
        .catch(() => {})
    }
    refreshLive()
    const timer = setInterval(refreshLive, 60_000)
    return () => clearInterval(timer)
  }, [])

  const rounds: Map<string, WcFixture[]> = data ? groupByRound(data.fixtures) : new Map()
  const totalMatches = data?.fixtures.length ?? 0
  const liveCount = liveIds.size

  return (
    <div className="mundial-page">
      <header className="wm-header">
        <div className="wm-header__pattern" aria-hidden="true" />
        <div className="wm-header__spectrum" aria-hidden="true" />
        <div className="wm-header__content">
          <Link to="/ranking?season=2026" className="wm-header__back">
            ← Volver al ranking
          </Link>
          <div className="wm-header__copy">
            <span className="wm-header__eyebrow">SFA · Edición Global</span>
            <h1 className="wm-header__title">
              <span className="wm-header__title-main">Mundial</span>
              <span className="wm-header__title-year">2026</span>
            </h1>
            <p className="wm-header__subtitle">
              {totalMatches > 0 ? `${totalMatches} partidos · Temporada 2026` : 'Cargando partidos…'}
            </p>
          </div>
          <div className="wm-header__stamp" aria-label="48 selecciones, Edición 2026">
            <span className="wm-header__stamp-count">48</span>
            <strong className="wm-header__stamp-label">Selecciones</strong>
            <small className="wm-header__stamp-edition">Edición 2026</small>
          </div>
        </div>
      </header>

      {liveCount > 0 && (
        <div className="wm-live-banner" role="status" aria-live="polite">
          <span className="wm-live-banner__dot" aria-hidden="true" />
          {liveCount === 1
            ? '1 partido en curso ahora mismo'
            : `${liveCount} partidos en curso ahora mismo`}
        </div>
      )}

      <main className="wm-body">
        {loading && (
          <div className="wm-loading">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="wm-round">
                <div className="skeleton wm-round__skeleton-title" />
                {Array.from({ length: 2 }).map((_, j) => (
                  <div key={j} className="skeleton wm-fixture-skeleton" />
                ))}
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="empty-state">
            {error}
          </div>
        )}

        {!loading && !error && rounds.size === 0 && (
          <div className="empty-state">
            No hay partidos registrados para el Mundial 2026 todavía.
          </div>
        )}

        {!loading && !error && rounds.size > 0 && (
          <div className="wm-rounds">
            {Array.from(rounds.entries()).map(([label, fixtures]) => (
              <section key={label} className="wm-round">
                <header className="wm-round__header">
                  <span className="wm-round__spectrum" aria-hidden="true" />
                  <h2 className="wm-round__title">{label}</h2>
                  <span className="wm-round__count">{fixtures.length} partidos</span>
                </header>
                <div className="wm-fixtures-grid">
                  {fixtures.map((f) => (
                    <FixtureCard key={f.id} fixture={f} liveIds={liveIds} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
