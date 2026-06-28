import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { Competition, RankedPlayer, PlayerDetail, SeasonItem } from '../types'
import { fetchRanking, fetchPlayer, fetchCompetitions, fetchSeasons } from '../api/client'
import FilterBar from '../components/ranking/FilterBar'
import RankingCard from '../components/ranking/RankingCard'
import ShowcaseCard from '../components/ranking/ShowcaseCard'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import WorldCupBanner from '../components/shared/WorldCupBanner'
import WorldCupPageHeader from '../components/shared/WorldCupPageHeader'
import WcLiveChip from '../components/shared/WcLiveChip'
import { useCountUp } from '../hooks/useCountUp'
import { isSeasonReceivingWcPoints, isWorldCupSeason } from '../utils/season'
import { playerOrTeamMatchesSearch } from '../utils/teamSearch'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 350
const MAIN_COMPETITION_IDS = [10, 1, 3, 6, 7, 9]
const WORLD_CUP_POSITION_OPTIONS = ['DEL', 'EXT', 'MCO', 'MC', 'LAT', 'DC']
const BONUS_FILTER_OPTIONS = ['Promesa', 'Veterano']

function matchesBonusFilter(player: RankedPlayer, bonusFilter: string): boolean {
  return !bonusFilter || player.b1_bonus_label === bonusFilter
}

