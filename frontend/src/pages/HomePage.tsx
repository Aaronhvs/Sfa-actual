import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking, fetchSeasons } from '../api/client'
import type { RankedPlayer, SeasonItem } from '../types'
import HomeRankingGallery from '../components/HomeRankingGallery'
import HomeMethod from '../components/HomeMethod'
import HomeContextExample from '../components/HomeContextExample'
import HomeDiscoverSections from '../components/HomeDiscoverSections'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import { tournamentCompetitionLogoByName } from '../utils/tournaments'
import './HomePage.css'

const COVERED_LEAGUES = ['Champions League', 'La Liga', 'Premier League', 'Serie A', 'Bundesliga', 'Ligue 1']

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
      <header className="home-hero">
        <div className="home-hero__copy">
          <p className="tp-eyebrow">Ranking de jugadores{season && ` · Temporada ${season.label}`}</p>
          <h1>No todos los goles valen igual.</h1>
          <p className="home-hero__lead">
            SFA puntúa cada acción de cada jugador según <strong>contra quién</strong>, <strong>en qué momento</strong> y <strong>en qué competición</strong> ocurre. El resultado es un ranking que premia el impacto real, no solo las estadísticas.
          </p>
          <div className="home-hero__actions">
            <Link to={rankingUrl} className="home-cta">Ver el ranking <ArrowIcon /></Link>
            <Link to="/metodologia" className="home-cta home-cta--ghost">Cómo funciona</Link>
          </div>
          <div className="home-hero__leagues">
            <ul aria-label="Competiciones analizadas">
              {COVERED_LEAGUES.map((name) => {
                const logo = tournamentCompetitionLogoByName(name)
                return (
                  <li key={name} title={name}>
                    <span className="tp-tile">{logo && <img src={logo} alt={name} loading="lazy" />}</span>
                  </li>
                )
              })}
            </ul>
            <span>Champions League, las cinco grandes ligas y sus copas</span>
          </div>
        </div>
        <HomeContextExample />
      </header>

      <section className="home-ranking sfa-podium" aria-labelledby="home-ranking-title" aria-busy={loading}>
        <header className="home-section-head">
          <div>
            <p className="tp-eyebrow">Top 3 de la temporada{season && ` ${season.label}`}</p>
            <h2 id="home-ranking-title">Quién manda en SFA</h2>
          </div>
          <Link to={rankingUrl}>Ranking completo <ArrowIcon /></Link>
        </header>
        {loading ? (
          <div className="home-loading" role="status">
            <span className="sr-only">Cargando los primeros puestos</span>
            <div className="skeleton" /><div className="skeleton" /><div className="skeleton" />
          </div>
        ) : error ? (
          <div className="home-state" role="alert">
            <strong>No pudimos cargar la clasificación.</strong>
            <span>Vuelve a intentarlo para consultar los primeros puestos.</span>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>Reintentar</button>
          </div>
        ) : !leader ? (
          <div className="home-state">
            <strong>Esta temporada todavía no tiene puntuaciones.</strong>
            <span>Puedes consultar otras temporadas en el ranking completo.</span>
            <Link to={rankingUrl}>Explorar temporadas</Link>
          </div>
        ) : (
          <HomeRankingGallery players={players} playerUrl={playerUrl} />
        )}
      </section>

      {season && <HomeDiscoverSections key={season.key} season={season} topPlayers={players} />}
      <HomeMethod />
    </div>
  )
}
