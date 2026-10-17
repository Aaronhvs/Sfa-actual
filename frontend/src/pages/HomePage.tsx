import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking, fetchSeasons } from '../api/client'
import type { RankedPlayer, SeasonItem } from '../types'
import HomeRankingGallery from '../components/HomeRankingGallery'
import HomeMethod from '../components/HomeMethod'
import HomeDiscoverSections from '../components/HomeDiscoverSections'
import './HomePage.css'

export default function HomePage() {
  const [season, setSeason] = useState<SeasonItem | null>(null)
  const [players, setPlayers] = useState<RankedPlayer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    async function load() {
      try {
        const catalog = await fetchSeasons()
        if (controller.signal.aborted) return
        const current = catalog.seasons.find((item) => item.is_latest) ?? catalog.seasons[0]
        if (!current) throw new Error('No hay temporadas disponibles')
        const result = await fetchRanking({ scope: current.key, limit: 3, offset: 0, signal: controller.signal })
        if (controller.signal.aborted) return
        setSeason(current)
        setPlayers(result.ranking)
        setLoading(false)

      } catch {
        if (controller.signal.aborted) return
        setError(true)
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [retry])

  const rankingUrl = season ? `/ranking?scope=${encodeURIComponent(season.key)}` : '/ranking'
  const playerUrl = (id: number) => `/player/${id}?${new URLSearchParams({ scope: season?.key ?? '', returnTo: rankingUrl })}`
  const leader = players[0]

  return (
    <div className="home-page">
      <header className="home-intro">
        <div>
          <p className="home-eyebrow">Stats Football Award</p>
          <h1>No todos los goles<br />valen igual.</h1>
          <p className="home-intro__text">Un <strong>ranking propio</strong> que pondera el rendimiento y el <strong>contexto de cada actuación.</strong></p>
        </div>
      </header>

      <section className="home-ranking" aria-labelledby="home-ranking-title" aria-busy={loading}>
        <header className="home-ranking-heading">
          <div className="home-ranking-heading__meta">
            <p>Ranking SFA <span aria-hidden="true">/</span> Top 3</p>
            {season && <span className="home-ranking-heading__season">Temporada {season.label}</span>}
          </div>
          <h2 id="home-ranking-title">Mejores jugadores de la temporada</h2>
        </header>
        {loading ? (
          <div className="home-loading" role="status">
            <span className="home-sr-only">Cargando los primeros puestos</span>
            <div className="skeleton" /><div className="skeleton" /><div className="skeleton" />
          </div>
        ) : error ? (
          <div className="home-state" role="alert">
            <h3>No pudimos cargar la clasificación.</h3>
            <p>Vuelve a intentarlo para consultar los primeros puestos.</p>
            <button className="home-button home-button--secondary" type="button" onClick={() => setRetry((value) => value + 1)}>Reintentar</button>
          </div>
        ) : !leader ? (
          <div className="home-state">
            <h3>Esta temporada todavía no tiene puntuaciones.</h3>
            <p>Puedes consultar otras temporadas en el ranking completo.</p>
            <Link to={rankingUrl} className="home-text-link">Explorar temporadas</Link>
          </div>
        ) : (
          <HomeRankingGallery players={players} playerUrl={playerUrl} />
        )}
      </section>

      <HomeMethod rankingUrl={rankingUrl} />
      {season && <HomeDiscoverSections key={season.key} season={season} topPlayers={players} />}
    </div>
  )
}