export default function RankingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
  const [season, setSeason] = useState<string>(searchParams.get('season') ?? '')
  const [position, setPosition] = useState('')
  const [bonusFilter, setBonusFilter] = useState('')
  const [competition, setCompetition] = useState<number | undefined>(undefined)
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [search, setSearch] = useState('')
  const [players, setPlayers] = useState<RankedPlayer[]>([])
  const [totalPlayers, setTotalPlayers] = useState(0)
  const [searchResults, setSearchResults] = useState<RankedPlayer[] | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [topDetails, setTopDetails] = useState<Map<number, PlayerDetail>>(new Map())
  const [loadingRanking, setLoadingRanking] = useState(true)
  const [loadingShowcase, setLoadingShowcase] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [pageDir, setPageDir] = useState<'next' | 'prev'>('next')
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isWcSeason = isWorldCupSeason(season, seasonItems)
  const showWcBanner = isSeasonReceivingWcPoints(season, seasonItems)
  const wcSeason = seasonItems.find((item) => item.is_world_cup)?.season

  useEffect(() => {
    fetchCompetitions().then(setCompetitions).catch(() => {})
    fetchSeasons()
      .then((data) => {
        setSeasonItems(data.seasons)
        const fromUrl = searchParams.get('season')
        if (!fromUrl) {
          // No URL param: initialize from API and stamp the URL so back-navigation works
          const fallback = data.seasons.find((item) => item.is_latest)?.season
            ?? data.seasons[0]?.season
          if (fallback) {
            setSeason(fallback)
            setSearchParams({ season: fallback }, { replace: true })
          }
        }
      })
      .catch(() => {})
  }, [])

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

  useEffect(() => {
    if (!isWcSeason) return
    setPosition('')
    setBonusFilter('')
    setCompetition(undefined)
    setSearch('')
  }, [isWcSeason])

  useEffect(() => {
    setPage(0)
    setPageDir('next')
    setSearchResults(null)
  }, [position, competition, search, bonusFilter])

  // Server-side name search — fires when local filter yields nothing and query >= 2 chars
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)

    const localHits = search
      ? players.filter((p) => matchesBonusFilter(p, bonusFilter) && playerOrTeamMatchesSearch(p.name, p.team, search))
      : players.filter((p) => matchesBonusFilter(p, bonusFilter))

    if (!search || search.length < 2 || (!isWcSeason && localHits.length > 0)) {
      setSearchResults(null)
      return
    }

    setSearchLoading(true)
    searchTimerRef.current = setTimeout(() => {
      fetchRanking({ season, name: search, position: position || undefined, limit: 50 })
        .then((data) => setSearchResults(data.ranking.filter((p) => matchesBonusFilter(p, bonusFilter))))
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false))
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [search, players, season, position, isWcSeason, bonusFilter])

  useEffect(() => {
    if (!season) return
    setLoadingRanking(true)
    setLoadingShowcase(true)
    setError(null)

    fetchRanking({ season, position: position || undefined, competition_id: competition, limit: 100 })
      .then((data) => {
        setPlayers(data.ranking)
        setTotalPlayers(data.total)
        setLoadingRanking(false)

        if (data.ranking.length >= 3) {
          Promise.allSettled(
            data.ranking.slice(0, 3).map((p) => fetchPlayer(p.id, season))
          ).then((results) => {
            const map = new Map<number, PlayerDetail>()
            data.ranking.slice(0, 3).forEach((p, i) => {
              const r = results[i]
              if (r.status === 'fulfilled') map.set(p.id, r.value)
            })
            setTopDetails(map)
            setLoadingShowcase(false)
          })
        } else {
          setTopDetails(new Map())
          setLoadingShowcase(false)
        }
      })
      .catch((e) => {
        setError(e.message ?? 'Error al cargar el ranking')
        setLoadingRanking(false)
        setLoadingShowcase(false)
      })
  }, [position, competition, season])

  const bonusFilteredPlayers = players.filter((p) => matchesBonusFilter(p, bonusFilter))
  const top3 = bonusFilteredPlayers.slice(0, 3)
  const restPlayers = bonusFilteredPlayers.slice(3)

  const localFiltered = search
    ? bonusFilteredPlayers.filter((p) => playerOrTeamMatchesSearch(p.name, p.team, search))
    : restPlayers

  const isServerSearch = search.length >= 2 && (isWcSeason || localFiltered.length === 0)
  const filteredPlayers = isServerSearch ? (searchResults ?? []) : localFiltered

  const showHero = !search && bonusFilteredPlayers.length >= 3
  const totalPages = Math.ceil(filteredPlayers.length / PAGE_SIZE)
  const currentPagePlayers = filteredPlayers.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const mainCompetitions = competitions
    .filter((c) => MAIN_COMPETITION_IDS.includes(c.id))
    .sort((a, b) => MAIN_COMPETITION_IDS.indexOf(a.id) - MAIN_COMPETITION_IDS.indexOf(b.id))

  const activeComp = competitions.find((c) => c.id === competition)
  const contextParts = [activeComp?.name, position || null, bonusFilter || null].filter(Boolean)
  const contextLabel = contextParts.length > 0 ? contextParts.join(' · ') : null

  const animatedTotal = useCountUp(totalPlayers)
  const seasonPicker = seasonItems.length > 0 ? (
    <div className="rp-season-picker">
      <span className="rp-season-picker__hint">Elige la temporada</span>
      <SeasonDropdown
        items={seasonItems}
        value={season}
        onChange={(nextSeason) => {
          setSeason(nextSeason)
          setSearchParams({ season: nextSeason }, { replace: true })
          setPage(0)
          setPageDir('next')
        }}
        includeAll={true}
      />
    </div>
  ) : null

  function goNext() {
    setPageDir('next')
    setPage((p) => p + 1)
  }

  function goPrev() {
    setPageDir('prev')
    setPage((p) => p - 1)
  }

  function goToPage(nextPage: number) {
    if (nextPage === page) return
    setPageDir(nextPage > page ? 'next' : 'prev')
    setPage(nextPage)
  }

  const visiblePages = Array.from({ length: totalPages }, (_, index) => index)
    .filter((index) => (
      index === 0
      || index === totalPages - 1
      || Math.abs(index - page) <= 1
    ))

  return (
    <div className="ranking-page">
      {isWcSeason ? (
        <WorldCupPageHeader />
      ) : (
      <header className="rp-header">
        <div className="rp-header__copy">
          <span className="rp-header__eyebrow">
            {season === 'all'
              ? 'Stats Football Award · Historial'
              : 'Stats Football Award · Clasificación SFA'}
          </span>
          <h1 className="rp-header__title">Ranking de jugadores</h1>
          <p className="rp-header__sub">No todos los goles valen igual.</p>
        </div>
      </header>
      )}

      <section
        className={`rp-control-deck${isWcSeason ? ' rp-control-deck--wc' : ''}`}
        aria-label={isWcSeason ? 'Controles del ranking mundial' : 'Controles del ranking'}
      >
        <WcLiveChip />
        {seasonPicker}
        <Link to="/metodologia" className="rp-control-deck__method">
          <span>
            <strong>Cómo funciona SFA</strong>
            <small>No todos los goles valen igual</small>
          </span>
          <i aria-hidden="true">→</i>
        </Link>
      </section>

      <section
        className={`rp-intro${isWcSeason ? ' rp-intro--wc' : ''}`}
        aria-labelledby="rp-intro-title"
      >
        <div className="rp-intro__copy">
          <span className="rp-intro__eyebrow">
            {isWcSeason ? 'Cómo funciona este ranking' : 'Qué mide SFA'}
          </span>
          <h2 id="rp-intro-title">
            {isWcSeason
              ? 'Todos empiezan en cero; cada actuación suma según su impacto real.'
              : 'No contamos solo acciones: medimos cuánto cambiaron el partido.'}
          </h2>
        </div>
        <p className="rp-intro__summary">
          Rival, marcador, minuto, dificultad y trascendencia modifican el valor
          de cada gol, asistencia y acción defensiva.
        </p>
        <Link to="/metodologia" className="rp-intro__link">
          Cómo funciona SFA
          <span aria-hidden="true">→</span>
        </Link>
      </section>

      {isWcSeason && (
        <div className="rp-world-cup-match-preview">
          <WcLiveChip />
        </div>
      )}

      {showWcBanner && !isWcSeason && (
        <div className="rp-wc-banner-wrap">
          <WorldCupBanner
            onViewWorldCup={wcSeason ? () => { setSeason(wcSeason); setSearchParams({ season: wcSeason }, { replace: true }) } : undefined}
          />
        </div>
      )}

      {loadingRanking && (
        <>
          <div className="players-showcase">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton skeleton-showcase-card" />
            ))}
          </div>
          <div className="rp-table-section">
            <div className="ranking-cards-grid">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skeleton rc-skeleton" />
              ))}
            </div>
          </div>
        </>
      )}

      {!loadingRanking && error && (
        <div className="empty-state">
          {isWcSeason ? `Mundial 2026 · ${error}` : error}
        </div>
      )}

      {!loadingRanking && !error && (
        <>
          {showHero && (
            <section
              className={`rp-podium${isWcSeason ? ' rp-podium--wc' : ''}`}
              aria-label="Podio del ranking"
            >
              <div className="players-showcase">
                {top3.map((p, index) => (
                  <ShowcaseCard
                    key={p.id}
                    player={p}
                    detail={loadingShowcase ? null : (topDetails.get(p.id) ?? null)}
                    isFirst={p.rank === 1}
                    podiumPlace={index + 1}
                    season={season}
                    isWorldCup={isWcSeason}
                  />
                ))}
              </div>
            </section>
          )}

          <div className={`rp-table-section${isWcSeason ? ' rp-table-section--wc' : ''}`}>
            <div className={`rp-ranking-head${isWcSeason ? ' rp-ranking-head--wc' : ''}`}>
              <div>
                <span>{isWcSeason ? 'Edición Mundial' : 'Clasificación completa'}</span>
                <h2>Todos los jugadores</h2>
              </div>
              {isWcSeason && (
                <div className="wc-ranking-tools">
                  <label className="wc-position-filter">
                    <span>Posición</span>
                    <strong aria-hidden="true">{position || 'Todas'}</strong>
                    <select
                      value={position}
                      onChange={(event) => setPosition(event.target.value)}
                      aria-label="Filtrar ranking mundial por posición"
                    >
                      <option value="">Todas</option>
                      {WORLD_CUP_POSITION_OPTIONS.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label className="wc-position-filter">
                    <span>Perfil</span>
                    <strong aria-hidden="true">{bonusFilter || 'Todos'}</strong>
                    <select
                      value={bonusFilter}
                      onChange={(event) => setBonusFilter(event.target.value)}
                      aria-label="Filtrar ranking mundial por promesa o veterano"
                    >
                      <option value="">Todos</option>
                      {BONUS_FILTER_OPTIONS.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label className="wc-ranking-search">
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <circle cx="8.5" cy="8.5" r="5.5" />
                    <path d="m13 13 4 4" />
                  </svg>
                  <input
                    type="search"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Buscar jugador o selección"
                    aria-label="Buscar en el ranking del Mundial"
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => setSearch('')}
                      aria-label="Limpiar búsqueda"
                    >
                      ×
                    </button>
                  )}
                  </label>
                </div>
              )}
            </div>

            {!isWcSeason && (
              <FilterBar
                position={position}
                onPosition={setPosition}
                bonusFilter={bonusFilter}
                onBonusFilter={setBonusFilter}
                competition={competition}
                onCompetition={setCompetition}
                competitions={mainCompetitions}
                search={search}
                onSearch={setSearch}
              />
            )}

            {contextLabel && (
              <div className="rp-context-label">
                {contextLabel}
              </div>
            )}

            {isServerSearch && searchLoading ? (
              <div className="empty-state">Buscando "{search}"…</div>
            ) : currentPagePlayers.length === 0 ? (
              <div className="empty-state">
                {search
                  ? `Sin resultados para "${search}"`
                  : isWcSeason
                    ? 'Mundial 2026 · Todavía no hay jugadores clasificados.'
                    : 'Sin jugadores para los filtros seleccionados.'}
              </div>
            ) : (
              <>
                <div className="ranking-table-head" aria-hidden="true">
                  <span>Pos.</span>
                  <span />
                  <span>Jugador</span>
                  <span>Rol</span>
                  <span>PJ</span>
                  <span>G + A</span>
                  <span>Puntos SFA</span>
                </div>
                <div
                  key={`${page}-${pageDir}`}
                  className={`ranking-cards-grid ranking-cards-grid--${pageDir === 'next' ? 'from-right' : 'from-left'}`}
                >
                  {currentPagePlayers.map((p, i) => (
                    <RankingCard
                      key={p.id}
                      player={p}
                      index={i}
                      competitionName={activeComp?.name}
                      season={season}
                      isWorldCup={isWcSeason}
                    />
                  ))}
                </div>

                {totalPages > 1 && (
                  <nav className="ranking-pagination" aria-label="Páginas del ranking">
                    <button
                      className="pagination-btn pagination-btn--prev"
                      onClick={goPrev}
                      disabled={page === 0}
                      aria-label="Ir a la página anterior"
                    >
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <path d="m10 3-5 5 5 5" />
                      </svg>
                      <span>Anterior</span>
                    </button>

                    <div className="ranking-pagination__center">
                      <div className="pagination-pages">
                        {visiblePages.map((pageIndex, index) => {
                          const previousVisible = visiblePages[index - 1]
                          const needsGap = previousVisible != null && pageIndex - previousVisible > 1
                          return (
                            <span className="pagination-pages__slot" key={pageIndex}>
                              {needsGap && <span className="pagination-ellipsis">…</span>}
                              <button
                                className={`pagination-page${pageIndex === page ? ' pagination-page--active' : ''}`}
                                onClick={() => goToPage(pageIndex)}
                                aria-label={`Ir a la página ${pageIndex + 1}`}
                                aria-current={pageIndex === page ? 'page' : undefined}
                              >
                                {pageIndex + 1}
                              </button>
                            </span>
                          )
                        })}
                      </div>
                      <div className="pagination-progress" aria-hidden="true">
                        <span style={{ transform: `scaleX(${(page + 1) / totalPages})` }} />
                      </div>
                      <span className="ranking-pagination__status">
                        {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filteredPlayers.length)}
                        {' '}de {filteredPlayers.length} jugadores
                      </span>
                    </div>

                    <button
                      className="pagination-btn pagination-btn--next"
                      onClick={goNext}
                      disabled={page >= totalPages - 1}
                      aria-label="Ir a la página siguiente"
                    >
                      <span>Siguiente</span>
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <path d="m6 3 5 5-5 5" />
                      </svg>
                    </button>
                  </nav>
                )}
                <div className="rp-ranking-total" aria-label="Jugadores contabilizados">
                  <span>{totalPlayers > 0 ? animatedTotal.toLocaleString('es-ES') : '—'}</span>
                  <small>Jugadores contabilizados</small>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
