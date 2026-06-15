import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { PlayerCompetitionAchievement, PlayerDetail, PlayerEvent, PlayerFixture, PlayerSeasonStats, SeasonItem } from '../types'
import { fetchPlayer, fetchPlayerAchievements, fetchPlayerEvents, fetchPlayerFixtures, fetchPlayerSeasonStats, fetchSeasons } from '../api/client'
import PlayerHeader from '../components/player/PlayerHeader'
import StatBar from '../components/player/StatBar'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import { isWorldCupSeason } from '../utils/season'

import PointsBreakdown from '../components/player/PointsBreakdown'
import FixtureList from '../components/player/FixtureList'
import PerformanceChart from '../components/player/PerformanceChart'
import CompetitionJourney from '../components/player/CompetitionJourney'

export default function PlayerPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const seasonFromUrl = searchParams.get('season') ?? ''

  useEffect(() => { window.scrollTo(0, 0) }, [id])

  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [season, setSeason] = useState<string>('')
  const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
  const [events, setEvents] = useState<PlayerEvent[]>([])
  const [fixtures, setFixtures] = useState<PlayerFixture[]>([])
  const [seasonStats, setSeasonStats] = useState<PlayerSeasonStats | null>(null)
  const [achievements, setAchievements] = useState<PlayerCompetitionAchievement[]>([])
  const [loading, setLoading] = useState(true)
  const [seasonChanging, setSeasonChanging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initialSeasonRef = useRef('')
  const isWcSeason = isWorldCupSeason(season, seasonItems)
  const playerSeasonItems: SeasonItem[] = (player?.available_seasons ?? []).map((item) => {
    const metadata = seasonItems.find((seasonItem) => seasonItem.season === item)
    return metadata ?? { season: item, is_latest: false }
  })

  function goBackToRanking() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1)
      return
    }

    const fallbackSeason = season || seasonFromUrl
    navigate(fallbackSeason ? `/ranking?season=${fallbackSeason}` : '/ranking')
  }

  useEffect(() => {
    fetchSeasons()
      .then((data) => setSeasonItems(data.seasons))
      .catch(() => {})
  }, [])

  // Carga inicial: respeta la temporada enlazada o deja que el backend resuelva la actual.
  useEffect(() => {
    if (!id) return
    const playerId = Number(id)
    setLoading(true)
    setError(null)
    fetchPlayer(playerId, seasonFromUrl || undefined)
      .then((p) => {
        setPlayer(p)
        const initialSeason = seasonFromUrl || p.available_seasons?.[0] || ''
        initialSeasonRef.current = initialSeason
        setSeason(initialSeason)
        return Promise.all([
          fetchPlayerEvents(playerId, initialSeason || undefined),
          fetchPlayerFixtures(playerId, initialSeason || undefined),
          fetchPlayerSeasonStats(playerId, initialSeason),
          fetchPlayerAchievements(playerId, initialSeason),
        ])
      })
      .then(([ev, fx, stats, playerAchievements]) => {
        setEvents(ev)
        setFixtures(fx)
        setSeasonStats(stats)
        setAchievements(playerAchievements)
      })
      .catch((e) => setError(e.message ?? 'Error al cargar el jugador'))
      .finally(() => setLoading(false))
  }, [id, seasonFromUrl])

  useEffect(() => {
    if (isWcSeason) {
      document.body.classList.add('mode-tournament')
    } else {
      document.body.classList.remove('mode-tournament')
    }
    return () => {
      document.body.classList.remove('mode-tournament')
    }
  }, [isWcSeason])

  // Reload when season changes (after initial load)
  useEffect(() => {
    if (!id || !season || !player) return
    if (season === initialSeasonRef.current) {
      initialSeasonRef.current = ''
      return
    }
    const playerId = Number(id)
    setSeasonChanging(true)
    setError(null)
    Promise.all([
      fetchPlayer(playerId, season),
      fetchPlayerEvents(playerId, season),
      fetchPlayerFixtures(playerId, season),
      fetchPlayerSeasonStats(playerId, season),
      fetchPlayerAchievements(playerId, season),
    ])
      .then(([p, ev, fx, stats, playerAchievements]) => {
        setPlayer(p)
        setEvents(ev)
        setFixtures(fx)
        setSeasonStats(stats)
        setAchievements(playerAchievements)
      })
      .catch((e) => setError(e.message ?? 'Error al cargar el jugador'))
      .finally(() => setSeasonChanging(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  if (loading) {
    return (
      <div className="page-container">
        <div className="skeleton-player-header">
          <div className="skeleton skeleton-circle" style={{ width: 100, height: 100 }} />
          <div className="skeleton-player-header__info">
            <div className="skeleton skeleton-ph" style={{ width: '30%', height: 10 }} />
            <div className="skeleton skeleton-ph" style={{ width: '65%', height: 28 }} />
            <div className="skeleton skeleton-ph" style={{ width: '45%', height: 12 }} />
            <div className="skeleton skeleton-ph" style={{ width: 100, height: 32, borderRadius: 4 }} />
          </div>
        </div>
        <div className="skeleton-stat-bar">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-stat-bar__item">
              <div className="skeleton skeleton-ph" style={{ width: 40, height: 28 }} />
              <div className="skeleton skeleton-ph" style={{ width: 56, height: 8 }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error || !player) {
    return (
      <div className="page-container">
        <button type="button" className="back-link" onClick={goBackToRanking}>
          <span aria-hidden="true">←</span>
          Volver al ranking
        </button>
        <div className="empty-state">{error ?? 'Jugador no encontrado.'}</div>
      </div>
    )
  }

  return (
    <div className={`page-container${isWcSeason ? ' player-page--wc' : ''}`}>
      <button type="button" className="back-link" onClick={goBackToRanking}>
        <span aria-hidden="true">←</span>
        Volver al ranking
      </button>

      <PlayerHeader player={player} isWorldCup={isWcSeason} />

      {player.available_seasons && player.available_seasons.length > 1 && (
        <div className="pp-season-bar">
          <span className="pp-season-bar__label">Temporada</span>
          <SeasonDropdown
            items={playerSeasonItems}
            value={season}
            onChange={setSeason}
            includeAll={true}
          />
        </div>
      )}
      <div
        className={`pp-season-content${seasonChanging ? ' pp-season-content--changing' : ''}`}
        aria-busy={seasonChanging}
      >
        <StatBar player={player} fixtures={fixtures} seasonStats={seasonStats} />

        <CompetitionJourney achievements={achievements} historical={season === 'all'} />

        <PerformanceChart fixtures={fixtures} playerTeam={player.team} />

        <p className="section-title mt-32">Historial de partidos</p>
        <FixtureList fixtures={fixtures} events={events} />

        <PointsBreakdown player={player} events={events} fixtures={fixtures} seasonStats={seasonStats} />
      </div>
    </div>
  )
}
