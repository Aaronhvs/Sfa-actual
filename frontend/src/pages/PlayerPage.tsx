import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { PlayerCompetitionAchievement, PlayerDetail, PlayerEvent, PlayerFixture, PlayerIndividualHonor, PlayerSeasonStats, SeasonItem } from '../types'
import { fetchPlayer, fetchPlayerAchievements, fetchPlayerEvents, fetchPlayerFixtures, fetchPlayerIndividualHonors, fetchPlayerSeasonStats, fetchSeasons } from '../api/client'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import { isWorldCupSeason } from '../utils/season'
import ProfileMoments from '../components/player/ProfileMoments'
import {
  ProfileCompetitions,
  ProfileContext,
  ProfileFixtures,
  ProfileHero,
  ProfileHonors,
  ProfileKpis,
  ProfileMatchBars,
  ProfilePointsSources,
  ProfileStyle,
} from '../components/player/ProfileView'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import './PlayerPage.css'

function safeRankingReturnTo(value: string | null): string | null {
  if (!value || value.startsWith('//')) return null

  try {
    const parsed = new URL(value, window.location.origin)
    if (parsed.origin !== window.location.origin || parsed.pathname !== '/ranking') {
      return null
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return null
  }
}

export default function PlayerPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const seasonFromUrl = searchParams.get('season') ?? ''
  const scopeFromUrl = searchParams.get('scope') ?? ''

  useEffect(() => { window.scrollTo(0, 0) }, [id])

  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [season, setSeason] = useState<string>('')
  const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
  const [events, setEvents] = useState<PlayerEvent[]>([])
  const [fixtures, setFixtures] = useState<PlayerFixture[]>([])
  const [seasonStats, setSeasonStats] = useState<PlayerSeasonStats | null>(null)
  const [achievements, setAchievements] = useState<PlayerCompetitionAchievement[]>([])
  const [individualHonors, setIndividualHonors] = useState<PlayerIndividualHonor[]>([])
  const [loading, setLoading] = useState(true)
  const [seasonChanging, setSeasonChanging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initialSeasonRef = useRef('')
  const isWcSeason = isWorldCupSeason(season, seasonItems)
  const selectedSeasonItem = seasonItems.find((item) => item.key === season)
  const playerSeasonItems: SeasonItem[] = seasonItems.filter((item) => (
    (player?.available_scopes ?? []).includes(item.key)
  ))

  function goBackToRanking() {
    const returnTo = safeRankingReturnTo(searchParams.get('returnTo'))
    if (returnTo) {
      navigate(returnTo)
      return
    }

    const targetScope = season || scopeFromUrl
    navigate(targetScope ? `/ranking?scope=${targetScope}` : '/ranking')
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
    fetchPlayer(
      playerId,
      scopeFromUrl ? undefined : seasonFromUrl || undefined,
      scopeFromUrl || undefined,
    )
      .then((p) => {
        setPlayer(p)
        const initialSeason = scopeFromUrl || p.scope || seasonFromUrl || p.available_scopes?.[0] || ''
        initialSeasonRef.current = initialSeason
        setSeason(initialSeason)
        const isAll = initialSeason === 'all'
        const requestScope = isAll ? undefined : initialSeason
        const requestSeason = isAll ? 'all' : undefined
        const statsRequest = fetchPlayerSeasonStats(playerId, requestSeason, requestScope)
        return Promise.all([
          fetchPlayerEvents(playerId, requestSeason, requestScope),
          fetchPlayerFixtures(playerId, requestSeason, requestScope),
          statsRequest,
          fetchPlayerAchievements(playerId, requestSeason, requestScope),
          fetchPlayerIndividualHonors(playerId, requestSeason, requestScope),
        ])
      })
      .then(([ev, fx, stats, playerAchievements, playerHonors]) => {
        setEvents(ev)
        setFixtures(fx)
        setSeasonStats(stats)
        setAchievements(playerAchievements)
        setIndividualHonors(playerHonors)
      })
      .catch((e) => setError(e.message ?? 'Error al cargar el jugador'))
      .finally(() => setLoading(false))
  }, [id, seasonFromUrl, scopeFromUrl])

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
    setIndividualHonors([])
    const isAll = season === 'all'
    const requestScope = isAll ? undefined : season
    const requestSeason = isAll ? 'all' : undefined
    const statsRequest = fetchPlayerSeasonStats(playerId, requestSeason, requestScope)
    Promise.all([
      fetchPlayer(playerId, requestSeason, requestScope),
      fetchPlayerEvents(playerId, requestSeason, requestScope),
      fetchPlayerFixtures(playerId, requestSeason, requestScope),
      statsRequest,
      fetchPlayerAchievements(playerId, requestSeason, requestScope),
      fetchPlayerIndividualHonors(playerId, requestSeason, requestScope),
    ])
      .then(([p, ev, fx, stats, playerAchievements, playerHonors]) => {
        setPlayer(p)
        setEvents(ev)
        setFixtures(fx)
        setSeasonStats(stats)
        setAchievements(playerAchievements)
        setIndividualHonors(playerHonors)
      })
      .catch((e) => setError(e.message ?? 'Error al cargar el jugador'))
      .finally(() => setSeasonChanging(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  if (loading) {
    return (
      <main className="pf-page" aria-busy="true">
        <span className="sr-only" role="status">Cargando jugador</span>
        <div className="pf-skel pf-skel--hero" />
        <div className="pf-skel pf-skel--row" />
        <div className="pf-skel pf-skel--bars" />
      </main>
    )
  }

  if (error || !player) {
    return (
      <main className="pf-page">
        <button type="button" className="pf-back" onClick={goBackToRanking}><ArrowIcon direction="left" /> Volver al ranking</button>
        <div className="pf-empty" role="alert">{error ?? 'Jugador no encontrado.'}</div>
      </main>
    )
  }

  const seasonLabel = season === 'all'
    ? 'Total histórico'
    : `Temporada ${selectedSeasonItem?.label ?? player.season}`
  const matchSeason = selectedSeasonItem?.season ?? player.season
  const seasonPicker = playerSeasonItems.length > 1 ? (
    <div className="pf-season">
      <SeasonDropdown
        items={playerSeasonItems}
        value={season}
        onChange={(value) => {
          setSeason(value)
          navigate(`/player/${id}?${value === 'all' ? 'season=all' : `scope=${value}`}`, { replace: true })
        }}
        includeAll={true}
      />
    </div>
  ) : null

  return (
    <main className={`pf-page${isWcSeason ? ' pf-page--wc' : ''}`}>
      <nav className="pf-crumbs" aria-label="Ruta">
        <button type="button" className="pf-back" onClick={goBackToRanking}><ArrowIcon direction="left" /> Volver al ranking</button>
      </nav>

      <ProfileHero player={player} fixtures={fixtures} stats={seasonStats} seasonLabel={seasonLabel} seasonPicker={seasonPicker} scope={season} />

      <div className={`pf-content${seasonChanging ? ' is-changing' : ''}`} aria-busy={seasonChanging}>
        <ProfileKpis player={player} stats={seasonStats} fixtures={fixtures} />

        <ProfileMatchBars fixtures={fixtures} team={player.team} season={matchSeason} />
        <ProfileHonors achievements={achievements} honors={individualHonors} />

        {fixtures.length > 0 && (
          <section className="pf-highlights" aria-labelledby="pf-hl-title">
            <header className="pf-section-head"><h2 id="pf-hl-title">Lo más destacado</h2><p>Sus acciones de más valor y lo mejor de su temporada</p></header>
            <ProfileMoments fixtures={fixtures} events={events} team={player.team} season={matchSeason} />
          </section>
        )}

        <ProfileStyle playerId={player.id} scope={season} available={player.available_scopes} stats={seasonStats} matches={player.matches} />

        <ProfileContext events={events} fixtures={fixtures} team={player.team} />

        <div className="pf-split">
          <ProfilePointsSources player={player} />
          <ProfileCompetitions fixtures={fixtures} />
        </div>

        <ProfileFixtures fixtures={fixtures} events={events} team={player.team} season={matchSeason} />

      </div>
    </main>
  )
}
